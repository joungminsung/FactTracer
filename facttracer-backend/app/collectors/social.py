from __future__ import annotations

import json
import urllib.request

from app.collectors.base import CollectedArticle
from app.core.config import get_settings
from app.services.articles.normalizer import normalize_whitespace


def collect_public_social_candidates(endpoint: str, *, publisher: str = "public-social") -> list[CollectedArticle]:
    request = urllib.request.Request(endpoint, headers={"User-Agent": get_settings().collector_user_agent})
    with urllib.request.urlopen(request, timeout=get_settings().collector_timeout_seconds) as response:
        payload = json.loads(response.read(2_000_000).decode("utf-8", errors="ignore"))
    items = payload.get("items") or payload.get("posts") or payload.get("results") or []
    results: list[CollectedArticle] = []
    for item in items[:50]:
        text = normalize_whitespace(item.get("text") or item.get("content") or item.get("description") or "")
        url = item.get("url") or item.get("link") or ""
        if text and url:
            results.append(
                CollectedArticle(
                    body_text=text,
                    publisher=item.get("author") or publisher,
                    source_type="social",
                    summary=text[:220],
                    title=text[:120],
                    url=url,
                ),
            )
    return results
