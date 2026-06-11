from __future__ import annotations

from typing import Any

from openai import OpenAI
from sqlalchemy.orm import Session

from app.collectors.base import CollectedArticle
from app.services.ai.prompts import prompt_system
from app.services.admin.settings import get_effective_setting


class OpenAIWebSearchProvider:
    name = "openai_web_search"

    def __init__(self, db: Session | None = None) -> None:
        self.api_key = get_effective_setting(db, "openai_api_key")
        self.enabled_setting = bool(get_effective_setting(db, "openai_web_search_enabled", False))
        self.model = str(get_effective_setting(db, "openai_web_search_model", "gpt-5.5"))
        self._client: OpenAI | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.enabled_setting and self.api_key)

    @property
    def client(self) -> OpenAI:
        if not self.api_key:
            raise RuntimeError("OpenAI API key is not configured")
        if self._client is None:
            self._client = OpenAI(api_key=self.api_key, timeout=30)
        return self._client

    def _search_prompt(self, query: str, *, route: dict[str, Any] | None = None) -> str:
        return (
            f"{prompt_system('openai_web_search')}\n\n"
            f"Route: {route or {}}\n"
            f"Query: {query}\n"
            "Return sources that can be audited later. Prefer direct pages over search result pages."
        )

    def search_sources(
        self,
        query: str,
        *,
        max_items: int = 5,
        route: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if not self.enabled:
            return []
        response = self.client.responses.create(
            include=["web_search_call.action.sources"],
            input=self._search_prompt(query, route=route),
            model=self.model,
            tools=[{"type": "web_search"}],
        )
        sources: list[dict[str, Any]] = []
        for item in getattr(response, "output", []) or []:
            action = getattr(item, "action", None)
            for source in getattr(action, "sources", []) or []:
                url = getattr(source, "url", "") or (source.get("url") if isinstance(source, dict) else "")
                title = getattr(source, "title", "") or (source.get("title") if isinstance(source, dict) else "")
                publisher = getattr(source, "publisher", "") or (
                    source.get("publisher") if isinstance(source, dict) else ""
                )
                if not url:
                    continue
                sources.append(
                    {
                        "publisher": publisher or "",
                        "reason": "openai web search",
                        "title": title or url,
                        "url": url,
                    },
                )
                if len(sources) >= max_items:
                    return sources
        return sources[:max_items]

    def search(
        self,
        *,
        max_items: int = 5,
        query: str,
        route: dict[str, Any] | None = None,
    ) -> list[CollectedArticle]:
        rows: list[CollectedArticle] = []
        for source in self.search_sources(query, max_items=max_items, route=route):
            rows.append(
                CollectedArticle(
                    publisher=str(source.get("publisher") or "OpenAI Web Search"),
                    source_type=str((route or {}).get("sourceType") or "web_search"),
                    summary=str(source.get("reason") or ""),
                    title=str(source.get("title") or source.get("url") or ""),
                    url=str(source.get("url") or ""),
                ),
            )
        return rows
