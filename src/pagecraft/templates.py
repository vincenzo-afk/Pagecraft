"""Layout and template handling for Pagecraft.

Pagecraft ships a set of default Jinja2 layouts (base, page, post, index,
tags, tag page) and lets projects override any of them by placing a
``templates/`` directory at the project root. Templates extend one
another through Jinja2's ``{% extends %}`` inheritance.
"""

from __future__ import annotations

import os

from jinja2 import Environment, FileSystemLoader

TEMPLATE_NAMES = ("base.html", "page.html", "post.html", "index.html",
                  "tags.html", "tag.html", "postcard.html")


DEFAULT_TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "templates")


def make_environment(project_root: str, templates_dir: str | None = None) -> Environment:
    """Create the Jinja2 environment with the project's overrides taking precedence.

    The built-in Pagecraft templates are always available as a fallback, so
    projects work even without a local ``templates/`` directory.
    """
    search_paths = [os.path.join(project_root, "templates"), DEFAULT_TEMPLATES_DIR]
    if templates_dir:
        search_paths.insert(0, templates_dir)
    env = Environment(
        loader=FileSystemLoader(search_paths, encoding="utf-8"),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    env.globals.update(site=site_context(project_root))
    return env


def site_context(project_root: str) -> dict:
    """Lazy site metadata for templates; filled in by the builder at build time."""
    from .config import SiteConfig

    config = SiteConfig.load(project_root)
    return {
        "title": config.title,
        "description": config.description,
        "url": config.url,
        "author": config.author,
        "feed_url": config.url + "/" + config.feed_filename if config.feed_enabled else "",
    }
