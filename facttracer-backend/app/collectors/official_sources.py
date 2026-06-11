from __future__ import annotations

import html
import re
import urllib.parse
import urllib.request

from app.collectors.base import CollectedArticle
from app.core.config import get_settings
from app.services.articles.parser import fetch_and_parse_url
from app.services.articles.normalizer import normalize_whitespace, token_set


def collect_official_source(url: str, *, publisher: str = "") -> list[CollectedArticle]:
    parsed = fetch_and_parse_url(url)
    return [
        CollectedArticle(
            body_text=parsed.body_text,
            image_candidates=parsed.image_candidates,
            image_url=parsed.image_candidates[0] if parsed.image_candidates else "",
            publisher=publisher or parsed.publisher,
            published_at=parsed.published_at,
            source_type="official",
            summary=parsed.summary,
            title=parsed.title,
            url=url,
        ),
    ]


def _fetch_html(url: str) -> str:
    settings = get_settings()
    request = urllib.request.Request(url, headers={"User-Agent": settings.collector_user_agent})
    with urllib.request.urlopen(request, timeout=settings.collector_timeout_seconds) as response:
        raw = response.read(1_500_000)
    return raw.decode("utf-8", errors="ignore")


def _anchor_rows(raw_html: str, *, base_url: str) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for match in re.finditer(r"(?is)<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", raw_html):
        href = html.unescape(match.group(1))
        label = normalize_whitespace(re.sub(r"<[^>]+>", " ", html.unescape(match.group(2))))
        url = urllib.parse.urljoin(base_url, href)
        if urllib.parse.urlparse(url).scheme not in {"http", "https"}:
            continue
        rows.append((url, label))
    return rows


def _query_terms(query: str) -> set[str]:
    return {term for term in token_set(query) if len(term) >= 2}


def _matches_query(url: str, label: str, terms: set[str]) -> bool:
    if not terms:
        return True
    text = normalize_whitespace(f"{label} {urllib.parse.unquote(url)}").lower()
    return any(term.lower() in text for term in terms)


def collect_official_site_search(
    collection_url: str,
    query: str,
    *,
    max_items: int = 5,
    publisher: str = "",
    source_type: str = "official",
) -> list[CollectedArticle]:
    if not collection_url:
        return []
    terms = _query_terms(query)
    try:
        raw_html = _fetch_html(collection_url)
    except Exception:
        return []

    candidates: list[tuple[str, str]] = []
    seen: set[str] = set()
    for url, label in _anchor_rows(raw_html, base_url=collection_url):
        if url in seen or not _matches_query(url, label, terms):
            continue
        seen.add(url)
        candidates.append((url, label))
        if len(candidates) >= max_items * 2:
            break

    results: list[CollectedArticle] = []
    for url, label in candidates[:max_items]:
        parsed = fetch_and_parse_url(url)
        title = parsed.title if parsed.title != url else label or url
        results.append(
            CollectedArticle(
                body_text=parsed.body_text,
                image_candidates=parsed.image_candidates,
                image_url=parsed.image_candidates[0] if parsed.image_candidates else "",
                publisher=publisher or parsed.publisher,
                published_at=parsed.published_at,
                source_type=source_type,
                summary=parsed.summary or label,
                title=title,
                url=url,
            ),
        )
    return results
