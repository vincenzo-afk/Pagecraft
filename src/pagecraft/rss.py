"""RSS 2.0 generation for published Pagecraft posts."""
from __future__ import annotations

import html
from datetime import datetime, timezone
from email.utils import format_datetime
from xml.etree.ElementTree import Element, SubElement, tostring


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def build_rss(items: list[dict], site_config) -> str:
    """Build a standards-friendly RSS 2.0 document from published post items."""
    newest = max((item.get("updated") or item["date"] for item in items), default=datetime.now())
    rss = Element("rss", version="2.0")
    rss.set("xmlns:atom", "http://www.w3.org/2005/Atom")
    rss.set("xmlns:content", "http://purl.org/rss/1.0/modules/content/")
    rss.set("xmlns:media", "http://search.yahoo.com/mrss/")

    channel = SubElement(rss, "channel")
    SubElement(channel, "title").text = site_config.title
    SubElement(channel, "link").text = site_config.url
    SubElement(channel, "description").text = site_config.description
    SubElement(channel, "language").text = site_config.language
    SubElement(channel, "lastBuildDate").text = format_datetime(_as_utc(newest), usegmt=True)
    SubElement(channel, "generator").text = "Pagecraft"

    atom_link = SubElement(channel, "atom:link")
    atom_link.set("href", site_config.feed_url)
    atom_link.set("rel", "self")
    atom_link.set("type", "application/rss+xml")

    for item in items[: site_config.feed_posts_limit]:
        entry = SubElement(channel, "item")
        SubElement(entry, "title").text = item["title"]
        SubElement(entry, "link").text = item["url"]
        SubElement(entry, "guid", isPermaLink="true").text = item["url"]
        SubElement(entry, "pubDate").text = format_datetime(_as_utc(item["date"]), usegmt=True)
        if item.get("updated"):
            SubElement(entry, "atom:updated").text = _as_utc(item["updated"]).isoformat().replace("+00:00", "Z")
        SubElement(entry, "description").text = item.get("summary") or item.get("description") or _strip_text(item.get("html") or "")
        SubElement(entry, "content:encoded").text = item.get("html") or ""
        if item.get("image"):
            media = SubElement(entry, "media:content")
            media.set("url", item["image"])
            media.set("medium", "image")

    return '<?xml version="1.0" encoding="UTF-8"?>\n' + tostring(rss, encoding="unicode").replace(" />", "/>")


def _strip_text(html_text: str) -> str:
    import re

    return html.unescape(re.sub(r"<[^>]+>", " ", html_text)).strip()
