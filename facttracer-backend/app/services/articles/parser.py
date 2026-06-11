from __future__ import annotations

import html
import re
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

from app.core.config import get_settings
from app.services.articles.normalizer import normalize_whitespace
from app.services.images.candidates import extract_image_urls_from_html


@dataclass
class ParsedArticle:
    title: str
    publisher: str
    body_text: str
    summary: str
    published_at: datetime | None
    parse_status: str
    image_candidates: list[str] = field(default_factory=list)


def _html_title(raw_html: str) -> str:
    patterns = [
        r"<meta[^>]+property=[\"']og:title[\"'][^>]+content=[\"']([^\"']+)[\"']",
        r"<meta[^>]+name=[\"']title[\"'][^>]+content=[\"']([^\"']+)[\"']",
        r"<title[^>]*>(.*?)</title>",
    ]
    for pattern in patterns:
        match = re.search(pattern, raw_html, re.IGNORECASE | re.DOTALL)
        if match:
            return normalize_whitespace(html.unescape(re.sub(r"<[^>]+>", " ", match.group(1))))
    return ""


def _html_body(raw_html: str) -> str:
    stripped = re.sub(r"(?is)<(script|style|noscript).*?</\1>", " ", raw_html)
    paragraphs = re.findall(r"(?is)<p[^>]*>(.*?)</p>", stripped)
    if paragraphs:
        text = " ".join(re.sub(r"<[^>]+>", " ", item) for item in paragraphs)
    else:
        text = re.sub(r"<[^>]+>", " ", stripped)
    return normalize_whitespace(html.unescape(text))


def parse_article_content(
    *,
    body_text: str = "",
    image_candidates: list[str] | None = None,
    published_at: datetime | None = None,
    publisher: str = "",
    title: str = "",
    url: str,
) -> ParsedArticle:
    body_text = normalize_whitespace(body_text)
    title = normalize_whitespace(title)
    publisher = normalize_whitespace(publisher) or urlparse(url).netloc
    summary = body_text[:220] if body_text else title
    return ParsedArticle(
        body_text=body_text,
        image_candidates=list(image_candidates or []),
        parse_status="parsed" if body_text else "title_only",
        published_at=published_at,
        publisher=publisher,
        summary=summary,
        title=title or url,
    )


def fetch_and_parse_url(url: str) -> ParsedArticle:
    settings = get_settings()
    request = urllib.request.Request(
        url,
        headers={"User-Agent": settings.collector_user_agent},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=settings.collector_timeout_seconds) as response:
            content_type = response.headers.get("content-type", "")
            published_header = response.headers.get("last-modified")
            raw = response.read(1_500_000)
        if "text/html" not in content_type and "xml" not in content_type and "text/" not in content_type:
            return parse_article_content(title=url, url=url)
        raw_html = raw.decode("utf-8", errors="ignore")
        published_at = parsedate_to_datetime(published_header) if published_header else None
        return parse_article_content(
            body_text=_html_body(raw_html),
            image_candidates=extract_image_urls_from_html(raw_html, base_url=url),
            published_at=published_at,
            publisher=urlparse(url).netloc,
            title=_html_title(raw_html),
            url=url,
        )
    except Exception:
        return parse_article_content(title=url, url=url)
