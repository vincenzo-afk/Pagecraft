"""Site configuration loading for Pagecraft.

Pagecraft reads a ``site.yaml`` file in the project root. All keys are
optional and fall back to sensible defaults so a brand-new project works
out of the box.
"""

from __future__ import annotations

import yaml
from dataclasses import dataclass, field

DEFAULTS = {
    "title": "My Pagecraft Site",
    "description": "A site generated with Pagecraft.",
    "url": "https://example.com",
    "author": "Anonymous",
    "posts_dir": "posts",
    "pages_dir": "pages",
    "assets_dir": "assets",
    "output_dir": "_site",
    "feed": {"enabled": True, "filename": "feed.xml", "posts_limit": 20},
    "permalinks": True,
}


@dataclass
class SiteConfig:
    title: str
    description: str
    url: str
    author: str
    posts_dir: str
    pages_dir: str
    assets_dir: str
    output_dir: str
    permalinks: bool
    feed_enabled: bool
    feed_filename: str
    feed_posts_limit: int
    extras: dict = field(default_factory=dict)

    @classmethod
    def load(cls, project_root: str) -> "SiteConfig":
        import os

        path = os.path.join(project_root, "site.yaml")
        raw = {}
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as fh:
                loaded = yaml.safe_load(fh) or {}
                raw = loaded if isinstance(loaded, dict) else {}
        for key, value in DEFAULTS.items():
            raw.setdefault(key, value)
        feed_cfg = raw.pop("feed") or {}
        return cls(
            title=raw["title"],
            description=raw["description"],
            url=raw["url"].rstrip("/"),
            author=raw["author"],
            posts_dir=raw["posts_dir"],
            pages_dir=raw["pages_dir"],
            assets_dir=raw["assets_dir"],
            output_dir=raw["output_dir"],
            permalinks=bool(raw["permalinks"]),
            feed_enabled=bool(feed_cfg.get("enabled", True)),
            feed_filename=feed_cfg.get("filename", "feed.xml"),
            feed_posts_limit=int(feed_cfg.get("posts_limit", 20)),
            extras=raw,
        )
