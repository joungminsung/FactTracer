from __future__ import annotations

from typing import Any, Protocol

from app.collectors.base import CollectedArticle
from app.collectors.news_search import collect_google_news_search
from app.collectors.official_sources import collect_official_site_search
from app.services.ai.openai_web_search import OpenAIWebSearchProvider


class SearchProvider(Protocol):
    name: str

    def search(self, *, max_items: int, query: str, route: dict[str, Any] | None = None) -> list[CollectedArticle]:
        ...


class GoogleNewsProvider:
    name = "google_news"

    def search(self, *, max_items: int = 10, query: str, route: dict[str, Any] | None = None) -> list[CollectedArticle]:
        return collect_google_news_search(query, max_items=max_items)


class SiteQueryProvider:
    name = "site_query"

    def search(self, *, max_items: int = 10, query: str, route: dict[str, Any] | None = None) -> list[CollectedArticle]:
        route = route or {}
        domain = str(route.get("domain") or "").strip()
        if not domain:
            return []
        publisher = str(route.get("name") or domain)
        source_type = str(route.get("sourceType") or "official")
        collection_url = str(route.get("collectionUrl") or "").strip()
        if collection_url and source_type in {"official", "public", "statistics", "law", "company"}:
            direct_rows = collect_official_site_search(
                collection_url,
                query,
                max_items=max_items,
                publisher=publisher,
                source_type=source_type,
            )
            if direct_rows:
                return direct_rows[:max_items]
        rows = collect_google_news_search(f"site:{domain} {query}".strip(), max_items=max_items, publisher=publisher)
        for row in rows:
            row.publisher = row.publisher or publisher
            row.source_type = source_type
        return rows


def provider_for_route(route: dict[str, Any], *, db: Any = None) -> SearchProvider:
    provider = str(route.get("provider") or "google_news")
    if provider == "openai_web_search":
        return OpenAIWebSearchProvider(db)
    if provider == "site_query":
        return SiteQueryProvider()
    return GoogleNewsProvider()
