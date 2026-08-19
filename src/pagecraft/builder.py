"""The Pagecraft build pipeline.

The builder renders a deterministic set of generated artifacts and records every
artifact in a versioned manifest.  It calculates all collection output on each
build but only writes files whose rendered content changed, which keeps builds
fast while ensuring indexes, feeds, tags, categories, pagination, and stale
files are always correct after an edit, rename, or deletion.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from math import ceil
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlsplit

from .assets import sync_assets
from .config import ConfigError, SiteConfig
from .content import ContentError, Page, route_to_output, slugify
from .discovery import build_robots, build_sitemap
from .renderer import generate_stylesheet, render_markdown
from .rss import build_rss
from .templates import make_environment, site_context


MANIFEST_SCHEMA = 2


class BuildError(ValueError):
    """A deterministic error an author can resolve in source or configuration."""


@dataclass
class BuildReport:
    output_dir: str
    generated: list[str]
    skipped: list[str]
    removed: list[str]
    copied: list[str]
    assets_skipped: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "output_dir": self.output_dir,
            "posts_built": len(self.generated),
            "files_skipped": len(self.skipped),
            "assets_copied": len(self.copied),
            "feed_generated": True,
            "generated": self.generated,
            "skipped": self.skipped,
            "removed": self.removed,
            "copied": self.copied,
            "assets_skipped": self.assets_skipped,
        }


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _absolute(site_url: str, route: str) -> str:
    return site_url.rstrip("/") + ("/" if route == "/" else route)


class Builder:
    """Build a Pagecraft project from Markdown, templates, and static assets."""

    def __init__(
        self,
        project_root: str,
        incremental: bool = True,
        *,
        include_drafts: bool = False,
        include_future: bool = False,
        now: datetime | None = None,
    ) -> None:
        self.project_root = str(Path(project_root).resolve())
        self.config = SiteConfig.load(self.project_root)
        self.env = make_environment(self.project_root)
        self.incremental = incremental
        self.include_drafts = include_drafts
        self.include_future = include_future
        self.now = now or datetime.now()
        self.output_dir = str(Path(self.project_root) / self.config.output_dir)
        self.manifest_path = Path(self.project_root) / ".pagecraft" / "manifest.json"
        self.manifest = self._load_manifest()
        self.posts: list[Page] = []
        self.pages: list[Page] = []
        self.published_posts: list[Page] = []
        self.published_pages: list[Page] = []
        self.generated: list[str] = []
        self.skipped: list[str] = []
        self.removed: list[str] = []
        self._routes: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Manifest and collection setup
    # ------------------------------------------------------------------
    def _load_manifest(self) -> dict[str, Any]:
        if not self.incremental or not self.manifest_path.exists():
            return {"schema": MANIFEST_SCHEMA, "outputs": {}, "assets": {}}
        try:
            manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"schema": MANIFEST_SCHEMA, "outputs": {}, "assets": {}}
        if manifest.get("schema") != MANIFEST_SCHEMA:
            return {"schema": MANIFEST_SCHEMA, "outputs": {}, "assets": {}}
        manifest.setdefault("outputs", {})
        manifest.setdefault("assets", {})
        return manifest

    def _save_manifest(self, outputs: dict[str, str], assets: dict[str, str]) -> None:
        signature = _hash_text("\n".join(f"{key}:{value}" for key, value in sorted(outputs.items())))
        payload = {
            "schema": MANIFEST_SCHEMA,
            "generated_at": self.now.isoformat(),
            "outputs": outputs,
            "assets": assets,
            "signature": signature,
        }
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def _collect_pages(self, directory: str, kind: str) -> list[Page]:
        root = Path(self.project_root) / directory
        if not root.is_dir():
            return []
        pages: list[Page] = []
        for source in sorted(path for path in root.rglob("*") if path.suffix.lower() in {".md", ".markdown"}):
            page = Page.load(str(source), kind)
            page.html = render_markdown(page.raw)
            pages.append(page)
        pages.sort(key=lambda page: (page.date, page.title.lower()), reverse=True)
        return pages

    def _post_route(self, page: Page) -> str:
        if page.permalink:
            return page.permalink
        return f"/{page.slug}.html" if self.config.permalinks else f"/posts/{page.slug}.html"

    def _page_route(self, page: Page) -> str:
        return page.permalink or f"/{page.slug}.html"

    # Kept for projects and tests that used Pagecraft's v0.1 internal helper.
    def _post_url(self, page: Page) -> str:
        return page.url or self._post_route(page)

    def _claim_route(self, route: str, owner: str) -> None:
        try:
            output = route_to_output(route)
        except ContentError as exc:
            raise BuildError(str(exc)) from exc
        existing = self._routes.get(output)
        if existing:
            raise BuildError(f"Route collision: '{route}' for {owner} conflicts with {existing}.")
        self._routes[output] = owner

    def _assign_routes(self) -> None:
        self._routes = {}
        fixed = {
            "/": "the home page",
            "/style.css": "the built-in stylesheet",
            "/tags.html": "the tag index",
            "/categories.html": "the category index",
            "/archive.html": "the archive page",
        }
        if self.config.feed_enabled:
            fixed[f"/{self.config.feed_filename}"] = "the RSS feed"
        if self.config.sitemap_enabled and not self.config.is_placeholder_url:
            fixed[f"/{self.config.sitemap_filename}"] = "the sitemap"
        if self.config.robots_enabled and not self.config.is_placeholder_url:
            fixed[f"/{self.config.robots_filename}"] = "the robots file"
        for route, owner in fixed.items():
            self._claim_route(route, owner)

        for page in self.posts + self.pages:
            page.url = self._post_route(page) if page.kind == "post" else self._page_route(page)
            page.output_path = route_to_output(page.url)
            self._claim_route(page.url, str(Path(page.path).relative_to(self.project_root)))

        tags = {tag for post in self.published_posts for tag in post.tags}
        categories = {category for post in self.published_posts for category in post.categories}
        for tag in sorted(tags, key=str.lower):
            self._claim_route(f"/tag-{slugify(tag)}.html", f"tag '{tag}'")
        for category in sorted(categories, key=str.lower):
            self._claim_route(f"/category-{slugify(category)}.html", f"category '{category}'")
        total_pages = max(1, ceil(len(self.published_posts) / self.config.pagination_per_page))
        for number in range(2, total_pages + 1):
            self._claim_route(f"/page/{number}/", f"pagination page {number}")

    def _prepare(self) -> None:
        try:
            self.posts = self._collect_pages(self.config.posts_dir, "post")
            self.pages = self._collect_pages(self.config.pages_dir, "page")
            self.published_posts = [
                page for page in self.posts
                if page.published(self.now, include_drafts=self.include_drafts, include_future=self.include_future)
            ]
            self.published_pages = [
                page for page in self.pages
                if page.published(self.now, include_drafts=self.include_drafts, include_future=self.include_future)
            ]
            for page in self.published_posts + self.published_pages:
                page.is_preview = page.draft or page.date > self.now
            self._assign_routes()
        except (ConfigError, ContentError) as exc:
            raise BuildError(str(exc)) from exc

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------
    def _base_context(self) -> dict[str, Any]:
        context = site_context(self.project_root)
        context.update(
            posts=self.published_posts,
            published_posts=self.published_posts,
            all_posts=self.posts,
            pages=self.published_pages,
            build_time=self.now,
            preview_mode=self.include_drafts or self.include_future,
        )
        return context

    def _terms(self, field: str, prefix: str) -> list[dict[str, Any]]:
        values = sorted({term for post in self.published_posts for term in getattr(post, field)}, key=str.lower)
        return [
            {
                "name": value,
                "slug": slugify(value),
                "url": f"/{prefix}-{slugify(value)}.html",
                "count": sum(value in getattr(post, field) for post in self.published_posts),
            }
            for value in values
        ]

    def _archives(self) -> list[dict[str, Any]]:
        groups: dict[tuple[int, int], list[Page]] = {}
        for post in self.published_posts:
            groups.setdefault((post.date.year, post.date.month), []).append(post)
        return [
            {"year": year, "month": month, "posts": posts}
            for (year, month), posts in sorted(groups.items(), reverse=True)
        ]

    def _meta(self, content: Page | None, route: str, *, title: str | None = None, description: str | None = None) -> dict[str, str]:
        canonical = (content.canonical_url if content and content.canonical_url else _absolute(self.config.url, route))
        image = (content.image if content and content.image else self.config.seo_default_image)
        if image.startswith("/"):
            image = _absolute(self.config.url, image)
        return {
            "title": title or (content.title if content else self.config.title),
            "description": description if description is not None else (content.description if content else self.config.description),
            "canonical": canonical,
            "image": image,
            "type": "article" if content and content.kind == "post" else "website",
            "published": content.date.isoformat() if content and content.kind == "post" else "",
            "updated": (content.updated or content.date).isoformat() if content and content and content.kind == "post" else "",
        }

    def _render_outputs(self) -> dict[str, str]:
        self._prepare()
        context = self._base_context()
        tags = self._terms("tags", "tag")
        categories = self._terms("categories", "category")
        archives = self._archives()
        context.update(tags=tags, categories=categories, archives=archives)
        outputs: dict[str, str] = {}

        # Built-in stylesheet combines the design system and Pygments colours.
        theme_file = Path(__file__).resolve().parent / "resources" / "static" / "theme.css"
        theme = theme_file.read_text(encoding="utf-8") if theme_file.exists() else ""
        outputs["style.css"] = theme + "\n" + generate_stylesheet()

        # Paged home pages.
        per_page = self.config.pagination_per_page
        page_count = max(1, ceil(len(self.published_posts) / per_page))
        index_template = self.env.get_template("index.html")
        for number in range(1, page_count + 1):
            start = (number - 1) * per_page
            items = self.published_posts[start:start + per_page]
            route = "/" if number == 1 else f"/page/{number}/"
            pagination = {
                "current": number,
                "total": page_count,
                "per_page": per_page,
                "previous_url": "/" if number == 2 else (f"/page/{number - 1}/" if number > 2 else ""),
                "next_url": f"/page/{number + 1}/" if number < page_count else "",
            }
            local = dict(context, posts=items, pagination=pagination, meta=self._meta(None, route))
            outputs[route_to_output(route)] = index_template.render(**local)

        post_template = self.env.get_template("post.html")
        for post in self.published_posts:
            local = dict(context, post=post, page=post, post_url=post.url, meta=self._meta(post, post.url))
            outputs[post.output_path] = post_template.render(**local)

        page_template = self.env.get_template("page.html")
        for page in self.published_pages:
            local = dict(context, page=page, page_url=page.url, meta=self._meta(page, page.url))
            outputs[page.output_path] = page_template.render(**local)

        outputs["tags.html"] = self.env.get_template("tags.html").render(
            **dict(context, meta=self._meta(None, "/tags.html", title=f"Tags — {self.config.title}"))
        )
        tag_template = self.env.get_template("tag.html")
        for tag in tags:
            posts = [post for post in self.published_posts if tag["name"] in post.tags]
            outputs[route_to_output(tag["url"])] = tag_template.render(
                **dict(context, tag=tag, posts=posts, meta=self._meta(None, tag["url"], title=f"{tag['name']} — {self.config.title}"))
            )

        outputs["categories.html"] = self.env.get_template("categories.html").render(
            **dict(context, meta=self._meta(None, "/categories.html", title=f"Categories — {self.config.title}"))
        )
        category_template = self.env.get_template("category.html")
        for category in categories:
            posts = [post for post in self.published_posts if category["name"] in post.categories]
            outputs[route_to_output(category["url"])] = category_template.render(
                **dict(context, category=category, posts=posts, meta=self._meta(None, category["url"], title=f"{category['name']} — {self.config.title}"))
            )

        outputs["archive.html"] = self.env.get_template("archive.html").render(
            **dict(context, meta=self._meta(None, "/archive.html", title=f"Archive — {self.config.title}"))
        )

        if self.config.feed_enabled and self.published_posts:
            items = [
                {
                    "title": post.title,
                    "url": _absolute(self.config.url, post.url),
                    "description": post.description,
                    "summary": post.summary,
                    "html": str(post.html),
                    "date": post.date,
                    "updated": post.updated,
                    "image": _absolute(self.config.url, post.image) if post.image.startswith("/") else post.image,
                }
                for post in self.published_posts
            ]
            outputs[self.config.feed_filename] = build_rss(items, self.config)

        if self.config.sitemap_enabled and not self.config.is_placeholder_url:
            sitemap_entries = [{"url": _absolute(self.config.url, "/"), "lastmod": self.now}]
            for page in self.published_posts + self.published_pages:
                sitemap_entries.append({"url": _absolute(self.config.url, page.url), "lastmod": page.updated or page.date})
            for term in tags + categories:
                sitemap_entries.append({"url": _absolute(self.config.url, term["url"]), "lastmod": self.now})
            sitemap_entries.extend(
                {"url": _absolute(self.config.url, route), "lastmod": self.now}
                for route in ["/tags.html", "/categories.html", "/archive.html"]
            )
            for number in range(2, page_count + 1):
                sitemap_entries.append({"url": _absolute(self.config.url, f"/page/{number}/"), "lastmod": self.now})
            outputs[self.config.sitemap_filename] = build_sitemap(sitemap_entries)

        if self.config.robots_enabled and not self.config.is_placeholder_url:
            outputs[self.config.robots_filename] = build_robots(self.config)
        return outputs

    # ------------------------------------------------------------------
    # Validation and output synchronization
    # ------------------------------------------------------------------
    def _internal_link_issues(self, outputs: dict[str, str]) -> list[str]:
        available = set(outputs)
        assets_root = Path(self.project_root) / self.config.assets_dir
        if assets_root.is_dir():
            available.update(path.relative_to(assets_root).as_posix() for path in assets_root.rglob("*") if path.is_file())
        issues: list[str] = []
        pattern = re.compile(r"(?:href|src)=[\"']([^\"']+)[\"']", re.IGNORECASE)
        for output, html in outputs.items():
            for href in pattern.findall(html):
                parts = urlsplit(href)
                if parts.scheme or parts.netloc or href.startswith(("#", "mailto:", "tel:", "data:")):
                    continue
                target = parts.path
                if not target or not target.startswith("/"):
                    continue
                relative = "index.html" if target == "/" else route_to_output(target)
                if relative not in available:
                    issues.append(f"{output}: internal link '{href}' does not resolve to generated output or an asset.")
        return sorted(set(issues))

    def check(self) -> list[str]:
        """Validate the project without writing build output; return any errors."""
        try:
            outputs = self._render_outputs()
            return self._internal_link_issues(outputs)
        except (BuildError, ConfigError, ContentError) as exc:
            return [str(exc)]

    def _remove_stale_outputs(self, outputs: dict[str, str]) -> None:
        previous = set(self.manifest.get("outputs", {}))
        for relative in sorted(previous - set(outputs)):
            path = Path(self.output_dir) / relative
            if path.is_file():
                path.unlink()
                self.removed.append(str(path))

    def _write_outputs(self, outputs: dict[str, str]) -> dict[str, str]:
        previous = self.manifest.get("outputs", {})
        hashes: dict[str, str] = {}
        output_root = Path(self.output_dir)
        for relative, content in sorted(outputs.items()):
            digest = _hash_text(content)
            hashes[relative] = digest
            path = output_root / relative
            if self.incremental and previous.get(relative) == digest and path.exists():
                self.skipped.append(str(path))
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            self.generated.append(str(path))
        return hashes

    def build(self) -> dict[str, Any]:
        outputs = self._render_outputs()
        output_root = Path(self.output_dir)
        output_root.mkdir(parents=True, exist_ok=True)
        self._remove_stale_outputs(outputs)
        asset_report = sync_assets(
            self.project_root,
            self.config.assets_dir,
            self.output_dir,
            self.manifest.get("assets", {}),
        )
        self.removed.extend(asset_report["removed"])
        output_hashes = self._write_outputs(outputs)
        self._save_manifest(output_hashes, asset_report["hashes"])
        report = BuildReport(
            output_dir=self.output_dir,
            generated=self.generated,
            skipped=self.skipped,
            removed=self.removed,
            copied=asset_report["copied"],
            assets_skipped=asset_report["skipped"],
        )
        return report.as_dict()
