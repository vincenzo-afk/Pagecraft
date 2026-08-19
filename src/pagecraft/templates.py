"""Jinja environment and shared template context for Pagecraft."""
from __future__ import annotations

from pathlib import Path

from jinja2 import ChoiceLoader, Environment, FileSystemLoader, select_autoescape

from .config import SiteConfig
from .content import slugify


PACKAGE_ROOT = Path(__file__).resolve().parent
BUILTIN_TEMPLATES = PACKAGE_ROOT / "resources" / "templates"
TEMPLATE_NAMES = (
    "base.html", "page.html", "post.html", "index.html", "tags.html", "tag.html",
    "categories.html", "category.html", "archive.html", "postcard.html",
)


def make_environment(project_root: str, templates_dir: str | None = None) -> Environment:
    """Create Jinja environment with project templates taking precedence."""
    loaders = []
    if templates_dir:
        loaders.append(FileSystemLoader(templates_dir, encoding="utf-8"))
    project_templates = Path(project_root) / "templates"
    if project_templates.is_dir():
        loaders.append(FileSystemLoader(str(project_templates), encoding="utf-8"))
    loaders.append(FileSystemLoader(str(BUILTIN_TEMPLATES), encoding="utf-8"))
    env = Environment(
        loader=ChoiceLoader(loaders),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    env.filters["date"] = lambda value, fmt="%B %d, %Y": value.strftime(fmt)
    env.filters["term_slug"] = slugify
    env.globals.update(site=site_context(project_root))
    return env


def site_context(project_root: str) -> dict:
    """Return stable global template data for a project."""
    config = SiteConfig.load(project_root)
    navigation = config.navigation or [
        {"label": "Home", "url": "/"},
        {"label": "Tags", "url": "/tags.html"},
        {"label": "Categories", "url": "/categories.html"},
        {"label": "Archive", "url": "/archive.html"},
    ]
    return {
        "title": config.title,
        "description": config.description,
        "url": config.url,
        "author": config.author,
        "language": config.language,
        "feed_url": config.feed_url if config.feed_enabled else "",
        "sitemap_url": config.sitemap_url if config.sitemap_enabled and not config.is_placeholder_url else "",
        "theme_mode": config.theme_mode,
        "default_image": config.seo_default_image,
        "twitter_handle": config.seo_twitter_handle,
        "navigation": navigation,
    }
