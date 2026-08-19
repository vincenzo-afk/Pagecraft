"""Regression coverage for Pagecraft's public v0.2 behavior."""
from __future__ import annotations

from datetime import datetime
import filecmp
import json
from pathlib import Path
import subprocess
import textwrap
import sys
import xml.etree.ElementTree as ET

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pagecraft.builder import BuildError, Builder  # noqa: E402
from pagecraft.config import ConfigError, SiteConfig  # noqa: E402
from pagecraft.content import ContentError, route_to_output, slugify  # noqa: E402
from pagecraft.renderer import highlight_code, render_markdown  # noqa: E402


def write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")
    return path


def make_site(tmp_path: Path, *, per_page: int = 2) -> Path:
    write(
        tmp_path / "site.yaml",
        f"""
        title: Test Journal
        description: A small test site.
        url: https://journal.example
        language: en
        author: Test Author
        pagination:
          per_page: {per_page}
        feed:
          enabled: true
          filename: feed.xml
          posts_limit: 20
        sitemap:
          enabled: true
          filename: sitemap.xml
        robots:
          enabled: true
          filename: robots.txt
        navigation:
          - label: Home
            url: /
          - label: Archive
            url: /archive.html
        """,
    )
    write(
        tmp_path / "posts" / "first.md",
        """
        ---
        title: First post
        date: 2026-08-10
        categories: [Writing]
        tags: [notes, pagecraft]
        description: First description.
        ---
        # First post
        A short first post.
        """,
    )
    write(
        tmp_path / "posts" / "second.md",
        """
        ---
        title: Second post
        date: 2026-08-11
        categories: [Tooling]
        tags: [pagecraft, code]
        summary: A concise summary.
        ---
        # Second post
        ```python
        answer = 42
        ```
        """,
    )
    write(
        tmp_path / "posts" / "third.md",
        """
        ---
        title: Third post
        date: 2026-08-12
        categories: [Writing]
        tags: [notes]
        ---
        # Third post
        Another entry.
        """,
    )
    write(
        tmp_path / "pages" / "about.md",
        """
        ---
        title: About
        description: About this site.
        ---
        # About
        A page.
        """,
    )
    return tmp_path


class TestConfigAndContent:
    def test_defaults_are_useful_for_a_new_directory(self, tmp_path):
        config = SiteConfig.load(str(tmp_path))
        assert config.title == "My Pagecraft Site"
        assert config.pagination_per_page == 10
        assert config.feed_enabled is True

    def test_nested_v02_settings_are_loaded(self, tmp_path):
        write(tmp_path / "site.yaml", "title: Custom\nurl: https://custom.example/\npagination:\n  per_page: 5\ntheme:\n  mode: dark\n")
        config = SiteConfig.load(str(tmp_path))
        assert config.url == "https://custom.example"
        assert config.pagination_per_page == 5
        assert config.theme_mode == "dark"

    def test_invalid_theme_and_pagination_are_rejected(self, tmp_path):
        write(tmp_path / "site.yaml", "theme:\n  mode: neon\npagination:\n  per_page: 0\n")
        with pytest.raises(ConfigError):
            SiteConfig.load(str(tmp_path))

    def test_slug_and_routes_are_safe_and_predictable(self):
        assert slugify("A Useful, Human Title!") == "a-useful-human-title"
        assert route_to_output("/") == "index.html"
        assert route_to_output("/page/2/") == "page/2/index.html"
        with pytest.raises(ContentError):
            route_to_output("/../private.html")


class TestRenderer:
    def test_markdown_has_heading_ids_and_highlighting(self):
        html = render_markdown("# A heading\n\n```python\nprint('hi')\n```\n")
        assert '<h1 id="a-heading">' in html
        assert "highlight" in html
        assert "print" in html

    def test_unknown_code_language_falls_back_gracefully(self):
        assert "highlight" in str(highlight_code("plain text", "not-a-real-language"))


class TestPublishingBuild:
    def test_complete_build_generates_collections_discovery_and_pagination(self, tmp_path):
        site = make_site(tmp_path)
        report = Builder(str(site), now=datetime(2026, 8, 19)).build()
        output = site / "_site"
        expected = {
            "index.html", "page/2/index.html", "first.html", "second.html", "third.html", "about.html",
            "tags.html", "tag-notes.html", "categories.html", "category-writing.html", "archive.html",
            "feed.xml", "sitemap.xml", "robots.txt", "style.css",
        }
        actual = {str(path.relative_to(output)) for path in output.rglob("*") if path.is_file()}
        assert expected <= actual
        assert report["posts_built"] >= len(expected)
        index = (output / "index.html").read_text(encoding="utf-8")
        assert "Third post" in index and "Second post" in index
        assert "First post" not in index  # it belongs on page 2
        assert "canonical" in (output / "second.html").read_text(encoding="utf-8")
        assert "sitemap.xml" in (output / "robots.txt").read_text(encoding="utf-8")
        ET.parse(output / "feed.xml")
        ET.parse(output / "sitemap.xml")

    def test_drafts_and_future_posts_are_excluded_unless_previewed(self, tmp_path):
        site = make_site(tmp_path)
        write(site / "posts" / "draft.md", "---\ntitle: Draft\ndate: 2026-08-10\ndraft: true\n---\nDraft body.")
        write(site / "posts" / "future.md", "---\ntitle: Future\ndate: 2026-09-01\n---\nFuture body.")
        Builder(str(site), now=datetime(2026, 8, 19)).build()
        assert not (site / "_site" / "draft.html").exists()
        assert not (site / "_site" / "future.html").exists()
        Builder(str(site), include_drafts=True, include_future=True, now=datetime(2026, 8, 19)).build()
        assert (site / "_site" / "draft.html").exists()
        assert (site / "_site" / "future.html").exists()
        assert "Preview" in (site / "_site" / "draft.html").read_text(encoding="utf-8")

    def test_permalink_and_route_collisions_are_handled(self, tmp_path):
        site = make_site(tmp_path)
        write(site / "posts" / "custom.md", "---\ntitle: Custom\ndate: 2026-08-13\npermalink: /custom/path/\n---\nHello")
        Builder(str(site), now=datetime(2026, 8, 19)).build()
        assert (site / "_site" / "custom" / "path" / "index.html").exists()
        write(site / "pages" / "collision.md", "---\ntitle: Collision\npermalink: /tags.html\n---\nNope")
        with pytest.raises(BuildError, match="Route collision"):
            Builder(str(site), now=datetime(2026, 8, 19)).build()

    def test_check_reports_valid_site_without_writing_output(self, tmp_path):
        site = make_site(tmp_path)
        builder = Builder(str(site), now=datetime(2026, 8, 19))
        assert builder.check() == []
        assert not (site / "_site").exists()


class TestIncrementalAndAssets:
    def test_second_build_skips_content_and_changed_source_updates_dependents(self, tmp_path):
        site = make_site(tmp_path)
        Builder(str(site), now=datetime(2026, 8, 19)).build()
        unchanged = Builder(str(site), now=datetime(2026, 8, 19)).build()
        assert unchanged["files_skipped"] > 0
        post = site / "posts" / "first.md"
        post.write_text(post.read_text(encoding="utf-8") + "\nA new sentence.\n", encoding="utf-8")
        changed = Builder(str(site), now=datetime(2026, 8, 19)).build()
        assert changed["files_skipped"] > 0
        assert "A new sentence." in (site / "_site" / "first.html").read_text(encoding="utf-8")
        assert (site / "_site" / "index.html").exists()

    def test_deleting_content_and_assets_removes_stale_output(self, tmp_path):
        site = make_site(tmp_path)
        write(site / "assets" / "images" / "mark.txt", "asset")
        Builder(str(site), now=datetime(2026, 8, 19)).build()
        (site / "posts" / "third.md").unlink()
        (site / "assets" / "images" / "mark.txt").unlink()
        report = Builder(str(site), now=datetime(2026, 8, 19)).build()
        assert not (site / "_site" / "third.html").exists()
        assert not (site / "_site" / "images" / "mark.txt").exists()
        assert any("third.html" in item for item in report["removed"])

    def test_manifest_has_a_versioned_schema(self, tmp_path):
        site = make_site(tmp_path)
        Builder(str(site), now=datetime(2026, 8, 19)).build()
        manifest = json.loads((site / ".pagecraft" / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["schema"] == 2
        assert manifest["outputs"]


class TestBundledResources:
    def test_packaged_templates_and_theme_match_source_copies(self):
        source_templates = ROOT / "templates"
        packaged_templates = ROOT / "src" / "pagecraft" / "resources" / "templates"
        assert not filecmp.dircmp(source_templates, packaged_templates).diff_files
        assert not filecmp.dircmp(source_templates, packaged_templates).left_only
        assert not filecmp.dircmp(source_templates, packaged_templates).right_only
        assert filecmp.cmp(
            ROOT / "static" / "theme.css",
            ROOT / "src" / "pagecraft" / "resources" / "static" / "theme.css",
            shallow=False,
        )


class TestCLI:
    def run_cli(self, *args: str, cwd: Path = ROOT):
        return subprocess.run(
            [sys.executable, "-m", "pagecraft.cli", *args], cwd=cwd, capture_output=True, text=True,
            env={**__import__("os").environ, "PYTHONPATH": str(ROOT / "src")}, check=False,
        )

    def test_init_new_post_build_check_and_clean(self, tmp_path):
        project = tmp_path / "journal"
        assert self.run_cli("init", str(project)).returncode == 0
        created = self.run_cli("new-post", "Release Notes", "--project", str(project), "--draft", "--tag", "v02")
        assert created.returncode == 0
        assert any(path.name.endswith("release-notes.md") for path in (project / "posts").iterdir())
        assert self.run_cli("check", "--project", str(project)).returncode == 0
        preview = self.run_cli("build", "--project", str(project), "--drafts", "--json")
        assert preview.returncode == 0
        payload = json.loads(preview.stdout)
        assert payload["generated"]
        assert self.run_cli("clean", "--project", str(project)).returncode == 0
        assert not (project / "_site").exists()

    def test_cli_reports_bad_configuration(self, tmp_path):
        write(tmp_path / "site.yaml", "pagination:\n  per_page: 0\n")
        result = self.run_cli("build", "--project", str(tmp_path))
        assert result.returncode == 1
        assert "error:" in result.stderr
