"""Content primitives used by Pagecraft's collection and build pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
from pathlib import PurePosixPath
import os
import re
from typing import Any

import frontmatter


class ContentError(ValueError):
    """A user-facing Markdown/front-matter error."""


def slugify(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower().strip()).strip("-")
    return value or "untitled"


def normalise_terms(value: Any, field_name: str, source: str) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        raise ContentError(f"{source}: '{field_name}' must be a list or string.")
    terms: list[str] = []
    seen: set[str] = set()
    for term in value:
        if not isinstance(term, str) or not term.strip():
            raise ContentError(f"{source}: '{field_name}' entries must be non-empty strings.")
        clean = term.strip()
        key = clean.lower()
        if key not in seen:
            terms.append(clean)
            seen.add(key)
    return terms


def coerce_datetime(value: Any, source: str) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    if isinstance(value, date):
        return datetime.combine(value, time.min)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError as exc:
            raise ContentError(f"{source}: 'date' must use ISO-8601 format.") from exc
    raise ContentError(f"{source}: 'date' must use ISO-8601 format.")


def route_to_output(url: str) -> str:
    """Turn a validated public URL path into a safe relative output path."""
    if not url.startswith("/"):
        raise ContentError("Routes must begin with '/'.")
    if url == "/":
        return "index.html"
    path = PurePosixPath(url.lstrip("/"))
    if path.is_absolute() or ".." in path.parts or str(path) in {".", ""}:
        raise ContentError(f"Unsafe route: {url}")
    rendered = path.as_posix()
    if url.endswith("/"):
        return f"{rendered}/index.html"
    return rendered


def normalise_permalink(value: Any, source: str) -> str | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise ContentError(f"{source}: 'permalink' must be a string.")
    value = value.strip()
    if not value.startswith("/") or "//" in value or ".." in PurePosixPath(value).parts:
        raise ContentError(f"{source}: 'permalink' must be a safe absolute site path.")
    if value == "/":
        raise ContentError(f"{source}: 'permalink' cannot replace the home page.")
    if value.endswith("/") or value.endswith(".html"):
        route_to_output(value)
        return value
    value = f"{value}.html"
    route_to_output(value)
    return value


def reading_time_minutes(markdown: str) -> int:
    words = len(re.findall(r"\b[\w'-]+\b", markdown))
    return max(1, round(words / 220))


@dataclass
class Page:
    """A Markdown post or standalone page with normalized public metadata."""

    path: str
    kind: str
    title: str
    slug: str
    raw: str
    metadata: dict[str, Any]
    date: datetime
    updated: datetime | None
    tags: list[str]
    categories: list[str]
    description: str
    summary: str
    image: str
    canonical_url: str
    permalink: str | None
    draft: bool
    reading_time: int
    html: str = ""
    url: str = ""
    output_path: str = ""
    is_preview: bool = False

    @classmethod
    def load(cls, path: str, kind: str) -> "Page":
        try:
            document = frontmatter.load(path)
        except Exception as exc:  # pragma: no cover - library errors are normalized
            raise ContentError(f"{path}: could not parse front matter ({exc}).") from exc
        meta = dict(document.metadata or {})
        source = os.path.relpath(path)
        title = meta.get("title") or os.path.splitext(os.path.basename(path))[0].replace("-", " ").title()
        if not isinstance(title, str) or not title.strip():
            raise ContentError(f"{source}: 'title' must be a non-empty string.")
        slug_value = meta.get("slug") or os.path.splitext(os.path.basename(path))[0]
        if not isinstance(slug_value, str):
            raise ContentError(f"{source}: 'slug' must be a string.")
        description = meta.get("description", "")
        summary = meta.get("summary", description)
        image = meta.get("image", "")
        canonical_url = meta.get("canonical_url", "")
        for label, value in (("description", description), ("summary", summary), ("image", image), ("canonical_url", canonical_url)):
            if not isinstance(value, str):
                raise ContentError(f"{source}: '{label}' must be a string.")
        raw_date = coerce_datetime(meta.get("date"), source)
        date_value = raw_date or datetime.fromtimestamp(os.path.getmtime(path))
        updated_value = coerce_datetime(meta.get("updated"), source) if meta.get("updated") else None
        draft = meta.get("draft", False)
        if not isinstance(draft, bool):
            raise ContentError(f"{source}: 'draft' must be true or false.")
        return cls(
            path=os.path.abspath(path),
            kind=kind,
            title=title.strip(),
            slug=slugify(slug_value),
            raw=document.content,
            metadata=meta,
            date=date_value,
            updated=updated_value,
            tags=normalise_terms(meta.get("tags"), "tags", source),
            categories=normalise_terms(meta.get("categories"), "categories", source),
            description=description.strip(),
            summary=summary.strip(),
            image=image.strip(),
            canonical_url=canonical_url.strip(),
            permalink=normalise_permalink(meta.get("permalink"), source),
            draft=draft,
            reading_time=reading_time_minutes(document.content),
        )

    def published(self, now: datetime, *, include_drafts: bool = False, include_future: bool = False) -> bool:
        if self.draft and not include_drafts:
            return False
        # Pages are normally timeless; an omitted date is supplied from the file mtime
        # only for stable ordering. Future-dating therefore applies to posts alone.
        if self.kind == "post" and self.date > now and not include_future:
            return False
        return True

    def term_slugs(self, kind: str) -> list[tuple[str, str]]:
        terms = self.tags if kind == "tag" else self.categories
        return [(term, slugify(term)) for term in terms]
