"""Unit tests for Pagecraft's core features."""

import os
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pagecraft.builder import Builder, Page  # noqa: E402
from pagecraft.config import SiteConfig  # noqa: E402
from pagecraft.renderer import highlight_code, render_markdown  # noqa: E402
from pagecraft.rss import build_rss  # noqa: E402

EXAMPLE = os.path.join(ROOT, "example")
SITE = os.path.join(EXAMPLE, "_site")


@pytest.fixture(autouse=True)
def clean_output():
    """Isolate every test: clear generated files and restore example sources."""
    source_snapshots = {}
    for directory in ("posts", "pages"):
        root = os.path.join(EXAMPLE, directory)
        for current_root, _, filenames in os.walk(root):
            for filename in filenames:
                path = os.path.join(current_root, filename)
                source_snapshots[path] = open(path, "rb").read()

    for path in (SITE, os.path.join(EXAMPLE, ".pagecraft")):
        if os.path.isdir(path):
            shutil.rmtree(path)
    yield
    for path in (SITE, os.path.join(EXAMPLE, ".pagecraft")):
        if os.path.isdir(path):
            shutil.rmtree(path)
    for path, content in source_snapshots.items():
        with open(path, "wb") as fh:
            fh.write(content)


class TestConfig:
    def test_load_defaults(self, tmp_path):
        config = SiteConfig.load(str(tmp_path))
        assert config.title == "My Pagecraft Site"
        assert config.feed_enabled is True

    def test_load_custom_yaml(self, tmp_path):
        (tmp_path / "site.yaml").write_text("title: Custom\nurl: https://x.com\n")
        config = SiteConfig.load(str(tmp_path))
        assert config.title == "Custom"
        assert config.url == "https://x.com"


class TestRenderer:
    def test_markdown_basic(self):
        assert "<strong>bold</strong>" in render_markdown("**bold**")
        assert "<h1 id" in render_markdown("# Heading")

    def test_syntax_highlighting(self):
        html = str(highlight_code('print("hi")\n', "python"))
        assert "highlight" in html
        assert "print" in html

    def test_unknown_language_fallback(self):
        html = str(highlight_code("hello", "not-a-language"))
        assert "highlight" in html

    def test_code_fence_rendered(self):
        md = "```python\nx = 1\n```\n"
        html = render_markdown(md)
        assert "highlight" in html
        assert "<pre>" in html


class TestBuilder:
    def test_full_build(self):
        builder = Builder(EXAMPLE)
        result = builder.build()
        assert result["posts_built"] > 0
        assert os.path.exists(os.path.join(SITE, "index.html"))
        assert os.path.exists(os.path.join(SITE, "hello-pagecraft.html"))
        assert os.path.exists(os.path.join(SITE, "about.html"))
        assert os.path.exists(os.path.join(SITE, "tags.html"))
        assert os.path.exists(os.path.join(SITE, "tag-static-sites.html"))
        assert os.path.exists(os.path.join(SITE, "feed.xml"))
        assert os.path.exists(os.path.join(SITE, "style.css"))
        # Asset copied verbatim from assets/
        assert os.path.exists(os.path.join(SITE, "theme.css"))

    def test_incremental_skips_unchanged(self):
        builder = Builder(EXAMPLE)
        builder.build()
        builder2 = Builder(EXAMPLE)
        result = builder2.build()
        # Everything unchanged on a second build.
        assert result["files_skipped"] > 0

    def test_single_post_change(self):
        Builder(EXAMPLE).build()
        target = os.path.join(EXAMPLE, "posts", "hello-pagecraft.md")
        with open(target, "a", encoding="utf-8") as fh:
            fh.write("\nA new sentence for testing.\n")
        result = Builder(EXAMPLE).build()
        # The changed post plus index, feed, and tag pages rebuild; the other
        # post's HTML is skipped.
        assert result["files_skipped"] > 0
        with open(os.path.join(SITE, "hello-pagecraft.html"), encoding="utf-8") as fh:
            assert "A new sentence for testing." in fh.read()
        with open(os.path.join(SITE, "incremental-builds.html"), encoding="utf-8") as fh:
            assert "A new sentence for testing." not in fh.read()

    def test_template_change_forces_full_rebuild(self):
        Builder(EXAMPLE).build()
        tpl = os.path.join(ROOT, "templates", "base.html")
        with open(tpl, "a", encoding="utf-8") as fh:
            fh.write("<!-- marker -->\n")
        try:
            result = Builder(EXAMPLE).build()
            assert result["posts_built"] > 0
        finally:
            with open(tpl, "r", encoding="utf-8") as fh:
                content = fh.read()
            with open(tpl, "w", encoding="utf-8") as fh:
                fh.write(content.replace("<!-- marker -->\n", ""))

    def test_asset_copying(self, tmp_path):
        project = str(tmp_path / "proj")
        os.makedirs(os.path.join(project, "assets", "img"))
        open(os.path.join(project, "assets", "img", "logo.png"), "w").close()
        result = Builder(project).build()
        assert result["assets_copied"] == 1
        assert os.path.exists(os.path.join(project, "_site", "img", "logo.png"))


class TestRSS:
    def test_feed_xml_valid(self):
        config = SiteConfig.load(EXAMPLE)
        builder = Builder(EXAMPLE)
        builder.build()
        items = [
            {"title": p.title, "url": config.url + builder._post_url(p),
             "description": p.description, "html": p.html, "date": p.date}
            for p in builder.posts
        ]
        assert items, "example site must contain posts"
        xml = build_rss(items, config)
        assert xml.startswith('<?xml version="1.0"')
        assert "<rss version" in xml
        assert "<item>" in xml
        assert "<generator>Pagecraft</generator>" in xml


class TestCLI:
    def test_build_command(self):
        out = subprocess.run(
            [sys.executable, "-m", "pagecraft.cli", "build", "--project", EXAMPLE],
            cwd=ROOT, capture_output=True, text=True, env={**os.environ, "PYTHONPATH": os.path.join(ROOT, "src")},
        )
        assert out.returncode == 0
        assert "Pagecraft built" in out.stdout

    def test_clean_command(self):
        subprocess.run(
            [sys.executable, "-m", "pagecraft.cli", "build", "--project", EXAMPLE],
            cwd=ROOT, capture_output=True, text=True, env={**os.environ, "PYTHONPATH": os.path.join(ROOT, "src")},
        )
        out = subprocess.run(
            [sys.executable, "-m", "pagecraft.cli", "clean", "--project", EXAMPLE],
            cwd=ROOT, capture_output=True, text=True, env={**os.environ, "PYTHONPATH": os.path.join(ROOT, "src")},
        )
        assert out.returncode == 0
        assert not os.path.isdir(SITE)
