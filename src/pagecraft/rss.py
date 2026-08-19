"""RSS 2.0 feed generation for Pagecraft.

Whenever a build includes blog posts, Pagecraft writes a valid RSS feed
(default ``feed.xml``) containing the newest posts with their titles,
dates, descriptions, and full HTML content.
"""

from __future__ import annotations

import html
from datetime import datetime, timezone
from email.utils import format_datetime
from xml.etree.ElementTree import Element, SubElement, tostring


def build_rss(items: list[dict], site_config) -> str:
    """Build an RSS 2.0 XML document for the given post items.

    Each item is a dict with keys: title, url, description, html, date.
    """
    now = datetime.now(timezone.utc)
    rss = Element("rss", version="2.0")
    rss.set("xmlns:atom", "http://www.w3.org/2005/Atom")
    rss.set("xmlns:content", "http://purl.org/rss/1.0/modules/content/")

    channel = SubElement(rss, "channel")
    SubElement(channel, "title").text = site_config.title
    SubElement(channel, "link").text = site_config.url
    SubElement(channel, "description").text = site_config.description
    SubElement(channel, "language").text = "en"
    SubElement(channel, "lastBuildDate").text = format_datetime(now, usegmt=True)
    SubElement(channel, "generator").text = "Pagecraft"

    atom_link = SubElement(channel, "atom:link")
    atom_link.set("href", site_config.url + "/" + site_config.feed_filename)
    atom_link.set("rel", "self")
    atom_link.set("type", "application/rss+xml")

    for item in items[: site_config.feed_posts_limit]:
        entry = SubElement(channel, "item")
        SubElement(entry, "title").text = item["title"]
        SubElement(entry, "link").text = item["url"]
        SubElement(entry, "guid").text = item["url"]
        pub_date = item["date"] if item["date"].tzinfo else item["date"].replace(tzinfo=timezone.utc)
        SubElement(entry, "pubDate").text = format_datetime(pub_date, usegmt=True)
        desc = SubElement(entry, "description")
        desc.text = item.get("description") or _strip_text(item.get("html") or "")
        content = SubElement(entry, "content:encoded")
        content.text = item.get("html") or ""

    return '<?xml version="1.0" encoding="UTF-8"?>\n' + _to_string(rss)


def _to_string(element: Element) -> str:
    raw = tostring(element, encoding="unicode")
    # Self-close empty tags in the RSS 2.0 style for compatibility.
    return raw.replace(" />", "/>")


def _strip_text(html_text: str) -> str:
    import re
    from markupsafe import Markup
    text = re.sub(r"<[^>]+>", " ", html_text)
    return html.unescape(text).strip()
