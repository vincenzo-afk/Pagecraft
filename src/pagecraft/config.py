"""Site configuration loading and validation for Pagecraft.

``site.yaml`` is deliberately small and forgiving for v0.1 projects.  New
v0.2 settings are optional; absent keys always fall back to stable defaults.
Configuration mistakes raise :class:`ConfigError` with a field-specific
message that is suitable for the command line and continuous integration.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml


class ConfigError(ValueError):
    """A user-facing site configuration error."""


DEFAULTS: dict[str, Any] = {
    "title": "My Pagecraft Site",
    "description": "A site generated with Pagecraft.",
    "url": "https://example.com",
    "author": "Anonymous",
    "language": "en",
    "posts_dir": "posts",
    "pages_dir": "pages",
    "assets_dir": "assets",
    "output_dir": "_site",
    "permalinks": True,
    "pagination": {"per_page": 10},
    "feed": {"enabled": True, "filename": "feed.xml", "posts_limit": 20},
    "sitemap": {"enabled": True, "filename": "sitemap.xml"},
    "robots": {"enabled": True, "filename": "robots.txt"},
    "seo": {"default_image": "", "twitter_handle": ""},
    "theme": {"mode": "auto"},
    "navigation": [],
}


def _mapping(value: Any, field_name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ConfigError(f"site.yaml: '{field_name}' must be a mapping.")
    return dict(value)


def _string(value: Any, field_name: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise ConfigError(f"site.yaml: '{field_name}' must be a string.")
    value = value.strip()
    if not allow_empty and not value:
        raise ConfigError(f"site.yaml: '{field_name}' cannot be empty.")
    return value


def _positive_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ConfigError(f"site.yaml: '{field_name}' must be a positive integer.")
    return value


def _relative_dir(value: Any, field_name: str) -> str:
    text = _string(value, field_name)
    path = Path(text)
    if path.is_absolute() or ".." in path.parts:
        raise ConfigError(f"site.yaml: '{field_name}' must be a safe relative path.")
    return path.as_posix().rstrip("/") or "."


def _merge_defaults(defaults: dict[str, Any], supplied: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge known defaults without discarding unknown top-level keys."""
    merged = dict(defaults)
    for key, value in supplied.items():
        if isinstance(defaults.get(key), dict) and isinstance(value, dict):
            merged[key] = _merge_defaults(defaults[key], value)
        else:
            merged[key] = value
    return merged


@dataclass(frozen=True)
class SiteConfig:
    title: str
    description: str
    url: str
    author: str
    language: str
    posts_dir: str
    pages_dir: str
    assets_dir: str
    output_dir: str
    permalinks: bool
    feed_enabled: bool
    feed_filename: str
    feed_posts_limit: int
    pagination_per_page: int
    sitemap_enabled: bool
    sitemap_filename: str
    robots_enabled: bool
    robots_filename: str
    seo_default_image: str
    seo_twitter_handle: str
    theme_mode: str
    navigation: list[dict[str, str]]
    extras: dict[str, Any] = field(default_factory=dict)

    @property
    def is_placeholder_url(self) -> bool:
        """Whether generated public-discovery files should be suppressed by default."""
        host = urlparse(self.url).netloc.lower()
        return not host or host in {"example.com", "www.example.com"}

    @property
    def feed_url(self) -> str:
        return f"{self.url}/{self.feed_filename.lstrip('/')}"

    @property
    def sitemap_url(self) -> str:
        return f"{self.url}/{self.sitemap_filename.lstrip('/')}"

    @classmethod
    def load(cls, project_root: str) -> "SiteConfig":
        path = Path(project_root) / "site.yaml"
        raw: dict[str, Any] = {}
        if path.exists():
            try:
                loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
            except yaml.YAMLError as exc:
                raise ConfigError(f"site.yaml: invalid YAML ({exc}).") from exc
            if loaded is not None and not isinstance(loaded, dict):
                raise ConfigError("site.yaml: root value must be a mapping.")
            raw = dict(loaded or {})

        merged = _merge_defaults(DEFAULTS, raw)
        url = _string(merged["url"], "url").rstrip("/")
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ConfigError("site.yaml: 'url' must be an absolute http(s) URL.")

        feed = _mapping(merged["feed"], "feed")
        sitemap = _mapping(merged["sitemap"], "sitemap")
        robots = _mapping(merged["robots"], "robots")
        pagination = _mapping(merged["pagination"], "pagination")
        seo = _mapping(merged["seo"], "seo")
        theme = _mapping(merged["theme"], "theme")

        mode = _string(theme.get("mode", "auto"), "theme.mode")
        if mode not in {"auto", "light", "dark"}:
            raise ConfigError("site.yaml: 'theme.mode' must be auto, light, or dark.")

        raw_navigation = merged.get("navigation", [])
        if not isinstance(raw_navigation, list):
            raise ConfigError("site.yaml: 'navigation' must be a list of label/url mappings.")
        navigation: list[dict[str, str]] = []
        for index, item in enumerate(raw_navigation):
            if not isinstance(item, dict):
                raise ConfigError(f"site.yaml: navigation item {index + 1} must be a mapping.")
            label = _string(item.get("label", ""), f"navigation[{index}].label")
            href = _string(item.get("url", ""), f"navigation[{index}].url")
            navigation.append({"label": label, "url": href})

        known = set(DEFAULTS)
        return cls(
            title=_string(merged["title"], "title"),
            description=_string(merged["description"], "description", allow_empty=True),
            url=url,
            author=_string(merged["author"], "author", allow_empty=True),
            language=_string(merged["language"], "language"),
            posts_dir=_relative_dir(merged["posts_dir"], "posts_dir"),
            pages_dir=_relative_dir(merged["pages_dir"], "pages_dir"),
            assets_dir=_relative_dir(merged["assets_dir"], "assets_dir"),
            output_dir=_relative_dir(merged["output_dir"], "output_dir"),
            permalinks=bool(merged["permalinks"]),
            feed_enabled=bool(feed.get("enabled", True)),
            feed_filename=_relative_dir(feed.get("filename", "feed.xml"), "feed.filename"),
            feed_posts_limit=_positive_int(feed.get("posts_limit", 20), "feed.posts_limit"),
            pagination_per_page=_positive_int(pagination.get("per_page", 10), "pagination.per_page"),
            sitemap_enabled=bool(sitemap.get("enabled", True)),
            sitemap_filename=_relative_dir(sitemap.get("filename", "sitemap.xml"), "sitemap.filename"),
            robots_enabled=bool(robots.get("enabled", True)),
            robots_filename=_relative_dir(robots.get("filename", "robots.txt"), "robots.filename"),
            seo_default_image=_string(seo.get("default_image", ""), "seo.default_image", allow_empty=True),
            seo_twitter_handle=_string(seo.get("twitter_handle", ""), "seo.twitter_handle", allow_empty=True),
            theme_mode=mode,
            navigation=navigation,
            extras={key: value for key, value in raw.items() if key not in known},
        )
