from __future__ import annotations

import re
from collections import defaultdict
from datetime import UTC, datetime

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.services.articles.normalizer import hash_text, jaccard_similarity, normalize_whitespace
from app.services.issues.synthesis import synthesize_issue_cache
from app.utils import to_iso


FULL_DATE_PATTERN = re.compile(
    r"(?P<year>\d{4})[.-](?P<month>\d{1,2})[.-](?P<day>\d{1,2})(?:\s+(?P<hour>\d{1,2}):(?P<minute>\d{2}))?",
)
KOREAN_DATE_PATTERN = re.compile(
    r"(?P<month>\d{1,2})월\s*(?P<day>\d{1,2})일(?:\s*(?P<ampm>오전|오후)?\s*(?P<hour>\d{1,2})시(?:\s*(?P<minute>\d{1,2})분?)?)?",
)
TIME_PATTERN = re.compile(
    r"(?:(?P<ampm>오전|오후)\s*)?(?P<hour>\d{1,2})시(?:\s*(?P<minute>\d{1,2})분?)?|(?P<hour24>\d{1,2}):(?P<minute24>\d{2})",
)
EVENT_HINTS = (
    "발생",
    "신고",
    "접수",
    "확인",
    "발표",
    "밝혔다",
    "설명",
    "사과",
    "고발",
    "조사",
    "착수",
    "중단",
    "재개",
    "확대",
)
FOLLOWUP_HINTS = ("고발", "조사", "수사", "감사", "착수", "기소", "압수", "재판")
OFFICIAL_HINTS = ("발표", "밝혔다", "설명", "사과", "확인", "공개")
INCIDENT_HINTS = ("발생", "신고", "접수", "부족", "중단", "재개", "확대")


def tone_from_verdict(verdict: str) -> str:
    if verdict in {"사실", "대체로 사실"}:
        return "positive"
    if verdict in {"일부 사실", "근거 부족", "단정 불가", "검증 불가", "업데이트 필요", "초기 기준", "법적 판단 필요", "오해 소지"}:
        return "warning"
    if verdict in {"사실 아님", "과장", "맥락 누락"}:
        return "negative"
    return "neutral"


def _claim_text(claim: models.Claim) -> str:
    return claim.sanitized_text or claim.claim_text


def _article_ref(article: models.Article | None) -> dict[str, Any] | None:
    if not article:
        return None
    return {
        "id": article.id,
        "title": article.title,
        "outlet": article.publisher,
        "publishedAt": to_iso(article.published_at or article.collected_at),
        "url": article.url,
    }


def _evidence_ref(evidence: models.Evidence) -> dict[str, Any]:
    return {
        "id": evidence.id,
        "title": evidence.title,
        "source": evidence.source_domain,
        "sourceType": evidence.source_type,
        "url": evidence.url,
        "credibility": round(evidence.credibility_score, 2),
        "summary": evidence.evidence_text,
    }


def _cluster_conflict(cluster_claims: list[models.Claim]) -> str:
    if not cluster_claims:
        return "아직 비교할 주장이 충분하지 않습니다."
    verdicts = sorted({claim.verdict for claim in cluster_claims if claim.verdict})
    types = sorted({claim.claim_type for claim in cluster_claims if claim.claim_type})
    if len(verdicts) > 1:
        return f"같은 쟁점 안에서 판정이 {', '.join(verdicts[:4])}로 갈립니다."
    if len(types) > 1:
        return f"같은 쟁점 안에 {', '.join(types[:4])} 유형의 주장이 함께 있습니다."
    return "같은 쟁점 안의 주장들이 수치, 시점, 근거 기준으로 비교됩니다."


def _cluster_common_ground(cluster_claims: list[models.Claim], evidences_by_claim: dict[str, list[models.Evidence]]) -> str:
    if not cluster_claims:
        return "공통 기준을 만들 추가 주장이 필요합니다."
    supported = [
        claim
        for claim in cluster_claims
        if claim.verdict in {"사실", "대체로 사실", "일부 사실"} or evidences_by_claim.get(claim.id)
    ]
    if supported:
        return "근거가 연결된 주장부터 확인하고, 근거가 부족한 주장은 별도 검토합니다."
    return "현재 공통분모는 쟁점 자체이며, 공식자료 또는 교차 근거가 더 필요합니다."


def _article_verdict(article_claims: list[models.Claim]) -> tuple[str, str, str]:
    if not article_claims:
        return "분석 대기", "warning", "아직 추출된 주장이 없습니다."
    verdicts = {claim.verdict for claim in article_claims}
    if verdicts & {"업데이트 필요", "초기 기준"}:
        return "업데이트 필요", "warning", "후속 보도나 새 근거 기준으로 다시 봐야 하는 주장이 있습니다."
    if verdicts & {"사실 아님", "과장", "맥락 누락"}:
        return "맥락 점검", "negative", "일부 주장이 근거와 충돌하거나 중요한 맥락이 빠져 있습니다."
    if verdicts and verdicts <= {"사실", "대체로 사실", "일부 사실"}:
        return "주장 단위 검증", "positive", "포함된 주요 주장이 현재 근거와 대체로 일치합니다."
    return "검증 중", "neutral", "포함된 주장을 근거와 대조하고 있습니다."


def _number_values(claim: models.Claim) -> list[str]:
    entities = claim.entities_json or {}
    values = entities.get("numbers") or []
    return [str(value) for value in values if str(value).strip()]


def _timeline_sort_key(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _coerce_event_datetime(
    *,
    day: str,
    hour: str | None,
    minute: str | None,
    month: str,
    reference: datetime,
    year: str | None = None,
) -> datetime | None:
    try:
        parsed_year = int(year) if year else reference.year
        parsed_hour = int(hour) if hour else 0
        if parsed_hour > 23:
            return None
        return datetime(
            parsed_year,
            int(month),
            int(day),
            parsed_hour,
            int(minute) if minute else 0,
            tzinfo=reference.tzinfo or UTC,
        )
    except ValueError:
        return None


def _ampm_hour(hour: str | None, ampm: str | None) -> str | None:
    if hour is None:
        return None
    parsed_hour = int(hour)
    if ampm == "오후" and parsed_hour < 12:
        parsed_hour += 12
    if ampm == "오전" and parsed_hour == 12:
        parsed_hour = 0
    return str(parsed_hour)


def _reported_event_datetime(text: str, *, reference: datetime) -> datetime | None:
    full_date = FULL_DATE_PATTERN.search(text)
    if full_date:
        return _coerce_event_datetime(
            day=full_date.group("day"),
            hour=full_date.group("hour"),
            minute=full_date.group("minute"),
            month=full_date.group("month"),
            reference=reference,
            year=full_date.group("year"),
        )
    korean_date = KOREAN_DATE_PATTERN.search(text)
    if korean_date:
        return _coerce_event_datetime(
            day=korean_date.group("day"),
            hour=_ampm_hour(korean_date.group("hour"), korean_date.group("ampm")),
            minute=korean_date.group("minute"),
            month=korean_date.group("month"),
            reference=reference,
        )
    time_match = TIME_PATTERN.search(text)
    if time_match:
        return _coerce_event_datetime(
            day=str(reference.day),
            hour=_ampm_hour(time_match.group("hour"), time_match.group("ampm")) or time_match.group("hour24"),
            minute=time_match.group("minute") or time_match.group("minute24"),
            month=str(reference.month),
            reference=reference,
            year=str(reference.year),
        )
    return None


def _sentences(text: str) -> list[str]:
    cleaned = normalize_whitespace(text)
    if not cleaned:
        return []
    pieces = re.split(r"(?<=[.!?。！？])\s+|(?<=[다요])\.\s*|\n+", cleaned)
    return [piece.strip(" .") for piece in pieces if len(piece.strip()) >= 8]


def _article_event_reference(article: models.Article) -> datetime:
    return article.published_at or article.collected_at or article.created_at


def _has_event_signal(sentence: str) -> bool:
    return any(hint in sentence for hint in EVENT_HINTS)


def _strip_event_date_prefix(value: str) -> str:
    value = FULL_DATE_PATTERN.sub("", value, count=1).strip(" :·-")
    value = KOREAN_DATE_PATTERN.sub("", value, count=1).strip(" :·-")
    value = TIME_PATTERN.sub("", value, count=1).strip(" :·-")
    return normalize_whitespace(value)


def _timeline_event_type(sentence: str, article: models.Article) -> str:
    source_type = article.source_type or "news"
    if any(hint in sentence for hint in FOLLOWUP_HINTS):
        return "followup_action"
    if source_type.startswith(("official", "public")) or any(hint in sentence for hint in OFFICIAL_HINTS):
        return "official_statement"
    if any(hint in sentence for hint in INCIDENT_HINTS):
        return "incident_event"
    return "reported_event"


def _article_timeline_events(article: models.Article) -> list[tuple[datetime, dict[str, Any]]]:
    reference = _article_event_reference(article)
    text = article.body_text or article.summary or article.title
    publisher = article.publisher or "출처 확인 전"
    events: list[tuple[datetime, dict[str, Any]]] = []
    candidates: list[tuple[datetime | None, str]] = []
    has_explicit_event_time = False
    for sentence in _sentences(text):
        occurred_at = _reported_event_datetime(sentence, reference=reference)
        if not occurred_at and not _has_event_signal(sentence):
            continue
        if occurred_at:
            has_explicit_event_time = True
        candidates.append((occurred_at, sentence))
    for occurred_at, sentence in candidates:
        if has_explicit_event_time and not occurred_at:
            continue
        occurred_at = occurred_at or _timeline_sort_key(reference)
        event_title = _strip_event_date_prefix(sentence) or normalize_whitespace(sentence)
        event_id = hash_text(f"{article.issue_id}:{to_iso(occurred_at)}:{event_title}")[:18]
        events.append(
            (
                occurred_at,
                {
                    "id": f"event:{event_id}",
                    "occurredAt": to_iso(occurred_at),
                    "type": _timeline_event_type(sentence, article),
                    "title": event_title[:120],
                    "description": f"{normalize_whitespace(sentence)} 출처: {publisher}"[:500],
                },
            ),
        )
    return events


def _dedupe_timeline_events(
    timeline_events: list[tuple[datetime, dict[str, Any]]],
) -> list[tuple[datetime, dict[str, Any]]]:
    deduped: list[tuple[datetime, dict[str, Any]]] = []
    for occurred_at, event in sorted(timeline_events, key=lambda row: _timeline_sort_key(row[0])):
        if any(
            abs((_timeline_sort_key(occurred_at) - _timeline_sort_key(existing_at)).total_seconds()) <= 60
            and jaccard_similarity(event["title"], existing["title"]) >= 0.55
            for existing_at, existing in deduped
        ):
            continue
        deduped.append((occurred_at, event))
    return deduped


def _article_sort_key(article: models.Article) -> datetime:
    value = article.published_at or article.collected_at or article.created_at
    return _timeline_sort_key(value)


def _quality_score(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _article_row(
    article: models.Article,
    article_claims: list[models.Claim],
    evidences_by_claim: dict[str, list[models.Evidence]],
) -> dict[str, Any]:
    article_evidences = [
        evidence
        for claim in article_claims
        for evidence in evidences_by_claim.get(claim.id, [])
    ]
    official_count = len(
        [
            evidence
            for evidence in article_evidences
            if evidence.source_type in {"official", "public", "statistics", "law"}
        ],
    )
    outdated_count = len(
        [claim for claim in article_claims if claim.verdict in {"초기 기준", "업데이트 필요"}],
    )
    verdict, tone, note = _article_verdict(article_claims)
    if article.parse_status == "title_only":
        verdict, tone = "업데이트 필요", "warning"
        note = "본문 추출 실패로 제목/요약 기준 분석만 완료했습니다."
    return {
        "id": article.id,
        "title": article.title,
        "outlet": article.publisher,
        "publishedAt": to_iso(article.published_at or article.collected_at),
        "url": article.url,
        "claimCount": len(article_claims),
        "outdatedClaims": outdated_count,
        "officialSourceCount": official_count,
        "verdict": verdict,
        "tone": tone,
        "note": note,
    }


def build_issue_cache_payload(db: Session, *, issue_id: str, use_ai: bool = False) -> tuple[models.Issue | None, dict[str, Any]]:
    issue = db.get(models.Issue, issue_id)
    if not issue:
        return None, {}

    articles = db.scalars(select(models.Article).where(models.Article.issue_id == issue_id)).all()
    articles_by_time = sorted(
        articles,
        key=_article_sort_key,
    )
    articles_for_table = list(reversed(articles_by_time))
    clusters = db.scalars(select(models.ClaimCluster).where(models.ClaimCluster.issue_id == issue_id)).all()
    claims = db.scalars(select(models.Claim).where(models.Claim.issue_id == issue_id)).all()
    claim_ids = [claim.id for claim in claims]
    evidences = (
        db.scalars(select(models.Evidence).where(models.Evidence.claim_id.in_(claim_ids))).all()
        if claim_ids
        else []
    )
    perspectives = db.scalars(select(models.Perspective).where(models.Perspective.issue_id == issue_id)).all()
    update_logs = db.scalars(
        select(models.UpdateLog).where(models.UpdateLog.issue_id == issue_id).order_by(models.UpdateLog.created_at.desc()),
    ).all()
    histories = (
        db.scalars(
            select(models.VerdictHistory)
            .where(models.VerdictHistory.claim_id.in_(claim_ids))
            .order_by(models.VerdictHistory.created_at.desc()),
        ).all()
        if claim_ids
        else []
    )

    articles_by_id = {article.id: article for article in articles}
    claims_by_cluster: dict[str, list[models.Claim]] = defaultdict(list)
    claims_by_article: dict[str, list[models.Claim]] = defaultdict(list)
    for claim in claims:
        if claim.cluster_id:
            claims_by_cluster[claim.cluster_id].append(claim)
        if claim.article_id:
            claims_by_article[claim.article_id].append(claim)
    evidences_by_claim: dict[str, list[models.Evidence]] = defaultdict(list)
    for evidence in evidences:
        evidences_by_claim[evidence.claim_id].append(evidence)
    histories_by_claim: dict[str, list[models.VerdictHistory]] = defaultdict(list)
    for history in histories:
        histories_by_claim[history.claim_id].append(history)

    changed_claims = len(histories)

    cached_claims = [
        {
            "id": claim.id,
            "text": _claim_text(claim),
            "type": claim.claim_type,
            "verdict": claim.verdict,
            "tone": tone_from_verdict(claim.verdict),
            "confidence": round(claim.confidence, 2),
            "evidence": (evidences_by_claim[claim.id][0].title if evidences_by_claim[claim.id] else "근거 확인 중"),
            "status": claim.status,
            "relatedArticles": [
                ref
                for ref in [_article_ref(articles_by_id.get(claim.article_id or ""))]
                if ref
            ],
            "evidences": [_evidence_ref(evidence) for evidence in evidences_by_claim.get(claim.id, [])[:6]],
            "rebuttals": [
                _claim_text(other)
                for other in claims_by_cluster.get(claim.cluster_id or "", [])
                if other.id != claim.id
            ][:4],
            "updateHistory": [
                {
                    "id": history.id,
                    "previousVerdict": history.previous_verdict,
                    "currentVerdict": history.current_verdict,
                    "reason": history.reason,
                    "changedAt": to_iso(history.created_at),
                }
                for history in histories_by_claim.get(claim.id, [])[:6]
            ],
        }
        for claim in claims[:80]
    ]
    cached_clusters = [
        {
            "title": cluster.title,
            "question": cluster.canonical_question,
            "claims": [
                _claim_text(claim)
                for claim in claims_by_cluster.get(cluster.id, [])[:6]
            ],
            "conflict": (
                _cluster_conflict(claims_by_cluster.get(cluster.id, []))
                if len(claims_by_cluster.get(cluster.id, [])) > 1
                else cluster.description or _cluster_conflict(claims_by_cluster.get(cluster.id, []))
            ),
            "commonGround": _cluster_common_ground(claims_by_cluster.get(cluster.id, []), evidences_by_claim),
            "verdict": claims_by_cluster.get(cluster.id, [None])[0].verdict if claims_by_cluster.get(cluster.id) else "근거 부족",
            "tone": tone_from_verdict(
                claims_by_cluster.get(cluster.id, [None])[0].verdict if claims_by_cluster.get(cluster.id) else "근거 부족",
            ),
        }
        for cluster in clusters[:40]
    ]
    cached_evidences = [
        {
            "id": evidence.id,
            "label": evidence.title,
            "source": evidence.source_domain,
            "date": to_iso(evidence.published_at or evidence.created_at),
            "summary": evidence.evidence_text,
            "credibility": round(evidence.credibility_score, 2),
            "url": evidence.url,
            "sourceType": evidence.source_type,
        }
        for evidence in evidences[:80]
    ]
    cached_articles = [
        _article_row(article, claims_by_article.get(article.id, []), evidences_by_claim)
        for article in articles_for_table[:80]
    ]
    cached_perspectives = [
        {
            "name": perspective.name,
            "core": perspective.summary,
            "uses": ", ".join(perspective.core_arguments_json[:3]) if perspective.core_arguments_json else "검증 가능한 주장",
            "challengedBy": ", ".join(perspective.conflicts_json[:3]) if perspective.conflicts_json else "근거 부족 주장",
            "commonGround": ", ".join(perspective.common_ground_json[:3]) if perspective.common_ground_json else "사실관계 확인 필요",
        }
        for perspective in perspectives[:20]
    ]
    timeline_events: list[tuple[datetime, dict[str, Any]]] = []
    for article in articles_by_time[:80]:
        timeline_events.extend(_article_timeline_events(article))
    cached_timeline = [event for _, event in _dedupe_timeline_events(timeline_events)[:120]]
    source_documents_by_url: dict[str, dict[str, Any]] = {}
    for evidence in evidences[:50]:
        source_documents_by_url[evidence.url] = {
            "id": evidence.id,
            "title": evidence.title,
            "publisher": evidence.source_domain,
            "publishedAt": to_iso(evidence.published_at or evidence.created_at),
            "url": evidence.url,
            "sourceType": evidence.source_type,
            "credibility": round(evidence.credibility_score, 2),
        }
    for article in articles[:80]:
        source_documents_by_url.setdefault(
            article.url,
            {
                "id": article.id,
                "title": article.title,
                "publisher": article.publisher,
                "publishedAt": to_iso(article.published_at or article.collected_at),
                "url": article.url,
                "sourceType": article.source_type or "media",
                "credibility": 0.55,
            },
        )
    cached_source_documents = list(source_documents_by_url.values())[:80]
    number_cluster_changes = []
    for cluster in clusters:
        cluster_claims = claims_by_cluster.get(cluster.id, [])
        values: list[str] = []
        for claim in cluster_claims:
            if claim.claim_type != "수치 주장":
                continue
            for value in _number_values(claim):
                if value not in values:
                    values.append(value)
        if len(values) >= 2:
            number_cluster_changes.append(
                {
                    "id": f"numbers:{cluster.id}",
                    "label": cluster.title,
                    "previousValue": values[0],
                    "currentValue": values[-1],
                    "changedAt": to_iso(max((claim.updated_at for claim in cluster_claims), key=_timeline_sort_key)),
                    "source": "주장 클러스터",
                    "note": "같은 쟁점 안에서 서로 다른 수치가 확인되어 비교가 필요합니다.",
                    "tone": "warning",
                },
            )

    cached_number_changes = number_cluster_changes[:20] + [
        {
            "id": history.id,
            "label": "판정 변경",
            "previousValue": history.previous_verdict or "이전 판정 없음",
            "currentValue": history.current_verdict,
            "changedAt": to_iso(history.created_at),
            "source": next(
                (
                    evidence.title
                    for evidence in evidences
                    if history.evidence_id and evidence.id == history.evidence_id
                ),
                "판정 이력",
            ),
            "note": history.reason or "근거 변화에 따라 판정이 갱신되었습니다.",
            "tone": tone_from_verdict(history.current_verdict),
        }
        for history in histories
    ][:20] + [
        {
            "id": log.id,
            "label": log.title,
            "previousValue": "이전 기준",
            "currentValue": log.description,
            "changedAt": to_iso(log.created_at),
            "source": "자동 업데이트",
            "note": log.description,
            "tone": "warning",
        }
        for log in update_logs
        if log.update_type in {"number_changed", "verdict_changed", "official_source"}
    ][:20]
    verified_claims = [claim for claim in claims if claim.status == "verified"]
    confirmed_claims = [claim for claim in verified_claims if claim.verdict in {"사실", "대체로 사실", "일부 사실"}]
    cached_confirmed_facts = [
        {
            "claimId": claim.id,
            "evidenceIds": [evidence.id for evidence in evidences_by_claim.get(claim.id, [])],
            "label": claim.claim_type,
            "text": _claim_text(claim),
            "verdict": claim.verdict,
            "tone": tone_from_verdict(claim.verdict),
        }
        for claim in confirmed_claims[:8]
    ]
    computed_summary = (
        f"{len(articles)}개 기사에서 {len(claims)}개 주장을 추출해 검증 중입니다."
        if not issue.summary and claims
        else ""
    )

    payload = {
        "article_count": len(articles),
        "cluster_count": len(clusters),
        "verified_count": len(verified_claims),
        "needs_review_count": len([claim for claim in claims if claim.status in {"needs_review", "needs_evidence"}]),
        "changed_claims": changed_claims,
        "claims": cached_claims,
        "claim_clusters": cached_clusters,
        "evidences": cached_evidences,
        "articles": cached_articles,
        "perspectives": cached_perspectives,
        "timeline": cached_timeline,
        "source_documents": cached_source_documents,
        "number_changes": cached_number_changes,
        "confirmed_facts": cached_confirmed_facts,
        "computed_summary": computed_summary,
    }
    return issue, synthesize_issue_cache(db, issue=issue, payload=payload, use_ai=use_ai)


def refresh_issue_cache(db: Session, *, issue_id: str) -> models.Issue | None:
    issue, payload = build_issue_cache_payload(db, issue_id=issue_id, use_ai=True)
    if not issue:
        return None

    previous_quality = issue.quality_report_json if isinstance(issue.quality_report_json, dict) else {}
    previous_ai_synthesis = previous_quality.get("aiSynthesis")
    if not isinstance(previous_ai_synthesis, dict):
        previous_ai_synthesis = None

    issue.article_count = payload["article_count"]
    issue.cluster_count = payload["cluster_count"]
    issue.verified_count = payload["verified_count"]
    issue.needs_review_count = payload["needs_review_count"]
    issue.changed_claims = payload["changed_claims"]
    issue.updated_at = models.now_utc()
    issue.last_updated_at = issue.updated_at

    issue.claims = payload["claims"]
    issue.claim_clusters = payload["claim_clusters"]
    issue.evidences = payload["evidences"]
    issue.articles = payload["articles"]
    issue.perspectives = payload["perspectives"]
    issue.timeline = payload["timeline"]
    issue.source_documents = payload["source_documents"]
    issue.number_changes = payload["number_changes"]
    issue.confirmed_facts = payload["confirmed_facts"]
    quality = payload.get("quality")
    if not isinstance(quality, dict):
        quality = {}
    ai_synthesis = payload.get("ai_synthesis")
    if isinstance(ai_synthesis, dict):
        quality = {**quality, "aiSynthesis": ai_synthesis}
    elif previous_ai_synthesis is not None:
        quality = {**quality, "aiSynthesis": previous_ai_synthesis}
    issue.quality_report_json = quality
    issue.quality_score = _quality_score(quality.get("score"))
    if payload.get("computed_summary"):
        issue.summary = payload["computed_summary"]
    db.flush()
    return issue
