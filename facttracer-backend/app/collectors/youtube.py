from __future__ import annotations

import json
import urllib.request

from app.collectors.base import CollectedArticle
from app.core.config import get_settings
from app.services.articles.normalizer import normalize_whitespace
from app.services.manual_checks.youtube import fetch_youtube_transcript


def collect_youtube_candidates(endpoint: str, *, publisher: str = "youtube") -> list[CollectedArticle]:
    request = urllib.request.Request(endpoint, headers={"User-Agent": get_settings().collector_user_agent})
    with urllib.request.urlopen(request, timeout=get_settings().collector_timeout_seconds) as response:
        payload = json.loads(response.read(2_000_000).decode("utf-8", errors="ignore"))
    items = payload.get("items") or payload.get("videos") or payload.get("results") or []
    results: list[CollectedArticle] = []
    for item in items[:30]:
        url = item.get("url") or item.get("link") or ""
        title = normalize_whitespace(item.get("title") or "")
        description = normalize_whitespace(item.get("description") or "")
        transcript, status = fetch_youtube_transcript(url) if url else ("", "missing_url")
        body = transcript or description
        if title and url:
            results.append(
                CollectedArticle(
                    body_text=body,
                    publisher=item.get("channel") or publisher,
                    source_type=f"youtube:{status}",
                    summary=(body or title)[:220],
                    title=title,
                    url=url,
                ),
            )
    return results
