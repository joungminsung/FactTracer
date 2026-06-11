from __future__ import annotations

import json
import re
from typing import Any

from openai import OpenAI
from sqlalchemy.orm import Session

from app import models
from app.services.admin.settings import get_effective_setting
from app.services.topics import normalize_topic


OPENAI_KEY_PATTERN = re.compile(r"sk-[A-Za-z0-9_*\\-]{8,}")

DOMAIN_SOURCE_LABELS = {
    "law.go.kr": "국가법령정보센터",
    "kostat.go.kr": "통계청",
    "mofa.go.kr": "외교부",
    "nec.go.kr": "중앙선거관리위원회",
    "news.google.com": "구글 뉴스",
}


def _safe_error(exc: Exception) -> str:
    redacted = OPENAI_KEY_PATTERN.sub("sk-<redacted>", str(exc))
    return redacted[:500]


def _loads_json(content: str, fallback: Any = None) -> Any:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    object_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if object_match:
        try:
            return json.loads(object_match.group(0))
        except json.JSONDecodeError:
            return fallback
    return fallback


def _source_label(source: dict[str, Any] | None) -> str:
    if not isinstance(source, dict):
        return "원문 자료"
    title = str(source.get("title") or "").strip()
    raw_publisher = str(source.get("publisher") or source.get("source") or source.get("outlet") or "").strip()
    compact_publisher = raw_publisher.removeprefix("www.").lower()
    if compact_publisher == "news.google.com" and " - " in title:
        outlet = title.rsplit(" - ", 1)[-1].strip()
        if outlet:
            return outlet
    label = DOMAIN_SOURCE_LABELS.get(compact_publisher, raw_publisher or title)
    return label or "원문 자료"


def _compact_source(source: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(source.get("id") or "").strip(),
        "label": _source_label(source),
        "title": str(source.get("title") or "원문 자료").strip()[:180],
        "publisher": str(source.get("publisher") or "").strip()[:80],
        "sourceType": str(source.get("sourceType") or "media").strip(),
        "url": str(source.get("url") or "").strip(),
    }


def _fact_payloads(issue: models.Issue, cache: dict[str, Any]) -> list[dict[str, str]]:
    rows = []
    for fact in (cache.get("confirmed_facts") or issue.confirmed_facts or [])[:5]:
        if not isinstance(fact, dict):
            continue
        text = str(fact.get("text") or "").strip()
        if not text:
            continue
        rows.append(
            {
                "text": text[:300],
                "verdict": str(fact.get("verdict") or "근거 확인 중").strip()[:80],
            },
        )
    return rows


def _cluster_payloads(issue: models.Issue, cache: dict[str, Any]) -> list[dict[str, str]]:
    rows = []
    for cluster in (cache.get("claim_clusters") or issue.claim_clusters or [])[:5]:
        if not isinstance(cluster, dict):
            continue
        title = str(cluster.get("title") or "쟁점").strip()
        conflict = str(cluster.get("conflict") or "").strip()
        common = str(cluster.get("commonGround") or cluster.get("common_ground") or "").strip()
        if not (title or conflict or common):
            continue
        rows.append(
            {
                "title": title[:120],
                "conflict": conflict[:300],
                "commonGround": common[:300],
            },
        )
    return rows


def _issue_payload(
    *,
    cache: dict[str, Any],
    issue: models.Issue,
    sources: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "id": issue.id,
        "title": issue.title,
        "topic": normalize_topic(issue.topic),
        "summary": (issue.summary or str(cache.get("computed_summary") or "")).strip()[:700],
        "issueScore": issue.issue_score,
        "needsReviewCount": issue.needs_review_count,
        "changedClaims": issue.changed_claims,
        "facts": _fact_payloads(issue, cache),
        "claimClusters": _cluster_payloads(issue, cache),
        "sources": [_compact_source(source) for source in sources[:6] if source.get("id")],
    }


class OpenAIPodcastScriptGenerator:
    def __init__(self, db: Session | None = None) -> None:
        self.ai_processing_enabled = bool(get_effective_setting(db, "ai_processing_enabled"))
        self.api_key = get_effective_setting(db, "openai_api_key")
        self.model = str(get_effective_setting(db, "openai_podcast_script_model") or "gpt-4o-mini")
        self.last_error: str | None = None
        self._client: OpenAI | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.ai_processing_enabled and self.api_key)

    @property
    def client(self) -> OpenAI:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        if self._client is None:
            self._client = OpenAI(api_key=self.api_key, timeout=60)
        return self._client

    def generate_issue_script(
        self,
        *,
        cache: dict[str, Any],
        episode_format: str,
        hosts: list[dict[str, str]],
        issue: models.Issue,
        sources: list[dict[str, Any]],
        validation_feedback: str | None = None,
        variant: str,
    ) -> dict[str, Any] | None:
        if not self.enabled:
            self.last_error = "openai_script_generation_disabled"
            return None
        payload = {
            "task": "generate_issue_podcast_script",
            "purpose": "국민의 알 권리",
            "variant": variant,
            "episodeFormat": episode_format,
            "hosts": hosts,
            "issue": _issue_payload(issue=issue, cache=cache, sources=sources),
            "allSources": [_compact_source(source) for source in sources[:8] if source.get("id")],
            "requirements": _requirements(hosts=hosts, issue_count=1, variant=variant),
        }
        if validation_feedback:
            payload["validationFeedback"] = validation_feedback
        return self._chat_json(payload)

    def generate_daily_script(
        self,
        *,
        hosts: list[dict[str, str]],
        issue_payloads: list[tuple[models.Issue, dict[str, Any], list[dict[str, Any]]]],
        sources: list[dict[str, Any]],
        validation_feedback: str | None = None,
        variant: str,
    ) -> dict[str, Any] | None:
        if not self.enabled:
            self.last_error = "openai_script_generation_disabled"
            return None
        selected_payloads = [
            _issue_payload(issue=issue, cache=cache, sources=issue_sources)
            for issue, cache, issue_sources in issue_payloads
        ]
        payload = {
            "task": "generate_comprehensive_daily_podcast_script",
            "purpose": "국민의 알 권리",
            "variant": variant,
            "episodeFormat": "panel_3",
            "hosts": hosts,
            "issues": selected_payloads,
            "allSources": [_compact_source(source) for source in sources[:12] if source.get("id")],
            "requirements": _requirements(hosts=hosts, issue_count=len(selected_payloads), variant=variant),
        }
        if validation_feedback:
            payload["validationFeedback"] = validation_feedback
        return self._chat_json(payload)

    def _chat_json(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        self.last_error = None
        messages = [
            {
                "role": "system",
                "content": _system_prompt(),
            },
            {
                "role": "user",
                "content": json.dumps(payload, ensure_ascii=False),
            },
        ]
        kwargs: dict[str, Any] = {
            "messages": messages,
            "model": self.model,
            "stream": False,
            "temperature": 0.45,
        }
        try:
            try:
                response = self.client.chat.completions.create(
                    **kwargs,
                    response_format=_response_schema(payload),
                )
            except Exception as schema_exc:
                try:
                    response = self.client.chat.completions.create(
                        **kwargs,
                        response_format={"type": "json_object"},
                    )
                except TypeError:
                    response = self.client.chat.completions.create(**kwargs)
                except Exception:
                    raise schema_exc
        except Exception as exc:
            self.last_error = _safe_error(exc)
            return None

        content = response.choices[0].message.content or ""
        parsed = _loads_json(content, fallback=None)
        if not isinstance(parsed, dict):
            self.last_error = "openai_script_generation_invalid_json"
            return None
        return parsed


def _response_schema(payload: dict[str, Any]) -> dict[str, Any]:
    issue_ids = _payload_issue_ids(payload)
    source_ids = _payload_source_ids(payload)
    host_ids = [
        str(host.get("id") or "").strip()
        for host in payload.get("hosts", [])
        if isinstance(host, dict) and str(host.get("id") or "").strip()
    ]
    requirements = payload.get("requirements") if isinstance(payload.get("requirements"), dict) else {}
    min_segments = int(requirements.get("minSegments") or 1)
    max_segments = int(requirements.get("maxSegments") or 20)
    segment_properties: dict[str, Any] = {
        "issueId": {"type": "string"},
        "speakerId": {"type": "string"},
        "sourceIds": {
            "type": "array",
            "items": {"type": "string"},
        },
        "text": {"type": "string"},
    }
    if issue_ids:
        segment_properties["issueId"]["enum"] = issue_ids
    if host_ids:
        segment_properties["speakerId"]["enum"] = host_ids
    if source_ids:
        segment_properties["sourceIds"]["items"]["enum"] = source_ids

    return {
        "type": "json_schema",
        "json_schema": {
            "name": "facttracer_podcast_script",
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "script": {
                        "type": "array",
                        "minItems": min_segments,
                        "maxItems": max_segments,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": segment_properties,
                            "required": ["issueId", "speakerId", "sourceIds", "text"],
                        },
                    },
                    "summary": {"type": "string"},
                },
                "required": ["script", "summary"],
            },
            "strict": True,
        },
    }


def _payload_issue_ids(payload: dict[str, Any]) -> list[str]:
    if isinstance(payload.get("issue"), dict):
        issue_id = str(payload["issue"].get("id") or "").strip()
        return [issue_id] if issue_id else []
    issue_ids: list[str] = []
    for issue in payload.get("issues", []):
        if not isinstance(issue, dict):
            continue
        issue_id = str(issue.get("id") or "").strip()
        if issue_id and issue_id not in issue_ids:
            issue_ids.append(issue_id)
    return issue_ids


def _payload_source_ids(payload: dict[str, Any]) -> list[str]:
    source_ids: list[str] = []
    for source in payload.get("allSources", []):
        if not isinstance(source, dict):
            continue
        source_id = str(source.get("id") or "").strip()
        if source_id and source_id not in source_ids:
            source_ids.append(source_id)
    return source_ids


def _requirements(*, hosts: list[dict[str, str]], issue_count: int, variant: str) -> dict[str, Any]:
    if variant == "short":
        min_segments = 5 if issue_count == 1 else max(6, issue_count * 2)
        max_segments = 8 if issue_count == 1 else max(9, issue_count * 3)
    elif variant == "deep":
        min_segments = 8 if issue_count == 1 else max(10, issue_count * 3)
        max_segments = 14 if issue_count == 1 else max(16, issue_count * 4)
    else:
        min_segments = 6 if issue_count == 1 else max(8, issue_count * 3)
        max_segments = 10 if issue_count == 1 else max(12, issue_count * 4)
    return {
        "minSegments": min_segments,
        "maxSegments": max_segments,
        "mustUseSpeakerIds": [host["id"] for host in hosts],
        "mustUseAtLeastTwoSpeakers": len(hosts) >= 2,
        "mustMentionPurposeInOpening": "국민의 알 권리",
        "mustUseSourceAttributionPhrases": "각 이슈마다 적어도 한 번은 해당 issue.sources의 label을 사용해 '출처명에 따르면' 형식으로 말하세요.",
        "mustSetIssueId": "script의 모든 항목에는 관련 issue.id를 issueId로 넣으세요.",
        "mustSetSourceIds": "출처 인용 문장이 있는 항목에는 반드시 해당 source.id를 sourceIds에 넣으세요.",
        "speechLevel": "한국어 존댓말만 사용하세요.",
        "style": "보고서 낭독이 아니라 자연스러운 토크쇼 대화입니다.",
        "avoidAwkwardPhrases": "대사 중간에 '라온입니다', '진행자입니다' 같은 자기소개를 넣지 마세요.",
        "issueCoverage": "daily/comprehensive 회차에서는 입력된 각 issue를 빠뜨리지 말고, 진행자 질문과 답변을 최소 1개씩 배치하세요.",
    }


def _system_prompt() -> str:
    return (
        "당신은 FactTracer의 AI 팟캐스트 작가입니다. 목표는 국민의 알 권리를 위해 "
        "확인된 뉴스 이슈를 자연스럽고 듣기 쉬운 한국어 존댓말 대화로 바꾸는 것입니다.\n"
        "규칙:\n"
        "- 제공된 issue, facts, claimClusters, sources 안의 사실만 사용하세요. 새로운 사실, 수치, 인물, 평가를 만들지 마세요.\n"
        "- 2명 이상 진행자가 있으면 반드시 서로 묻고 답하는 대화체로 작성하세요. 한 사람이 긴 보고서를 읽는 형식은 금지입니다.\n"
        "- 모든 문장은 존댓말이어야 합니다. 반말, '~했다', '~된다' 같은 건조한 보고서 종결을 피하고 방송 대화처럼 말하세요.\n"
        "- 각 이슈의 핵심 설명에는 반드시 '연합뉴스에 따르면', '관계 기관에 따르면'처럼 출처명을 직접 말하세요.\n"
        "- daily/comprehensive 회차에서는 모든 issue마다 출처 인용 문장을 하나 이상 넣어야 합니다.\n"
        "- script 배열의 모든 항목에는 입력 issue.id와 일치하는 issueId를 반드시 넣으세요.\n"
        "- sourceIds는 비워두지 말고, 대사에서 말한 출처에 대응하는 source.id를 넣으세요.\n"
        "- 첫 대사는 '국민의 알 권리'라는 목적을 자연스럽게 포함해야 합니다.\n"
        "- 대사 중간에 캐릭터가 자기 이름을 소개하는 문장, 예를 들어 '라온입니다' 같은 표현은 쓰지 마세요.\n"
        "- 과장, 단정, 음모론적 표현, 법적 결론 단정은 금지입니다. 확인 범위를 분리해 말하세요.\n"
        "- 반환은 JSON 객체만 허용됩니다. 마크다운을 쓰지 마세요.\n"
        "JSON 형식:\n"
        "{"
        "\"summary\":\"회차 한 문장 요약\","
        "\"script\":["
        "{\"speakerId\":\"anchor\",\"text\":\"대사\","
        "\"sourceIds\":[\"source_1\"],\"issueId\":\"입력 issue.id\"}"
        "]"
        "}"
    )
