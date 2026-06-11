from __future__ import annotations

import html
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

from app.collectors.base import CollectedArticle
from app.collectors.media import extract_media_image_urls
from app.core.config import get_settings
from app.services.articles.normalizer import normalize_whitespace


def collect_rss(feed_url: str, *, publisher: str = "") -> list[CollectedArticle]:
    settings = get_settings()
    request = urllib.request.Request(feed_url, headers={"User-Agent": settings.collector_user_agent})
    with urllib.request.urlopen(request, timeout=settings.collector_timeout_seconds) as response:
        raw = response.read(2_000_000)
    root = ET.fromstring(raw)
    items = root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry")
    results: list[CollectedArticle] = []
    for item in items[:50]:
        title = item.findtext("title") or item.findtext("{http://www.w3.org/2005/Atom}title") or ""
        link = item.findtext("link") or ""
        atom_link = item.find("{http://www.w3.org/2005/Atom}link")
        if not link and atom_link is not None:
            link = atom_link.attrib.get("href", "")
        description = item.findtext("description") or item.findtext("summary") or ""
        published = item.findtext("pubDate") or item.findtext("published") or item.findtext("updated")
        try:
            published_at = parsedate_to_datetime(published) if published else None
        except Exception:
            published_at = None
        if title and link:
            image_urls = extract_media_image_urls(item)
            results.append(
                CollectedArticle(
                    body_text=normalize_whitespace(html.unescape(description)),
                    image_candidates=image_urls,
                    image_url=image_urls[0] if image_urls else "",
                    published_at=published_at,
                    publisher=publisher,
                    source_type="rss",
                    summary=normalize_whitespace(html.unescape(description))[:220],
                    title=normalize_whitespace(html.unescape(title)),
                    url=link,
                ),
            )
    return results
