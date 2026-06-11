from __future__ import annotations

import re
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.services.admin.settings import get_effective_setting
from app.services.issues.article_quality import issue_relevance_stats, relevant_issue_articles
from app.services.topics import normalize_topic
from app.utils import new_id


HIGH_IMPACT_TOPICS = {"정치", "재난", "보건", "경제", "IT"}

OFFICIAL_SOURCE_TYPES = {"official", "public", "government", "statistics", "law"}
BAD_PARSE_STATUSES = {"failed", "error", "empty", "unsupported"}
NUMBER_PATTERN = re.compile(r"\d+(?:,\d{3})*(?:\.\d+)?")
SUPPORTED_CONFIRMED_VERDICTS = {"사실", "대체로 사실", "일부 사실"}

RETRY_VARIANTS: dict[str, tuple[str, ...]] = {
    "articleCoverage": ("후속", "추가 보도", "종합"),
    "publisherDiversity": ("복수 매체", "후속", "종합"),
    "officialCoverage": ("공식자료", "해명", "설명자료"),
    "claimCoverage": ("쟁점", "주장", "논란"),
    "evidenceCoverage": ("근거", "자료", "팩트체크"),
    "timelineCoverage": ("후속", "감사", "고발", "집회"),
    "numberCoverage": ("수치", "집계", "통계"),
    "confirmedFacts": ("확인", "팩트체크", "검증"),
    "perspectiveCoverage": ("반론", "입장", "쟁점"),
    "parseHealth": ("원문", "전문", "자료"),
    "relevanceCoverage": ("핵심 사건", "대표 기사", "사건 경위"),
}


def _json_rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _source_type(value: Any) -> str:
    return str(value or "").strip().lower()


def _has_official_source_type(value: Any) -> bool:
    source_type = _source_type(value)
    return source_type in OFFICIAL_SOURCE_TYPES or source_type.startswith(("official", "public"))


def _has_text(value: Any) -> bool:
    return bool(str(value or "").strip())


def _article_count(issue: models.Issue, articles: list[models.Article]) -> int:
    return max(len(articles), int(issue.article_count or 0), len(_json_rows(issue.articles)))


def _publisher_names(issue: models.Issue, articles: list[models.Article]) -> set[str]:
    names = {article.publisher.strip() for article in articles if article.publisher and article.publisher.strip()}
    for row in _json_rows(issue.articles):
        publisher = str(row.get("publisher") or row.get("outlet") or "").strip()
        if publisher:
            names.add(publisher)
    return names


def _official_source_count(
    issue: models.Issue,
    articles: list[models.Article],
    evidences: list[models.Evidence],
) -> int:
    count = sum(1 for article in articles if _has_official_source_type(article.source_type))
    count += sum(1 for evidence in evidences if _has_official_source_type(evidence.source_type))
    for row in _json_rows(issue.source_documents):
        if _has_official_source_type(row.get("sourceType") or row.get("source_type")):
            count += 1
    for row in _json_rows(issue.articles):
        count += int(row.get("officialSourceCount") or 0)
        if _has_official_source_type(row.get("sourceType") or row.get("source_type")):
            count += 1
    return count


def _number_signal_count(issue: models.Issue, articles: list[models.Article], claims: list[models.Claim]) -> int:
    count = len(_json_rows(issue.number_changes))
    for claim in claims:
        entities = claim.entities_json or {}
        count += len([value for value in entities.get("numbers", []) if str(value).strip()])
    for row in _json_rows(issue.claims):
        entities = row.get("entities") or row.get("entities_json") or {}
        if isinstance(entities, dict):
            count += len([value for value in entities.get("numbers", []) if str(value).strip()])
    text = " ".join(
        [
            issue.title or "",
            issue.summary or "",
            *[article.title or "" for article in articles],
            *[article.summary or "" for article in articles],
            *[article.body_text[:500] for article in articles],
        ],
    )
    return count + len(NUMBER_PATTERN.findall(text))


def _parse_health(articles: list[models.Article]) -> dict[str, int]:
    bad = 0
    parsed = 0
    pending = 0
    for article in articles:
        status = _source_type(article.parse_status)
        if status in BAD_PARSE_STATUSES:
            bad += 1
        elif status in {"parsed", "completed", "ok"} or _has_text(article.body_text):
            parsed += 1
        else:
            pending += 1
    return {"bad": bad, "parsed": parsed, "pending": pending}


def _db_grounded_confirmed_fact_count(claims: list[models.Claim], evidences: list[models.Evidence]) -> int:
    evidence_claim_ids = {evidence.claim_id for evidence in evidences}
    return len(
        [
            claim
            for claim in claims
            if claim.id in evidence_claim_ids
            and claim.status == "verified"
            and claim.verdict in SUPPORTED_CONFIRMED_VERDICTS
        ],
    )


def _is_future(value: Any, now: Any) -> bool:
    if value is None:
        return False
    if value.tzinfo is None:
        value = value.replace(tzinfo=now.tzinfo)
    return value > now


def _quality_retry_keywords(db: Session, issue_id: str) -> list[models.SearchKeyword]:
    return db.scalars(
        select(models.SearchKeyword).where(
            models.SearchKeyword.issue_id == issue_id,
            models.SearchKeyword.source == "quality_retry",
        ),
    ).all()


def _active_quality_retry_keywords(db: Session, issue_id: str) -> list[models.SearchKeyword]:
    return [
        keyword
        for keyword in _quality_retry_keywords(db, issue_id)
        if keyword.status == "active"
    ]


def _deactivate_quality_retry_keywords(db: Session, issue_id: str, *, reason: str) -> None:
    now = models.now_utc()
    for keyword in _quality_retry_keywords(db, issue_id):
        keyword.status = "inactive"
        keyword.metadata_json = {
            **(keyword.metadata_json or {}),
            "deactivated_reason": reason,
            "deactivated_at": now.isoformat(),
        }
        keyword.updated_at = now


def _has_pending_retry_wave(db: Session, *, issue: models.Issue, now: Any) -> bool:
    if _is_future(issue.next_quality_retry_at, now):
        return True
    keyword_ids = [keyword.id for keyword in _active_quality_retry_keywords(db, issue.id)]
    if not keyword_ids:
        return False
    return bool(
        db.scalar(
            select(models.JobAttempt.id).where(
                models.JobAttempt.job_type == "search_news",
                models.JobAttempt.target_id.in_(keyword_ids),
                models.JobAttempt.status.in_(["queued", "running"]),
            ),
        ),
    )


def build_issue_quality_report(db: Session, *, issue: models.Issue) -> dict[str, Any]:
    articles = db.scalars(select(models.Article).where(models.Article.issue_id == issue.id)).all()
    claims = db.scalars(select(models.Claim).where(models.Claim.issue_id == issue.id)).all()
    claim_ids = [claim.id for claim in claims]
    evidences = (
        db.scalars(select(models.Evidence).where(models.Evidence.claim_id.in_(claim_ids))).all()
        if claim_ids
        else []
    )

    min_articles = int(get_effective_setting(db, "issue_quality_min_articles") or 4)
    min_publishers = int(get_effective_setting(db, "issue_quality_min_publishers") or 2)
    relevant_articles = relevant_issue_articles(issue, articles)
    relevance = issue_relevance_stats(issue, articles)
    if articles:
        article_count = len(relevant_articles)
        articles_for_signals = relevant_articles
    else:
        article_count = _article_count(issue, articles)
        articles_for_signals = articles
    publishers = _publisher_names(issue, articles_for_signals)
    official_count = _official_source_count(issue, articles_for_signals, evidences)
    claim_count = max(len(claims), len(_json_rows(issue.claims)), len(_json_rows(issue.claim_clusters)))
    evidence_count = max(len(evidences), len(_json_rows(issue.evidences)), len(_json_rows(issue.source_documents)))
    confirmed_fact_count = max(
        len(_json_rows(issue.confirmed_facts)),
        _db_grounded_confirmed_fact_count(claims, evidences),
    )
    perspective_count = len(_json_rows(issue.perspectives))
    timeline_count = len(_json_rows(issue.timeline))
    number_count = _number_signal_count(issue, articles_for_signals, claims)
    parse_health = _parse_health(articles_for_signals)

    missing: list[str] = []
    if articles and (
        relevance["relevantArticleCount"] < min_articles
        or (relevance["totalArticleCount"] >= min_articles and relevance["relevanceRatio"] < 0.5)
    ):
        missing.append("relevanceCoverage")
    if article_count < min_articles:
        missing.append("articleCoverage")
    if len(publishers) < min_publishers:
        missing.append("publisherDiversity")
    if official_count == 0:
        missing.append("officialCoverage")
    if claim_count == 0:
        missing.append("claimCoverage")
    if evidence_count == 0 and claim_count > 0:
        missing.append("evidenceCoverage")
    if confirmed_fact_count == 0 and (claim_count > 0 or evidence_count > 0):
        missing.append("confirmedFacts")
    if perspective_count == 0 and claim_count > 1:
        missing.append("perspectiveCoverage")
    if timeline_count == 0 and issue.topic in HIGH_IMPACT_TOPICS:
        missing.append("timelineCoverage")
    if number_count > 0 and not _json_rows(issue.number_changes):
        missing.append("numberCoverage")
    if parse_health["bad"] > 0 or (article_count > 0 and parse_health["parsed"] == 0):
        missing.append("parseHealth")

    score = 100
    if "relevanceCoverage" in missing:
        score -= 24
    score -= max(0, min_articles - article_count) * 8
    score -= max(0, min_publishers - len(publishers)) * 8
    score -= 14 if official_count == 0 else 0
    score -= 24 if claim_count == 0 else 0
    score -= 10 if evidence_count == 0 and claim_count > 0 else 0
    score -= 8 if confirmed_fact_count == 0 and (claim_count > 0 or evidence_count > 0) else 0
    score -= 6 if perspective_count == 0 and claim_count > 1 else 0
    score -= 8 if timeline_count == 0 and issue.topic in HIGH_IMPACT_TOPICS else 0
    score -= 6 if number_count > 0 and not _json_rows(issue.number_changes) else 0
    score -= min(parse_health["bad"] * 10, 20)
    score = max(0, min(100, int(score)))

    return {
        "score": score,
        "missingSignals": missing,
        "signals": {
            "articleCount": article_count,
            "publisherCount": len(publishers),
            "officialSourceCount": official_count,
            "claimCount": claim_count,
            "evidenceCount": evidence_count,
            "confirmedFactCount": confirmed_fact_count,
            "perspectiveCount": perspective_count,
            "timelineCount": timeline_count,
            "numberSignalCount": number_count,
            "parseHealth": parse_health,
            "relevance": relevance,
        },
    }


def _max_attempts(db: Session, issue: models.Issue) -> int:
    key = "issue_quality_high_impact_max_attempts" if issue.topic in HIGH_IMPACT_TOPICS else "issue_quality_max_attempts"
    return int(get_effective_setting(db, key) or 0)


def _base_queries(issue: models.Issue) -> list[str]:
    values = [issue.title]
    seen: set[str] = set()
    queries: list[str] = []
    for value in values:
        query = str(value or "").strip()
        if len(query) < 2 or query in seen:
            continue
        seen.add(query)
        queries.append(query)
    return queries or [issue.id]


def _retry_queries(issue: models.Issue, missing_signals: list[str]) -> list[tuple[str, str]]:
    queries: list[tuple[str, str]] = []
    seen: set[str] = set()
    for base in _base_queries(issue):
        for signal in missing_signals:
            variants = RETRY_VARIANTS.get(signal, ())
            for variant in variants:
                query = f"{base} {variant}".strip()[:300]
                if query in seen:
                    continue
                seen.add(query)
                queries.append((signal, query))
    return queries[:18]


def _storage_query(issue: models.Issue, query: str) -> str:
    suffix = f" [issue:{issue.id}]"
    return f"{query[: 300 - len(suffix)]}{suffix}"


def _upsert_quality_retry_keyword(
    db: Session,
    *,
    cooldown: int,
    issue: models.Issue,
    query: str,
    signal: str,
) -> models.SearchKeyword:
    storage_query = _storage_query(issue, query)
    keyword = db.scalar(select(models.SearchKeyword).where(models.SearchKeyword.query == storage_query))
    metadata = {
        "quality_issue_id": issue.id,
        "quality_missing_signal": signal,
        "quality_attempt": issue.quality_attempts,
        "search_queries": [query],
    }
    if keyword:
        if keyword.issue_id and keyword.issue_id != issue.id:
            storage_query = _storage_query(issue, f"{query} {signal}")
            keyword = db.scalar(select(models.SearchKeyword).where(models.SearchKeyword.query == storage_query))
        if keyword:
            keyword.issue_id = issue.id
            keyword.metadata_json = {**(keyword.metadata_json or {}), **metadata}
            keyword.priority = "high" if issue.topic in HIGH_IMPACT_TOPICS else "normal"
            keyword.search_interval_minutes = max(1, cooldown)
            keyword.seed_query = issue.title
            keyword.source = "quality_retry"
            keyword.status = "active"
            keyword.topic = normalize_topic(issue.topic)
            keyword.updated_at = models.now_utc()
            db.flush()
            return keyword

    keyword = models.SearchKeyword(
        id=new_id("keyword"),
        issue_id=issue.id,
        metadata_json=metadata,
        priority="high" if issue.topic in HIGH_IMPACT_TOPICS else "normal",
        query=storage_query,
        search_interval_minutes=max(1, cooldown),
        seed_query=issue.title,
        source="quality_retry",
        status="active",
        topic=normalize_topic(issue.topic),
    )
    db.add(keyword)
    db.flush()
    return keyword


def assess_issue_quality(db: Session, *, issue_id: str) -> dict[str, Any]:
    issue = db.get(models.Issue, issue_id)
    if not issue:
        return {"status": "not_found", "missingSignals": [], "score": 0}

    report = build_issue_quality_report(db, issue=issue)
    now = models.now_utc()
    missing_signals = list(report.get("missingSignals") or [])
    issue.quality_score = int(report["score"])
    issue.last_quality_checked_at = now

    if not missing_signals:
        issue.quality_status = "sufficient"
        issue.quality_report_json = report
        issue.next_quality_retry_at = None
        issue.updated_at = now
        _deactivate_quality_retry_keywords(db, issue.id, reason="sufficient")
        db.flush()
        return report | {"status": "sufficient"}

    if issue.quality_status == "needs_retry" and _has_pending_retry_wave(db, issue=issue, now=now):
        issue.quality_report_json = report
        issue.updated_at = now
        db.flush()
        return report | {"status": "retry_pending"}

    max_attempts = _max_attempts(db, issue)
    if int(issue.quality_attempts or 0) >= max_attempts:
        issue.quality_status = "exhausted"
        issue.quality_report_json = report
        issue.next_quality_retry_at = None
        issue.updated_at = now
        _deactivate_quality_retry_keywords(db, issue.id, reason="exhausted")
        db.flush()
        return report | {"status": "exhausted"}

    issue.quality_attempts = int(issue.quality_attempts or 0) + 1
    issue.quality_status = "needs_retry"
    cooldown = int(get_effective_setting(db, "issue_quality_retry_cooldown_minutes") or 30)
    issue.next_quality_retry_at = now + timedelta(minutes=max(1, cooldown))
    issue.updated_at = now
    report["researchTrigger"] = {
        "issueId": issue.id,
        "missingSignals": missing_signals,
        "reason": "quality_gap",
        "status": "queued",
    }
    issue.quality_report_json = report

    for signal, query in _retry_queries(issue, missing_signals):
        _upsert_quality_retry_keyword(
            db,
            cooldown=cooldown,
            issue=issue,
            query=query,
            signal=signal,
        )

    db.flush()
    return report | {"status": "needs_retry"}
