from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app import models
from app.services.claims.clusterer import rebuild_issue_claim_clusters
from app.services.images.candidates import link_image_candidates_to_issue_with_previous, upsert_image_candidate
from app.services.images.selector import select_representative_image
from app.services.issues.page_builder import refresh_issue_cache
from app.services.topics import normalize_topic


def hide_issue(db: Session, *, issue_id: str) -> models.Issue | None:
    issue = db.get(models.Issue, issue_id)
    if issue:
        issue.is_public = False
        issue.status = "숨김"
    queue = db.get(models.AdminQueueItem, issue_id)
    if queue:
        queue.status = "숨김"
    db.flush()
    return issue


def set_manual_representative_image(
    db: Session,
    *,
    issue_id: str,
    source: str = "",
    source_url: str = "",
    url: str,
) -> models.ImageCandidate:
    issue = db.get(models.Issue, issue_id)
    if not issue:
        raise ValueError("issue not found")
    candidate = upsert_image_candidate(
        db,
        issue_id=issue.id,
        publisher=source or "수동 지정",
        source_type="manual",
        source_url=source_url,
        url=url,
    )
    if not candidate:
        raise ValueError("invalid image url")
    candidate.status = "selected"
    candidate.confidence = 1.0
    candidate.reason = "수동 지정 대표 이미지"
    candidate.updated_at = models.now_utc()
    issue.representative_image_url = candidate.url
    issue.representative_image_source = candidate.publisher
    issue.representative_image_source_url = candidate.source_url
    issue.representative_image_confidence = 1.0
    issue.representative_image_updated_at = models.now_utc()
    issue.updated_at = models.now_utc()
    refresh_issue_cache(db, issue_id=issue.id)
    db.flush()
    return candidate


def merge_issue(db: Session, *, source_issue_id: str, target_issue_id: str) -> models.Issue:
    source = db.get(models.Issue, source_issue_id)
    target = db.get(models.Issue, target_issue_id)
    if not source or not target:
        raise ValueError("issue not found")
    moved_article_ids = db.scalars(select(models.Article.id).where(models.Article.issue_id == source_issue_id)).all()
    db.execute(update(models.Article).where(models.Article.issue_id == source_issue_id).values(issue_id=target_issue_id))
    db.execute(update(models.Claim).where(models.Claim.issue_id == source_issue_id).values(issue_id=target_issue_id))
    db.execute(update(models.ClaimCluster).where(models.ClaimCluster.issue_id == source_issue_id).values(issue_id=target_issue_id))
    db.execute(update(models.SearchKeyword).where(models.SearchKeyword.issue_id == source_issue_id).values(issue_id=target_issue_id))
    db.execute(update(models.DiscoveredIncident).where(models.DiscoveredIncident.issue_id == source_issue_id).values(issue_id=target_issue_id))
    db.execute(update(models.UpdateLog).where(models.UpdateLog.issue_id == source_issue_id).values(issue_id=target_issue_id))
    db.execute(update(models.Perspective).where(models.Perspective.issue_id == source_issue_id).values(issue_id=target_issue_id))
    db.execute(update(models.AgentRun).where(models.AgentRun.issue_id == source_issue_id).values(issue_id=target_issue_id))
    db.execute(update(models.Notification).where(models.Notification.issue_id == source_issue_id).values(issue_id=target_issue_id))
    db.execute(update(models.IssueReport).where(models.IssueReport.issue_id == source_issue_id).values(issue_id=target_issue_id))
    db.execute(update(models.SubmittedClaim).where(models.SubmittedClaim.issue_id == source_issue_id).values(issue_id=target_issue_id))
    db.execute(update(models.ModerationReport).where(models.ModerationReport.issue_id == source_issue_id).values(issue_id=target_issue_id))
    db.execute(update(models.ProductMetricEvent).where(models.ProductMetricEvent.issue_id == source_issue_id).values(issue_id=target_issue_id))
    db.execute(update(models.VerificationRequest).where(models.VerificationRequest.issue_id == source_issue_id).values(issue_id=target_issue_id))
    db.execute(
        update(models.VerificationRequest)
        .where(models.VerificationRequest.matched_issue_id == source_issue_id)
        .values(matched_issue_id=target_issue_id),
    )
    db.execute(
        update(models.VerificationRequest)
        .where(models.VerificationRequest.result_issue_id == source_issue_id)
        .values(result_issue_id=target_issue_id),
    )

    saved_rows = db.scalars(select(models.SavedIssue).where(models.SavedIssue.issue_id == source_issue_id)).all()
    for saved in saved_rows:
        already_saved = db.get(models.SavedIssue, {"user_id": saved.user_id, "issue_id": target_issue_id})
        if already_saved:
            db.delete(saved)
        else:
            saved.issue_id = target_issue_id

    target.issue_score = max(target.issue_score, source.issue_score)
    target.risk = "고영향" if "고영향" in {target.risk, source.risk} else target.risk
    source.is_public = False
    source.status = "병합됨"
    previous_issue_ids: set[str] = set()
    source_image_candidates = db.scalars(
        select(models.ImageCandidate).where(models.ImageCandidate.issue_id == source_issue_id),
    ).all()
    for candidate in source_image_candidates:
        if candidate.issue_id and candidate.issue_id != target_issue_id:
            previous_issue_ids.add(candidate.issue_id)
        candidate.issue_id = target_issue_id
        candidate.updated_at = models.now_utc()
    for article_id in moved_article_ids:
        _, previous = link_image_candidates_to_issue_with_previous(db, article_id=article_id, issue_id=target_issue_id)
        previous_issue_ids.update(previous)
    select_representative_image(db, issue_id=target_issue_id)
    for previous_issue_id in previous_issue_ids:
        if previous_issue_id != target_issue_id:
            select_representative_image(db, issue_id=previous_issue_id)
    rebuild_issue_claim_clusters(db, issue_id=target_issue_id)
    refresh_issue_cache(db, issue_id=target_issue_id)
    db.flush()
    return target


def split_article_to_issue(db: Session, *, article_id: str, title: str, topic: str) -> models.Issue:
    article = db.get(models.Article, article_id)
    if not article:
        raise ValueError("article not found")
    issue = models.Issue(
        id=f"issue_split_{article.id[-12:]}",
        is_public=False,
        status="검토 대기",
        summary="분리된 기사에서 새 이슈 후보를 만들었습니다.",
        title=title,
        topic=normalize_topic(topic),
    )
    issue = db.merge(issue)
    article.issue_id = issue.id
    db.execute(update(models.Claim).where(models.Claim.article_id == article_id).values(issue_id=issue.id))
    _, previous_issue_ids = link_image_candidates_to_issue_with_previous(db, article_id=article_id, issue_id=issue.id)
    select_representative_image(db, issue_id=issue.id)
    for previous_issue_id in previous_issue_ids:
        select_representative_image(db, issue_id=previous_issue_id)
    refresh_issue_cache(db, issue_id=issue.id)
    db.flush()
    return issue
