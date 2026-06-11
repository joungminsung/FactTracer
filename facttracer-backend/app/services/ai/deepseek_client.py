import json
import re
from typing import Any

from openai import OpenAI
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.ai.prompts import prompt_system
from app.services.admin.settings import get_effective_setting


class DeepSeekAnalysisService:
    def __init__(self, db: Session | None = None) -> None:
        self.settings = get_settings()
        self.ai_processing_enabled = bool(get_effective_setting(db, "ai_processing_enabled"))
        self.api_key = get_effective_setting(db, "deepseek_api_key")
        self.base_url = get_effective_setting(db, "deepseek_base_url")
        self.flash_model = get_effective_setting(db, "deepseek_flash_model")
        self.pro_model = get_effective_setting(db, "deepseek_pro_model")
        self._client: OpenAI | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.ai_processing_enabled and self.api_key)

    @property
    def client(self) -> OpenAI:
        if not self.api_key:
            raise RuntimeError("DEEPSEEK_API_KEY is not configured")
        if self._client is None:
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=20,
            )
        return self._client

    def _loads_json(self, content: str, fallback: Any) -> Any:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
            cleaned = re.sub(r"```$", "", cleaned).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        object_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        array_match = re.search(r"\[.*\]", cleaned, re.DOTALL)
        for match in (object_match, array_match):
            if not match:
                continue
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                continue
        return fallback

    def _chat_json(
        self,
        *,
        fallback: Any = None,
        messages: list[dict[str, str]],
        model: str,
    ) -> Any:
        if not self.enabled:
            return fallback
        kwargs: dict[str, Any] = {
            "messages": messages,
            "model": model,
            "stream": False,
            "temperature": 0.1,
        }
        try:
            response = self.client.chat.completions.create(
                **kwargs,
                response_format={"type": "json_object"},
            )
        except TypeError:
            response = self.client.chat.completions.create(**kwargs)
        except Exception:
            return fallback
        content = response.choices[0].message.content or ""
        return self._loads_json(content, fallback)

    def analyze_article_reference(self, article_url: str) -> dict | None:
        if not self.enabled:
            return None
        return self._chat_json(
            messages=[
                {
                    "role": "system",
                    "content": prompt_system("article_reference"),
                },
                {
                    "role": "user",
                    "content": f"Article URL submitted for verification: {article_url}",
                },
            ],
            model=self.flash_model,
        )

    def analyze_article_content(
        self,
        *,
        body_text: str,
        publisher: str,
        title: str,
        url: str,
    ) -> dict | None:
        if not self.enabled:
            return None
        compact_body = body_text[:8000]
        return self._chat_json(
            fallback=None,
            messages=[
                {
                    "role": "system",
                    "content": prompt_system("article_triage"),
                },
                {
                    "role": "user",
                    "content": (
                        f"URL: {url}\nPublisher: {publisher}\nTitle: {title}\n\n"
                        f"Article text:\n{compact_body}"
                    ),
                },
            ],
            model=self.flash_model,
        )

    def generate_search_keywords(
        self,
        *,
        limit: int = 10,
        query: str,
        topic: str = "사회",
    ) -> list[dict]:
        if not self.enabled:
            return []
        payload = self._chat_json(
            fallback={"keywords": []},
            messages=[
                {
                    "role": "system",
                    "content": prompt_system("search_keyword_generation"),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {"seed_query": query, "topic": topic, "limit": limit},
                        ensure_ascii=False,
                    ),
                },
            ],
            model=self.flash_model,
        )
        rows = payload.get("keywords", []) if isinstance(payload, dict) else []
        if not isinstance(rows, list):
            return []
        cleaned: list[dict] = []
        for row in rows[:limit]:
            if not isinstance(row, dict):
                continue
            keyword = str(row.get("query") or "").strip()
            if len(keyword) < 2:
                continue
            cleaned.append(row | {"query": keyword[:300]})
        return cleaned

    def build_research_plan(
        self,
        *,
        issue: dict,
        missing_signals: list[str],
        trigger_type: str,
    ) -> dict | None:
        if not self.enabled:
            return None
        return self._chat_json(
            fallback=None,
            messages=[
                {
                    "role": "system",
                    "content": prompt_system("research_planning"),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "issue": issue,
                            "missingSignals": missing_signals,
                            "triggerType": trigger_type,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            model=self.flash_model,
        )

    def define_incident_candidate(
        self,
        *,
        articles: list[dict],
        topic_name: str,
    ) -> dict | None:
        if not self.enabled or not articles:
            return None
        return self._chat_json(
            fallback=None,
            messages=[
                {
                    "role": "system",
                    "content": prompt_system("incident_definition"),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {"discovery_topic": topic_name, "articles": articles[:10]},
                        ensure_ascii=False,
                    ),
                },
            ],
            model=self.flash_model,
        )

    def extract_claims_from_article(
        self,
        *,
        body_text: str,
        limit: int = 12,
        summary: str = "",
        title: str,
    ) -> list[dict]:
        if not self.enabled:
            return []
        payload = self._chat_json(
            fallback={"claims": []},
            messages=[
                {
                    "role": "system",
                    "content": prompt_system("claim_extraction"),
                },
                {
                    "role": "user",
                    "content": (
                        f"Limit: {limit}\nTitle: {title}\nSummary: {summary}\n\n"
                        f"Text:\n{body_text[:10000]}"
                    ),
                },
            ],
            model=self.flash_model,
        )
        rows = payload.get("claims", []) if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            return []
        claims: list[dict] = []
        for row in rows[:limit]:
            if not isinstance(row, dict):
                continue
            text = str(row.get("claim_text") or "").strip()
            if len(text) < 8:
                continue
            claims.append(row | {"claim_text": text})
        return claims

    def structure_claim(self, claim_text: str, reason: str) -> dict | None:
        if not self.enabled:
            return None
        return self._chat_json(
            fallback=None,
            messages=[
                {
                    "role": "system",
                    "content": prompt_system("claim_structuring"),
                },
                {
                    "role": "user",
                    "content": f"Claim: {claim_text}\nReason: {reason}",
                },
            ],
            model=self.flash_model,
        )

    def generate_evidence_candidates(
        self,
        *,
        claim_text: str,
        claim_type: str,
        entities_json: dict,
        local_documents: list[dict],
    ) -> list[dict]:
        if not self.enabled or not local_documents:
            return []
        payload = self._chat_json(
            fallback={"evidences": []},
            messages=[
                {
                    "role": "system",
                    "content": prompt_system("evidence_ranking"),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "claim": claim_text,
                            "claim_type": claim_type,
                            "entities": entities_json,
                            "documents": local_documents[:20],
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            model=self.flash_model,
        )
        rows = payload.get("evidences", []) if isinstance(payload, dict) else []
        return [row for row in rows if isinstance(row, dict)]

    def verify_claim_against_evidence(
        self,
        *,
        claim_text: str,
        claim_type: str,
        entities_json: dict,
        evidences: list[dict],
    ) -> dict | None:
        if not self.enabled:
            return None
        return self._chat_json(
            fallback=None,
            messages=[
                {
                    "role": "system",
                    "content": prompt_system("claim_verification"),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "claim": claim_text,
                            "claim_type": claim_type,
                            "entities": entities_json,
                            "evidences": evidences[:12],
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            model=self.pro_model,
        )

    def build_perspectives(
        self,
        *,
        issue_title: str,
        claims: list[dict],
    ) -> list[dict]:
        if not self.enabled or not claims:
            return []
        payload = self._chat_json(
            fallback={"perspectives": []},
            messages=[
                {
                    "role": "system",
                    "content": prompt_system("perspective_mapping"),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {"issue_title": issue_title, "claims": claims[:50]},
                        ensure_ascii=False,
                    ),
                },
            ],
            model=self.flash_model,
        )
        rows = payload.get("perspectives", []) if isinstance(payload, dict) else []
        return [row for row in rows if isinstance(row, dict)]

    def synthesize_issue_detail(
        self,
        *,
        articles: list[dict] | None = None,
        claims: list[dict] | None = None,
        evidences: list[dict] | None = None,
        issue_title: str,
        records: dict[str, Any] | None = None,
    ) -> dict | None:
        if not self.enabled:
            return None
        supplied_records = records or {
            "articles": articles or [],
            "claims": claims or [],
            "evidences": evidences or [],
        }
        payload = self._chat_json(
            fallback=None,
            messages=[
                {
                    "role": "system",
                    "content": prompt_system("issue_detail_synthesis"),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "issue_title": issue_title,
                            "records": supplied_records,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            model=self.pro_model,
        )
        return payload if isinstance(payload, dict) else None

    def review_issue_reverification(
        self,
        *,
        issue_title: str,
        memo: str | None,
        priority: str,
    ) -> dict | None:
        if not self.enabled:
            return None
        return self._chat_json(
            fallback=None,
            messages=[
                {
                    "role": "system",
                    "content": prompt_system("reverification_review"),
                },
                {
                    "role": "user",
                    "content": f"Issue: {issue_title}\nPriority: {priority}\nMemo: {memo or ''}",
                },
            ],
            model=self.pro_model,
        )
