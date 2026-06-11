from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.services.classification.taxonomy import classify_issue_taxonomy, infer_event_group_name, infer_major_topic_name
from app.services.articles.normalizer import normalize_whitespace
from app.services.issues.article_quality import cleanup_redundant_parse_jobs, should_attach_article_to_issue
from app.services.issues.importance import apply_issue_importance
from app.services.issues.page_builder import build_issue_cache_payload
from app.services.issues.quality import assess_issue_quality
from app.services.issues.scoring import infer_topic


ISSUE_SUFFIX_RE = re.compile(r"\s*\[issue:[^\]]+\]\s*$")


def _compact(value: str) -> str:
    return re.sub(r"[^0-9a-zA-Z가-힣]+", "", value).lower()


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _article_has_claims(db: Session, article_id: str) -> bool:
    return bool(db.scalar(select(models.Claim.id).where(models.Claim.article_id == article_id).limit(1)))


def _keyword_query_text(keyword: models.SearchKeyword) -> str:
    return normalize_whitespace(ISSUE_SUFFIX_RE.sub("", keyword.query or ""))


def _keyword_contains_issue_title(keyword: models.SearchKeyword, issue: models.Issue) -> bool:
    title = _compact(issue.title or "")
    if not title:
        return True
    if title in _compact(_keyword_query_text(keyword)):
        return True
    metadata = keyword.metadata_json if isinstance(keyword.metadata_json, dict) else {}
    for query in metadata.get("search_queries") or []:
        if title in _compact(str(query or "")):
            return True
    return False


def _deactivate_broad_retry_keywords(
    db: Session,
    *,
    apply: bool,
    issue_ids: set[str],
    samples: list[dict[str, str]],
) -> int:
    keywords = db.scalars(
        select(models.SearchKeyword).where(
            models.SearchKeyword.source == "quality_retry",
            models.SearchKeyword.status == "active",
            models.SearchKeyword.issue_id.is_not(None),
        ),
    ).all()
    count = 0
    now = models.now_utc()
    for keyword in keywords:
        if not keyword.issue_id:
            continue
        issue = db.get(models.Issue, keyword.issue_id)
        if not issue or _keyword_contains_issue_title(keyword, issue):
            continue
        count += 1
        issue_ids.add(issue.id)
        if len(samples) < 12:
            samples.append({"issueId": issue.id, "keywordId": keyword.id, "query": keyword.query})
        if not apply:
            continue
        keyword.status = "inactive"
        keyword.metadata_json = {
            **(keyword.metadata_json or {}),
            "deactivated_reason": "broad_quality_retry_keyword",
            "deactivated_at": now.isoformat(),
            "repair": "information_quality",
        }
        keyword.updated_at = now
    return count


def _rebuild_issue_cache(db: Session, *, issue_id: str) -> bool:
    issue, payload = build_issue_cache_payload(db, issue_id=issue_id, use_ai=False)
    if not issue:
        return False

    previous_quality = issue.quality_report_json if isinstance(issue.quality_report_json, dict) else {}
    previous_ai_synthesis = previous_quality.get("aiSynthesis")
    if not isinstance(previous_ai_synthesis, dict):
        previous_ai_synthesis = None

    issue.article_count = _safe_int(payload.get("article_count"))
    issue.cluster_count = _safe_int(payload.get("cluster_count"))
    issue.verified_count = _safe_int(payload.get("verified_count"))
    issue.needs_review_count = _safe_int(payload.get("needs_review_count"))
    issue.changed_claims = _safe_int(payload.get("changed_claims"))
    issue.claims = payload.get("claims") or []
    issue.claim_clusters = payload.get("claim_clusters") or []
    issue.evidences = payload.get("evidences") or []
    issue.articles = payload.get("articles") or []
    issue.perspectives = payload.get("perspectives") or []
    issue.timeline = payload.get("timeline") or []
    issue.source_documents = payload.get("source_documents") or []
    issue.number_changes = payload.get("number_changes") or []
    issue.confirmed_facts = payload.get("confirmed_facts") or []

    quality = payload.get("quality") if isinstance(payload.get("quality"), dict) else {}
    if previous_ai_synthesis is not None:
        quality = {**quality, "aiSynthesis": previous_ai_synthesis}
    issue.quality_report_json = quality
    issue.quality_score = _safe_int(quality.get("score"))
    if payload.get("computed_summary"):
        issue.summary = str(payload["computed_summary"])
    issue.updated_at = models.now_utc()
    issue.last_updated_at = issue.updated_at
    return True


def _issue_topic_text(db: Session, issue: models.Issue) -> str:
    article_rows = db.scalars(
        select(models.Article)
        .where(models.Article.issue_id == issue.id)
        .order_by(models.Article.published_at.desc().nullslast(), models.Article.collected_at.desc())
        .limit(12),
    ).all()
    article_text = " ".join(
        normalize_whitespace(f"{article.title} {article.summary} {article.body_text[:240]}")
        for article in article_rows
    )
    title_signal = " ".join([issue.title or ""] * 4)
    summary_signal = " ".join([issue.summary or ""] * 2)
    return normalize_whitespace(f"{title_signal} {summary_signal} {article_text}")


def _reclassify_issue_taxonomy(db: Session, issue: models.Issue) -> bool:
    before = (issue.topic, issue.major_topic_name, issue.event_group_name, issue.major_topic_id, issue.event_group_id)
    text = _issue_topic_text(db, issue)
    topic = infer_topic(text or issue.title)
    major_topic_name = infer_major_topic_name(issue.title or text)
    if major_topic_name != "2026 지방선거":
        major_topic_name = f"{topic} 주요 이슈"
    event_group_name = infer_event_group_name(issue.title or text)
    classify_issue_taxonomy(
        db,
        event_group_name=event_group_name,
        issue=issue,
        major_topic_name=major_topic_name,
        summary=issue.summary,
        title=issue.title,
    )
    event_group = db.get(models.EventGroup, issue.event_group_id) if issue.event_group_id else None
    if event_group and event_group.name != event_group_name:
        event_group.name = event_group_name
        event_group.summary = text[:500]
        event_group.signal_json = {
            **(event_group.signal_json or {}),
            "repair": "information_quality",
            "repairedEventGroupName": event_group_name,
        }
        event_group.updated_at = models.now_utc()
        issue.event_group_name = event_group_name
    after = (issue.topic, issue.major_topic_name, issue.event_group_name, issue.major_topic_id, issue.event_group_id)
    return before != after


def _detach_contaminated_articles(
    db: Session,
    *,
    apply: bool,
    issue_ids: set[str],
    samples: list[dict[str, str]],
    skipped_samples: list[dict[str, str]],
) -> dict[str, int]:
    detached = 0
    skipped_claim_linked = 0
    images_detached = 0
    now = models.now_utc()
    articles = db.scalars(
        select(models.Article).where(
            models.Article.issue_id.is_not(None),
            models.Article.issue_id != "",
        ),
    ).all()
    issues_by_id: dict[str, models.Issue] = {}
    for article in articles:
        if not article.issue_id:
            continue
        issue = issues_by_id.get(article.issue_id)
        if issue is None:
            issue = db.get(models.Issue, article.issue_id)
            if issue is None:
                continue
            issues_by_id[article.issue_id] = issue
        should_attach, reason = should_attach_article_to_issue(
            db,
            article=article,
            content_hash=article.content_hash,
            issue=issue,
        )
        if should_attach:
            continue
        issue_ids.add(issue.id)
        if _article_has_claims(db, article.id):
            skipped_claim_linked += 1
            if len(skipped_samples) < 12:
                skipped_samples.append({"issueId": issue.id, "articleId": article.id, "reason": reason})
            continue
        detached += 1
        if len(samples) < 12:
            samples.append({"issueId": issue.id, "articleId": article.id, "reason": reason, "title": article.title})
        if not apply:
            continue
        article.ai_notes = {
            **(article.ai_notes or {}),
            "qualityRepair": {
                "detachedFromIssueId": issue.id,
                "detachedAt": now.isoformat(),
                "reason": reason,
            },
        }
        article.issue_id = None
        article.updated_at = now
        candidates = db.scalars(
            select(models.ImageCandidate).where(
                models.ImageCandidate.article_id == article.id,
                models.ImageCandidate.issue_id == issue.id,
            ),
        ).all()
        for candidate in candidates:
            candidate.issue_id = None
            candidate.updated_at = now
            images_detached += 1
    return {
        "detachedArticles": detached,
        "skippedClaimLinkedArticles": skipped_claim_linked,
        "detachedImageCandidates": images_detached,
    }


def _issue_ids_for_rebuild(db: Session, *, rebuild_all: bool, affected_issue_ids: set[str], limit: int | None) -> list[str]:
    if rebuild_all:
        query = select(models.Issue.id).order_by(models.Issue.updated_at.desc())
        if limit is not None:
            query = query.limit(limit)
        return list(db.scalars(query).all())
    ids = sorted(affected_issue_ids)
    if limit is not None:
        ids = ids[:limit]
    return ids


def repair_information_quality(
    db: Session,
    *,
    apply: bool = False,
    rebuild_all: bool = True,
    limit: int | None = None,
) -> dict[str, Any]:
    affected_issue_ids: set[str] = set()
    detached_samples: list[dict[str, str]] = []
    skipped_samples: list[dict[str, str]] = []
    keyword_samples: list[dict[str, str]] = []

    article_result = _detach_contaminated_articles(
        db,
        apply=apply,
        issue_ids=affected_issue_ids,
        samples=detached_samples,
        skipped_samples=skipped_samples,
    )
    keyword_count = _deactivate_broad_retry_keywords(
        db,
        apply=apply,
        issue_ids=affected_issue_ids,
        samples=keyword_samples,
    )
    if apply:
        db.flush()
    parse_jobs = cleanup_redundant_parse_jobs(db) if apply else {"completed": 0}
    if apply:
        db.flush()

    rebuilt = 0
    reassessed = 0
    retry_needed = 0
    sufficient = 0
    taxonomy_updated = 0
    importance_updated = 0
    for issue_id in _issue_ids_for_rebuild(db, rebuild_all=rebuild_all, affected_issue_ids=affected_issue_ids, limit=limit):
        issue = db.get(models.Issue, issue_id)
        if apply and issue and _reclassify_issue_taxonomy(db, issue):
            taxonomy_updated += 1
        if apply and issue_id in affected_issue_ids:
            issue = db.get(models.Issue, issue_id)
            if issue:
                issue.quality_attempts = 0
                issue.next_quality_retry_at = None
                issue.quality_status = "unchecked"
        if not apply:
            rebuilt += 1
            continue
        if not _rebuild_issue_cache(db, issue_id=issue_id):
            continue
        rebuilt += 1
        result = assess_issue_quality(db, issue_id=issue_id)
        reassessed += 1
        if result.get("status") == "sufficient":
            sufficient += 1
        else:
            retry_needed += 1
        issue = db.get(models.Issue, issue_id)
        if issue:
            previous = (issue.issue_score, issue.risk)
            apply_issue_importance(issue)
            if previous != (issue.issue_score, issue.risk):
                importance_updated += 1

    return {
        **article_result,
        "parseJobsCompleted": int(parse_jobs.get("completed") or 0),
        "broadRetryKeywordsDeactivated": keyword_count,
        "issuesRebuilt": rebuilt,
        "issuesReassessed": reassessed,
        "issuesSufficient": sufficient,
        "issuesNeedingRetry": retry_needed,
        "taxonomyUpdated": taxonomy_updated,
        "importanceUpdated": importance_updated,
        "affectedIssueCount": len(affected_issue_ids),
        "detachedSamples": detached_samples,
        "skippedClaimLinkedSamples": skipped_samples,
        "broadRetryKeywordSamples": keyword_samples,
    }
