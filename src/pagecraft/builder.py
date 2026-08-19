"""Core build pipeline for Pagecraft with incremental build support.

Pagecraft tracks file modification times and content hashes in a
``.pagecraft/manifest.json`` cache. On each build it regenerates only
the posts, pages, index, tag pages, and RSS feed whose inputs changed,
reusing everything else. A full build is performed when the cache is
missing, the layout templates changed, or ``--full`` is requested.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import datetime
from pathlib import Path

import frontmatter
from jinja2 import Environment

from .assets import copy_assets
from .config import SiteConfig
from .renderer import generate_stylesheet, render_markdown
from .rss import build_rss
from .templates import make_environment


def _content_hash(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _slugify(text: str) -> str:
    import re
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "untitled"


class Page:
    """A single post or page loaded from a Markdown file with front matter."""

    def __init__(self, path: str, project_root: str, kind: str):
        self.path = path
        self.kind = kind  # "post" or "page"
        meta = frontmatter.load(path)
        self.metadata = meta.metadata or {}
        self.raw = meta.content
        self.title = self.metadata.get("title", Path(path).stem.replace("-", " ").title())
        self.slug = self.metadata.get("slug") or _slugify(Path(path).stem)
        raw_date = self.metadata.get("date")
        if isinstance(raw_date, datetime):
            self.date = raw_date
        else:
            self.date = datetime.fromtimestamp(os.path.getmtime(path))
        self.tags = [str(t).strip() for t in (self.metadata.get("tags") or [])]
        self.description = self.metadata.get("description", "")
        self.html = render_markdown(self.raw)


class Builder:
    def __init__(self, project_root: str, incremental: bool = True):
        self.project_root = os.path.abspath(project_root)
        self.config = SiteConfig.load(self.project_root)
        self.env: Environment = make_environment(self.project_root)
        self.incremental = incremental
        self.manifest_path = os.path.join(self.project_root, ".pagecraft", "manifest.json")
        self.manifest = self._load_manifest()
        self.output_dir = os.path.join(self.project_root, self.config.output_dir)
        self.posts: list[Page] = []
        self.pages: list[Page] = []
        self.changed: list[str] = []
        self.skipped: list[str] = []
        self.new_manifest: dict = {"hashes": {}, "built_at": ""}

    # ------------------------------------------------------------------ #
    # Manifest (incremental cache) handling
    # ------------------------------------------------------------------ #
    def _load_manifest(self) -> dict:
        if not self.incremental or not os.path.exists(self.manifest_path):
            return {"hashes": {}, "built_at": ""}
        try:
            with open(self.manifest_path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (json.JSONDecodeError, OSError):
            return {"hashes": {}, "built_at": ""}

    def _save_manifest(self) -> None:
        os.makedirs(os.path.dirname(self.manifest_path), exist_ok=True)
        with open(self.manifest_path, "w", encoding="utf-8") as fh:
            json.dump(self.new_manifest, fh, indent=2, default=str)

    def _templates_changed(self) -> bool:
        templates_dir = os.path.join(self.project_root, "templates")
        if not os.path.isdir(templates_dir):
            return False
        for dirpath, _, filenames in os.walk(templates_dir):
            for name in filenames:
                path = os.path.join(dirpath, name)
                if self.new_manifest["hashes"].get(path) != _content_hash(path):
                    return True
        return False

    def _content_changed(self, page: Page) -> bool:
        old = self.manifest.get("hashes", {}).get(page.path)
        return old != _content_hash(page.path)

    # ------------------------------------------------------------------ #
    # Collection
    # ------------------------------------------------------------------ #
    def _collect_pages(self, directory: str, kind: str) -> list[Page]:
        root = os.path.join(self.project_root, directory)
        pages: list[Page] = []
        if not os.path.isdir(root):
            return pages
        for dirpath, _, filenames in os.walk(root):
            for name in sorted(filenames):
                if not name.endswith((".md", ".markdown")):
                    continue
                pages.append(Page(os.path.join(dirpath, name), self.project_root, kind))
        pages.sort(key=lambda p: p.date, reverse=True)
        return pages

    def _post_url(self, page: Page) -> str:
        if self.config.permalinks:
            return f"/{page.slug}.html"
        return f"/{page.kind}s/{page.slug}.html"

    def _page_url(self, page: Page) -> str:
        return f"/{page.slug}.html"

    # ------------------------------------------------------------------ #
    # Build
    # ------------------------------------------------------------------ #
    def build(self) -> dict:
        os.makedirs(self.output_dir, exist_ok=True)

        # Regenerate theme CSS when the manifest is empty (new build).
        stylesheet_path = os.path.join(self.output_dir, "style.css")
        if not os.path.exists(stylesheet_path) or not self.manifest.get("hashes"):
            with open(stylesheet_path, "w", encoding="utf-8") as fh:
                fh.write(generate_stylesheet())

        self.posts = self._collect_pages(self.config.posts_dir, "post")
        self.pages = self._collect_pages(self.config.pages_dir, "page")

        full_rebuild = (
            not self.incremental
            or not self.manifest.get("hashes")
            or self._templates_changed()
        )

        self._build_index(full_rebuild)
        self._build_posts(full_rebuild)
        self._build_pages(full_rebuild)
        self._build_tags(full_rebuild)
        self._build_feed(full_rebuild)

        copied = copy_assets(self.project_root, self.config.assets_dir, self.output_dir)

        self.new_manifest["built_at"] = str(datetime.now())
        self._save_manifest()

        return {
            "output_dir": self.output_dir,
            "posts_built": len(self.changed),
            "files_skipped": len(self.skipped),
            "assets_copied": len(copied),
            "feed_generated": True,
        }

    # ------------------------------------------------------------------ #
    # Individual outputs
    # ------------------------------------------------------------------ #
    def _write(self, relative_path: str, content: str, *, force: bool = False) -> None:
        path = os.path.join(self.output_dir, relative_path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.new_manifest["hashes"][path] = hashlib.sha256(content.encode()).hexdigest()
        old_hash = self.manifest.get("hashes", {}).get(path)
        if not force and old_hash == self.new_manifest["hashes"][path]:
            self.skipped.append(path)
            return
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        self.changed.append(path)

    def _base_context(self) -> dict:
        from .templates import site_context
        ctx = site_context(self.project_root)
        ctx["posts"] = self.posts
        ctx["pages"] = self.pages
        return ctx

    def _build_index(self, full: bool) -> None:
        ctx = self._base_context()
        html = self.env.get_template("index.html").render(**ctx)
        self._write("index.html", html, force=full)

    def _build_posts(self, full: bool) -> None:
        template = self.env.get_template("post.html")
        for post in self.posts:
            changed = full or self._content_changed(post)
            if not changed:
                self.skipped.append(self._post_url(post))
                continue
            ctx = self._base_context()
            ctx.update(post=post, post_url=self._post_url(post))
            html = template.render(**ctx)
            self._write(self._post_url(post).lstrip("/"), html)

    def _build_pages(self, full: bool) -> None:
        template = self.env.get_template("page.html")
        for page in self.pages:
            changed = full or self._content_changed(page)
            if not changed:
                self.skipped.append(self._page_url(page))
                continue
            ctx = self._base_context()
            ctx.update(page=page, page_url=self._page_url(page))
            html = template.render(**ctx)
            self._write(self._page_url(page).lstrip("/"), html)

    def _build_tags(self, full: bool) -> None:
        all_tags = sorted({tag for post in self.posts for tag in post.tags})
        tags_index = self.env.get_template("tags.html").render(
            **self._base_context(), tags=all_tags
        )
        self._write("tags.html", tags_index, force=full)

        tag_template = self.env.get_template("tag.html")
        for tag in all_tags:
            posts = [p for p in self.posts if tag in p.tags]
            ctx = self._base_context()
            ctx.update(tag=tag, posts=posts)
            html = tag_template.render(**ctx)
            # Tag pages are cheap to regenerate; only skip on full cache hits.
            if not full and self.manifest.get("hashes", {}).get(os.path.join(self.output_dir, f"tag-{tag}.html")):
                self.skipped.append(f"tag-{tag}.html")
                continue
            self._write(f"tag-{tag}.html", html)

    def _build_feed(self, full: bool) -> None:
        if not self.config.feed_enabled or not self.posts:
            return
        items = [
            {
                "title": post.title,
                "url": self.config.url + self._post_url(post),
                "description": post.description,
                "html": post.html,
                "date": post.date,
            }
            for post in self.posts
        ]
        xml = build_rss(items, self.config)
        self._write(self.config.feed_filename, xml, force=full)
