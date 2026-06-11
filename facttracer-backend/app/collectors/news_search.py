from __future__ import annotations

import json
import html
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

from app.collectors.base import CollectedArticle
from app.collectors.media import extract_media_image_urls
from app.core.config import get_settings
from app.services.articles.normalizer import normalize_whitespace


def collect_json_news(endpoint: str, *, publisher: str = "", query: str = "") -> list[CollectedArticle]:
    settings = get_settings()
    url = endpoint
    if query:
        separator = "&" if "?" in endpoint else "?"
        url = f"{endpoint}{separator}{urllib.parse.urlencode({'q': query})}"
    request = urllib.request.Request(url, headers={"User-Agent": settings.collector_user_agent})
    with urllib.request.urlopen(request, timeout=settings.collector_timeout_seconds) as response:
        payload = json.loads(response.read(2_000_000).decode("utf-8", errors="ignore"))
    items = payload.get("items") or payload.get("articles") or payload.get("results") or []
    results: list[CollectedArticle] = []
    for item in items[:50]:
        title = item.get("title") or item.get("name") or ""
        link = item.get("url") or item.get("link") or ""
        if title and link:
            summary = item.get("summary") or item.get("description") or item.get("content") or ""
            results.append(
                CollectedArticle(
                    body_text=normalize_whitespace(item.get("body") or item.get("content") or ""),
                    publisher=item.get("publisher") or item.get("source") or publisher,
                    source_type="news_search",
                    summary=normalize_whitespace(summary)[:220],
                    title=normalize_whitespace(title),
                    url=link,
                ),
            )
    return results


def _strip_html(value: str) -> str:
    return normalize_whitespace(re.sub(r"<[^>]+>", " ", html.unescape(value or "")))


def google_news_search_url(query: str, *, language: str = "ko", region: str = "KR") -> str:
    encoded = urllib.parse.urlencode({"q": query, "hl": language, "gl": region, "ceid": f"{region}:{language}"})
    return f"https://news.google.com/rss/search?{encoded}"


def collect_google_news_search(
    query: str,
    *,
    language: str = "ko",
    max_items: int = 30,
    publisher: str = "Google News",
    region: str = "KR",
) -> list[CollectedArticle]:
    settings = get_settings()
    request = urllib.request.Request(
        google_news_search_url(query, language=language, region=region),
        headers={"User-Agent": settings.collector_user_agent},
    )
    with urllib.request.urlopen(request, timeout=settings.collector_timeout_seconds) as response:
        raw = response.read(2_000_000)

    root = ET.fromstring(raw)
    results: list[CollectedArticle] = []
    for item in root.findall(".//item")[:max_items]:
        title = _strip_html(item.findtext("title") or "")
        link = item.findtext("link") or ""
        description = _strip_html(item.findtext("description") or "")
        source = item.find("source")
        source_name = _strip_html(source.text if source is not None and source.text else "") or publisher
        published = item.findtext("pubDate")
        try:
            published_at = parsedate_to_datetime(published) if published else None
        except Exception:
            published_at = None
        if not title or not link:
            continue
        image_urls = extract_media_image_urls(item)
        results.append(
            CollectedArticle(
                body_text=description,
                image_candidates=image_urls,
                image_url=image_urls[0] if image_urls else "",
                published_at=published_at,
                publisher=source_name,
                source_type="news_search",
                summary=description[:220],
                title=title,
                url=link,
            ),
        )
    return results
