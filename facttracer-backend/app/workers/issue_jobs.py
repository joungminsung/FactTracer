from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app.collectors.base import CollectedArticle
from app.collectors.news_search import collect_google_news_search, collect_json_news
from app.collectors.official_sources import collect_official_source
from app.collectors.rss import collect_rss
from app.collectors.social import collect_public_social_candidates
from app.collectors.youtube import collect_youtube_candidates
from app.db.session import SessionLocal
from app.services.admin.settings import get_effective_setting
from app.services.articles.deduplicator import upsert_article
from app.services.articles.normalizer import hash_text
from app.services.articles.parser import fetch_and_parse_url, parse_article_content
from app.services.audit.logger import record_agent_run
from app.services.ai.deepseek_client import DeepSeekAnalysisService
from app.services.classification.taxonomy import classify_issue_taxonomy
from app.services.claims.workflow import extract_claims_for_article
from app.services.discovery.incident_detector import (
    cluster_collected_articles,
    define_incident,
    upsert_discovered_incident,
)
from app.services.issues.detector import detect_or_match_issue
from app.services.issues.article_quality import should_attach_article_to_issue
from app.services.issues.matcher import find_similar_issue
from app.services.issues.page_builder import refresh_issue_cache
from app.services.issues.publisher import slugify
from app.services.images.candidates import (
    link_image_candidates_to_issue,
    link_image_candidates_to_issue_with_previous,
    persist_parsed_image_candidates,
    upsert_image_candidate,
)
from app.services.images.selector import select_representative_image
from app.services.notifications.events import notify_update_log
from app.services.perspectives.mapper import rebuild_perspectives
from app.services.podcasts.corrections import apply_podcast_correction_policy
from app.services.search.keywords import fallback_keyword_variants, upsert_search_keyword
from app.services.topics import normalize_topic
from app.services.verification.verifier import verify_claim as verify_claim_record
from app.utils import new_id


logger = logging.getLogger(__name__)


def create_update_log(
    db: Session,
    *,
    description: str,
    issue_id: str,
    related_article_id: str | None = None,
    related_claim_id: str | None = None,
    title: str,
    update_type: str,
) -> models.UpdateLog:
    log = models.UpdateLog(
        description=description,
        id=new_id("update"),
        issue_id=issue_id,
        related_article_id=related_article_id,
        related_claim_id=related_claim_id,
        title=title,
        update_type=update_type,
    )
    db.add(log)
    db.flush()
    notify_update_log(db, update_log=log)
    apply_podcast_correction_policy(
        db,
        description=description,
        issue_id=issue_id,
        title=title,
        update_log_id=log.id,
        update_type=update_type,
    )
    return log


def _classify_issue_best_effort(
    db: Session,
    *,
    event_group_name: str | None = None,
    issue: models.Issue,
    major_topic_name: str | None = None,
    title: str = "",
    summary: str = "",
) -> bool:
    try:
        with db.begin_nested():
            try:
                classify_issue_taxonomy(
                    db,
                    event_group_name=event_group_name,
                    issue=issue,
                    major_topic_name=major_topic_name,
                    summary=summary,
                    title=title,
                )
            except TypeError as exc:
                if "unexpected keyword argument" not in str(exc):
                    raise
                classify_issue_taxonomy(db, issue=issue, title=title, summary=summary)
        return True
    except Exception as exc:
        logger.exception("Issue taxonomy classification failed for %s", issue.id)
        try:
            db.expire(issue)
        except Exception:
            pass
        try:
            record_agent_run(
                db,
                agent="Taxonomy Classifier",
                error_message=str(exc),
                issue_id=issue.id,
                input_json={"summary": summary, "title": title},
                status="failed",
                target=issue.title,
            )
        except Exception:
            logger.exception("Failed to record taxonomy classification error for %s", issue.id)
        return False


def _ensure_search_issue(db: Session, *, keyword: models.SearchKeyword) -> models.Issue:
    if keyword.issue_id:
        issue = db.get(models.Issue, keyword.issue_id)
        if issue:
            _classify_issue_best_effort(db, issue=issue, title=keyword.seed_query or keyword.query)
            return issue
    title = keyword.seed_query or keyword.query
    similar_issue, _ = find_similar_issue(
        db,
        title=title,
        topic=keyword.topic,
    )
    if similar_issue:
        keyword.issue_id = similar_issue.id
        similar_issue.issue_score = max(similar_issue.issue_score, 70 if keyword.priority == "high" else 55)
        similar_issue.updated_at = models.now_utc()
        db.flush()
        _classify_issue_best_effort(db, issue=similar_issue, title=title)
        return similar_issue
    issue_id = f"issue_search_{slugify(title)[:48]}"
    issue = db.get(models.Issue, issue_id)
    if not issue:
        issue = models.Issue(
            id=issue_id,
            is_public=True,
            issue_score=70 if keyword.priority == "high" else 55,
            risk="고영향" if keyword.priority == "high" else "일반",
            slug=slugify(title),
            status="검증 진행",
            summary="검색 수집으로 발견된 기사와 근거를 주장 단위로 검증 중입니다.",
            title=title,
            topic=normalize_topic(keyword.topic),
        )
        db.add(issue)
        db.flush()
    keyword.issue_id = issue.id
    _classify_issue_best_effort(db, issue=issue, title=title)
    return issue


def _ensure_discovery_issue(
    db: Session,
    *,
    definition: dict,
    existing_issue_id: str | None = None,
    priority: str,
) -> models.Issue:
    title = str(definition.get("title") or "새 사건 후보")[:180]
    summary = str(definition.get("summary") or "")[:1200]
    if existing_issue_id:
        existing_issue = db.get(models.Issue, existing_issue_id)
        if existing_issue:
            _classify_issue_best_effort(
                db,
                event_group_name=str(definition.get("event_group_name") or definition.get("eventGroup") or ""),
                issue=existing_issue,
                major_topic_name=str(definition.get("major_topic_name") or definition.get("majorTopic") or ""),
                summary=summary,
                title=title,
            )
            return existing_issue
    similar_issue, _ = find_similar_issue(
        db,
        summary=summary,
        title=title,
        topic=str(definition.get("topic") or ""),
    )
    if similar_issue:
        similar_issue.issue_score = max(similar_issue.issue_score, int(definition.get("score") or 0))
        if summary and (
            not similar_issue.summary
            or similar_issue.summary == "검색 수집으로 발견된 기사와 근거를 주장 단위로 검증 중입니다."
        ):
            similar_issue.summary = summary
        similar_issue.updated_at = models.now_utc()
        db.flush()
        _classify_issue_best_effort(
            db,
            event_group_name=str(definition.get("event_group_name") or definition.get("eventGroup") or ""),
            issue=similar_issue,
            major_topic_name=str(definition.get("major_topic_name") or definition.get("majorTopic") or ""),
            summary=summary,
            title=title,
        )
        return similar_issue
    issue_id = f"issue_discovery_{slugify(title)[:48]}"
    issue = db.get(models.Issue, issue_id)
    if not issue:
        issue = models.Issue(
            id=issue_id,
            is_public=True,
            issue_score=int(definition.get("score") or 60),
            risk="고영향" if priority == "high" or int(definition.get("score") or 0) >= 75 else "일반",
            slug=slugify(title),
            status="검증 진행",
            summary=summary or "검색 discovery로 발견된 사건을 검증 중입니다.",
            title=title,
            topic=normalize_topic(definition.get("topic")),
        )
        db.add(issue)
        db.flush()
    else:
        issue.issue_score = max(issue.issue_score, int(definition.get("score") or 0))
        if definition.get("summary"):
            issue.summary = str(definition.get("summary"))[:1200]
        issue.updated_at = models.now_utc()
    _classify_issue_best_effort(
        db,
        event_group_name=str(definition.get("event_group_name") or definition.get("eventGroup") or ""),
        issue=issue,
        major_topic_name=str(definition.get("major_topic_name") or definition.get("majorTopic") or ""),
        summary=summary,
        title=title,
    )
    return issue


def _prepare_article_for_claim_extraction(db: Session, *, article: models.Article) -> models.Issue | None:
    started_at = datetime.now(UTC)
    if not (article.ai_notes or {}).get("analysis"):
        analysis = DeepSeekAnalysisService(db).analyze_article_content(
            body_text=article.body_text,
            publisher=article.publisher,
            title=article.title,
            url=article.url,
        )
        if analysis:
            article.ai_notes = {**(article.ai_notes or {}), "analysis": analysis}
            normalized_title = str(analysis.get("normalized_title") or "").strip()
            summary = str(analysis.get("summary") or "").strip()
            if normalized_title and article.title == article.url:
                article.title = normalized_title[:500]
            if summary:
                article.summary = summary[:1000]
            article.updated_at = models.now_utc()
    issue = detect_or_match_issue(db, article=article)
    if not issue:
        record_agent_run(
            db,
            agent="Issue Detector",
            article_id=article.id,
            output_json={"matched": False},
            status="needs_review",
            target=article.title,
        )
        return None

    article.issue_id = issue.id
    _link_and_select_article_image_candidates(db, article=article, issue_id=issue.id)
    _classify_issue_best_effort(db, issue=issue, title=article.title, summary=article.summary)
    record_agent_run(
        db,
        agent="Article Triage",
        article_id=article.id,
        issue_id=issue.id,
        output_json={"issue_id": issue.id},
        started_at=started_at,
        status="completed",
        target=article.title,
    )
    db.flush()
    return issue


def process_article(db: Session, *, article: models.Article) -> list[models.Claim]:
    started_at = datetime.now(UTC)
    issue = _prepare_article_for_claim_extraction(db, article=article)
    if not issue:
        return []
    claims = extract_claims_for_article(db, article=article)
    for claim in claims:
        verify_claim_record(db, claim=claim)
    if article.source_type.startswith(("official", "public")):
        existing_claims = db.scalars(select(models.Claim).where(models.Claim.issue_id == issue.id)).all()
        for claim in existing_claims:
            verify_claim_record(db, claim=claim)
        create_update_log(
            db,
            description="공식 또는 공공 출처가 반영되어 관련 주장 판정을 재계산했습니다.",
            issue_id=issue.id,
            related_article_id=article.id,
            title="공식자료 반영",
            update_type="official_source",
        )
    create_update_log(
        db,
        description=f"새 기사에서 {len(claims)}개 주장을 추출했습니다.",
        issue_id=issue.id,
        related_article_id=article.id,
        title="새 기사 반영",
        update_type="new_article",
    )
    rebuild_perspectives(db, issue_id=issue.id)
    refresh_issue_cache(db, issue_id=issue.id)
    _enqueue_issue_enrichment_jobs(db, issue_id=issue.id)
    record_agent_run(
        db,
        agent="Article Pipeline",
        article_id=article.id,
        issue_id=issue.id,
        output_json={"claim_count": len(claims)},
        started_at=started_at,
        status="completed",
        target=article.title,
    )
    db.flush()
    return claims


def _persist_collected_image_candidates(
    db: Session,
    *,
    article: models.Article,
    collected: CollectedArticle,
    issue_id: str | None,
) -> list[models.ImageCandidate]:
    urls = [collected.image_url, *(collected.image_candidates or [])]
    candidates: list[models.ImageCandidate] = []
    seen: set[str] = set()
    for url in urls:
        value = str(url or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        candidate = upsert_image_candidate(
            db,
            article_id=article.id,
            issue_id=article.issue_id or issue_id,
            publisher=article.publisher or collected.publisher,
            source_type=article.source_type or collected.source_type,
            source_url=article.url or collected.url,
            url=value,
        )
        if candidate:
            candidates.append(candidate)
    return candidates


def _mark_remote_parse_eligible(article: models.Article, *, collected: CollectedArticle) -> None:
    if collected.image_url or collected.image_candidates:
        return
    if not article.url.lower().startswith(("http://", "https://")):
        return
    notes = dict(article.ai_notes or {})
    if notes.get("remoteParseAttempted"):
        return
    notes["remoteParseEligible"] = True
    article.ai_notes = notes
    article.updated_at = models.now_utc()


def link_article_image_candidates_to_issue(
    db: Session,
    *,
    article: models.Article,
    issue_id: str,
) -> list[models.ImageCandidate]:
    return link_image_candidates_to_issue(db, article_id=article.id, issue_id=issue_id)


def _link_and_select_article_image_candidates(
    db: Session,
    *,
    article: models.Article,
    issue_id: str,
) -> list[models.ImageCandidate]:
    linked, previous_issue_ids = link_image_candidates_to_issue_with_previous(
        db,
        article_id=article.id,
        issue_id=issue_id,
    )
    if linked:
        select_representative_image(db, issue_id=issue_id)
    for previous_issue_id in previous_issue_ids:
        if previous_issue_id != issue_id:
            select_representative_image(db, issue_id=previous_issue_id)
    return linked


def _hydrate_remote_article_assets(db: Session, *, article: models.Article) -> int:
    notes = dict(article.ai_notes or {})
    if not notes.get("remoteParseEligible") or notes.get("remoteParseAttempted"):
        return 0
    if not article.url.lower().startswith(("http://", "https://")):
        return 0

    notes["remoteParseAttempted"] = True
    try:
        parsed = fetch_and_parse_url(article.url)
    except Exception as exc:
        notes["remoteParseError"] = str(exc)[:240]
        article.ai_notes = notes
        article.updated_at = models.now_utc()
        db.flush()
        return 0

    if parsed.body_text and len(parsed.body_text) > len(article.body_text or ""):
        article.body_text = parsed.body_text
        article.content_hash = hash_text(parsed.body_text or parsed.title)
    if parsed.summary and len(parsed.summary) > len(article.summary or ""):
        article.summary = parsed.summary
    if parsed.title and (not article.title or article.title == article.url):
        article.title = parsed.title[:500]
    if parsed.publisher and not article.publisher:
        article.publisher = parsed.publisher[:200]
    if parsed.published_at and not article.published_at:
        article.published_at = parsed.published_at
    if parsed.parse_status:
        article.parse_status = parsed.parse_status

    candidates = persist_parsed_image_candidates(
        db,
        article=article,
        issue_id=article.issue_id,
        parsed=parsed,
        source_type=article.source_type,
        source_url=article.url,
    )
    notes["remoteImageCandidateCount"] = len(candidates)
    if not candidates and parsed.parse_status == "title_only":
        notes["remoteParseStatus"] = "title_only"
    article.ai_notes = notes
    article.updated_at = models.now_utc()
    db.flush()
    return len(candidates)


def _article_has_image_candidate(db: Session, *, article_id: str) -> bool:
    return bool(
        db.scalar(
            select(models.ImageCandidate.id)
            .where(models.ImageCandidate.article_id == article_id)
            .limit(1),
        ),
    )


def _hydrate_issue_article_images(db: Session, *, issue_id: str, limit: int = 3) -> int:
    articles = db.scalars(
        select(models.Article)
        .where(models.Article.issue_id == issue_id)
        .order_by(models.Article.created_at.desc())
        .limit(max(limit * 4, limit)),
    ).all()
    hydrated = 0
    attempts = 0
    for article in articles:
        if attempts >= limit:
            break
        if _article_has_image_candidate(db, article_id=article.id):
            continue
        notes = dict(article.ai_notes or {})
        if notes.get("remoteParseAttempted"):
            continue
        notes["remoteParseEligible"] = True
        article.ai_notes = notes
        attempts += 1
        hydrated += _hydrate_remote_article_assets(db, article=article)
    return hydrated


def ingest_collected_article(
    db: Session,
    *,
    collected: CollectedArticle,
    issue_id: str | None = None,
    source_id: str | None = None,
) -> tuple[models.Article, bool]:
    parsed = parse_article_content(
        body_text=collected.body_text or collected.summary,
        published_at=collected.published_at,
        publisher=collected.publisher,
        title=collected.title,
        url=collected.url,
    )
    article, created = upsert_article(
        db,
        issue_id=issue_id,
        parsed=parsed,
        source_id=source_id,
        source_type=collected.source_type,
        url=collected.url,
    )
    _persist_collected_image_candidates(db, article=article, collected=collected, issue_id=issue_id)
    _mark_remote_parse_eligible(article, collected=collected)
    if article.issue_id:
        select_representative_image(db, issue_id=article.issue_id)
    if created:
        process_article(db, article=article)
        if article.issue_id:
            _persist_collected_image_candidates(db, article=article, collected=collected, issue_id=article.issue_id)
            select_representative_image(db, issue_id=article.issue_id)
    return article, created


def upsert_collected_article_record(
    db: Session,
    *,
    collected: CollectedArticle,
    issue_id: str | None = None,
    source_id: str | None = None,
) -> tuple[models.Article, bool]:
    parsed = parse_article_content(
        body_text=collected.body_text or collected.summary,
        published_at=collected.published_at,
        publisher=collected.publisher,
        title=collected.title,
        url=collected.url,
    )
    target_issue_id = issue_id
    parsed_content_hash = hash_text(parsed.body_text or parsed.title)
    if issue_id:
        issue = db.get(models.Issue, issue_id)
        should_attach, _ = should_attach_article_to_issue(
            db,
            article=collected,
            content_hash=parsed_content_hash,
            issue=issue,
        )
        if not should_attach:
            target_issue_id = None
    article, created = upsert_article(
        db,
        issue_id=target_issue_id,
        parsed=parsed,
        source_id=source_id,
        source_type=collected.source_type,
        url=collected.url,
    )
    _persist_collected_image_candidates(db, article=article, collected=collected, issue_id=target_issue_id)
    _mark_remote_parse_eligible(article, collected=collected)
    if article.issue_id:
        select_representative_image(db, issue_id=article.issue_id)
    return article, created


def _article_has_claims(db: Session, *, article_id: str) -> bool:
    return bool(db.scalar(select(models.Claim.id).where(models.Claim.article_id == article_id).limit(1)))


def _enqueue_parse_article_job(db: Session, *, article_id: str) -> bool:
    existing = db.scalar(
        select(models.JobAttempt.id).where(
            models.JobAttempt.job_type == "parse_article",
            models.JobAttempt.target_id == article_id,
            models.JobAttempt.status.in_(["queued", "running"]),
        ),
    )
    if existing:
        return False
    from app.services.jobs import enqueue_job

    enqueue_job(
        db,
        input_json={"article_id": article_id},
        job_type="parse_article",
        run_immediately=False,
        target_id=article_id,
    )
    return True


def _enqueue_search_news_job(db: Session, *, keyword_id: str) -> bool:
    existing = db.scalar(
        select(models.JobAttempt.id).where(
            models.JobAttempt.job_type == "search_news",
            models.JobAttempt.target_id == keyword_id,
            models.JobAttempt.status.in_(["queued", "running"]),
        ),
    )
    if existing:
        return False
    from app.services.jobs import enqueue_job

    enqueue_job(
        db,
        input_json={"keyword_id": keyword_id},
        job_type="search_news",
        run_immediately=False,
        target_id=keyword_id,
    )
    return True


def _enqueue_singleton_job(db: Session, *, issue_id: str, job_type: str) -> bool:
    existing = db.scalar(
        select(models.JobAttempt.id).where(
            models.JobAttempt.job_type == job_type,
            models.JobAttempt.target_id == issue_id,
            models.JobAttempt.status.in_(["queued", "running"]),
        ),
    )
    if existing:
        return False
    from app.services.jobs import enqueue_job

    enqueue_job(
        db,
        input_json={"issue_id": issue_id},
        job_type=job_type,
        run_immediately=False,
        target_id=issue_id,
    )
    return True


def _enqueue_target_job(
    db: Session,
    *,
    input_json: dict | None = None,
    job_type: str,
    target_id: str,
) -> bool:
    existing = db.scalar(
        select(models.JobAttempt.id).where(
            models.JobAttempt.job_type == job_type,
            models.JobAttempt.target_id == target_id,
            models.JobAttempt.status.in_(["queued", "running"]),
        ),
    )
    if existing:
        return False
    from app.services.jobs import enqueue_job

    enqueue_job(
        db,
        input_json=input_json or {},
        job_type=job_type,
        run_immediately=False,
        target_id=target_id,
    )
    return True


def _enqueue_research_issue_job(
    db: Session,
    *,
    issue_id: str,
    missing_signals: list[str] | None = None,
    round_index: int = 1,
    seed_query: str = "",
    trigger_type: str,
) -> bool:
    existing = db.scalar(
        select(models.JobAttempt.id).where(
            models.JobAttempt.job_type == "research_issue",
            models.JobAttempt.target_id == issue_id,
            models.JobAttempt.status.in_(["queued", "running"]),
        ),
    )
    if existing:
        return False
    from app.services.jobs import enqueue_job

    enqueue_job(
        db,
        input_json={
            "issue_id": issue_id,
            "missing_signals": missing_signals or [],
            "round_index": round_index,
            "seed_query": seed_query,
            "trigger_type": trigger_type,
        },
        job_type="research_issue",
        run_immediately=False,
        target_id=issue_id,
    )
    return True


def _enqueue_issue_enrichment_jobs(db: Session, *, issue_id: str) -> dict:
    return {
        "quality": _enqueue_singleton_job(db, issue_id=issue_id, job_type="assess_issue_quality"),
        "image": _enqueue_singleton_job(db, issue_id=issue_id, job_type="select_representative_image"),
        "page": _enqueue_singleton_job(db, issue_id=issue_id, job_type="update_issue_page"),
    }


def _enqueue_quality_job(db: Session, *, issue_id: str) -> bool:
    return _enqueue_singleton_job(db, issue_id=issue_id, job_type="assess_issue_quality")


def _collect_search_results(
    queries: list[str],
    *,
    max_items: int,
    recent_days: int = 14,
    per_query_limit: int | None = None,
) -> list[CollectedArticle]:
    results_by_url: dict[str, CollectedArticle] = {}
    limit = max(1, min(per_query_limit or max_items, 30))
    expanded_queries = _recent_search_queries(queries, recent_days=recent_days)
    for query in expanded_queries:
        clean_query = str(query).strip()
        if not clean_query:
            continue
        try:
            for item in collect_google_news_search(clean_query, max_items=limit):
                if item.url:
                    results_by_url.setdefault(item.url, item)
        except Exception:
            continue
        if len(results_by_url) >= max_items:
            break
    return list(results_by_url.values())[:max_items]


def _recent_search_queries(queries: list[str], *, recent_days: int = 14) -> list[str]:
    windows = [2, 7, max(14, recent_days)]
    expanded: list[str] = []
    seen: set[str] = set()
    for query in queries:
        value = str(query).strip()
        if len(value) < 2:
            continue
        for candidate in [value, *(f"{value} when:{days}d" for days in windows if days <= max(recent_days, 14))]:
            if candidate not in seen:
                expanded.append(candidate)
                seen.add(candidate)
    return expanded[:36]


def _keyword_search_queries(keyword: models.SearchKeyword | None, search_query: str) -> list[str]:
    extra_queries = ((keyword.metadata_json or {}).get("search_queries") or []) if keyword else []
    if keyword and keyword.source == "quality_retry" and extra_queries:
        queries: list[str] = [str(query) for query in extra_queries]
    else:
        queries = [search_query]
    if keyword and keyword.seed_query and keyword.seed_query != search_query:
        queries.append(keyword.seed_query)
    if keyword:
        queries.extend(str(query) for query in extra_queries)
    variant_base = queries[0] if keyword and keyword.source == "quality_retry" and queries else search_query
    queries.extend(fallback_keyword_variants(variant_base)[:12])
    if keyword and keyword.seed_query:
        queries.extend(fallback_keyword_variants(keyword.seed_query)[:8])
    seen: set[str] = set()
    cleaned: list[str] = []
    for query in queries:
        value = str(query).strip()
        if len(value) < 2 or value in seen:
            continue
        seen.add(value)
        cleaned.append(value)
    return cleaned[:18]


def _issue_article_count(db: Session, *, issue_id: str) -> int:
    return int(db.scalar(select(func.count(models.Article.id)).where(models.Article.issue_id == issue_id)) or 0)


def _is_future(value: datetime | None, now: datetime) -> bool:
    if value is None:
        return False
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    return value > now


def _quality_retry_search_guard(db: Session, *, keyword: models.SearchKeyword | None) -> dict | None:
    if not keyword or keyword.source != "quality_retry":
        return None
    base = {
        "article_count": 0,
        "issue_id": keyword.issue_id,
        "keyword_id": keyword.id,
        "query": keyword.query,
    }
    if keyword.status != "active":
        return base | {"reason": "keyword_inactive", "status": "skipped"}
    if not keyword.issue_id:
        keyword.status = "inactive"
        keyword.updated_at = models.now_utc()
        db.commit()
        return base | {"reason": "missing_issue_id", "status": "skipped"}
    issue = db.get(models.Issue, keyword.issue_id)
    if not issue:
        keyword.status = "inactive"
        keyword.updated_at = models.now_utc()
        db.commit()
        return base | {"reason": "issue_missing", "status": "skipped"}
    if issue.quality_status != "needs_retry":
        keyword.status = "inactive"
        keyword.updated_at = models.now_utc()
        db.commit()
        return base | {"reason": "issue_quality_status", "status": "skipped"}
    now = models.now_utc()
    if _is_future(issue.next_quality_retry_at, now):
        return base | {"reason": "quality_retry_cooldown", "status": "retry_pending"}
    return None


def _issue_backfill_queries(issue: models.Issue) -> list[str]:
    queries = [issue.title]
    queries.extend(fallback_keyword_variants(issue.title)[:14])
    summary = (issue.summary or "").strip()
    if summary:
        queries.append(f"{issue.title} {summary[:80]}")
    for followup in ("후속", "해명", "설명자료", "공식자료", "발표", "조사", "감사", "고발", "수사"):
        queries.append(f"{issue.title} {followup}")
    for cluster in issue.claim_clusters or []:
        if not isinstance(cluster, dict):
            continue
        title = str(cluster.get("title") or "").strip()
        question = str(cluster.get("question") or "").strip()
        if title:
            queries.append(f"{issue.title} {title}")
        if question:
            queries.append(f"{issue.title} {question[:80]}")
    seen: set[str] = set()
    cleaned: list[str] = []
    for query in queries:
        value = str(query).strip()
        if len(value) < 2 or value in seen:
            continue
        seen.add(value)
        cleaned.append(value[:300])
    return cleaned[:24]


def collect_source(source_id: str) -> dict:
    db = SessionLocal()
    try:
        source = db.get(models.SourceDomain, source_id)
        if not source:
            return {"status": "not_found", "article_count": 0}
        run = models.CollectorRun(
            collector=source.source_type,
            id=new_id("collector"),
            source_id=source.id,
            status="running",
        )
        db.add(run)
        db.commit()

        try:
            if source.source_type == "rss":
                collected = collect_rss(source.collection_url, publisher=source.name)
            elif source.source_type in {"official", "public"}:
                collected = collect_official_source(source.collection_url, publisher=source.name)
            elif source.source_type == "youtube":
                collected = collect_youtube_candidates(source.collection_url, publisher=source.name)
            elif source.source_type in {"social", "sns"}:
                collected = collect_public_social_candidates(source.collection_url, publisher=source.name)
            elif source.source_type in {"search", "news_search"}:
                collected = collect_google_news_search(source.note or source.name, max_items=10, publisher=source.name)
            else:
                collected = collect_json_news(source.collection_url, publisher=source.name)
            created_count = 0
            parse_job_count = 0
            for item in collected:
                article, created = upsert_collected_article_record(db, collected=item, source_id=source.id)
                created_count += int(created)
                if (created or not _article_has_claims(db, article_id=article.id)) and _enqueue_parse_article_job(
                    db,
                    article_id=article.id,
                ):
                    parse_job_count += 1
            run.status = "completed"
            run.article_count = created_count
            run.finished_at = models.now_utc()
            run.output_json = {"collected": len(collected), "created": created_count, "parse_jobs": parse_job_count}
            source.last_collected_at = models.now_utc()
            source.last_collection_status = "completed"
            db.commit()
            return {"status": "completed", "article_count": created_count, "parse_jobs": parse_job_count}
        except Exception as exc:
            run.status = "failed"
            run.error_message = str(exc)
            run.finished_at = models.now_utc()
            source.last_collection_status = "failed"
            db.commit()
            return {"status": "failed", "article_count": 0, "error": str(exc)}
    finally:
        db.close()


def search_news(keyword_id: str | None = None, *, query: str | None = None) -> dict:
    db = SessionLocal()
    try:
        keyword = db.get(models.SearchKeyword, keyword_id) if keyword_id else None
        guarded = _quality_retry_search_guard(db, keyword=keyword)
        if guarded:
            return guarded
        search_query = query or (keyword.query if keyword else "")
        if not search_query:
            return {"status": "not_found", "article_count": 0}
        run = models.CollectorRun(
            collector="news_search",
            id=new_id("collector"),
            source_id=keyword.id if keyword else None,
            status="running",
            output_json={"query": search_query},
        )
        db.add(run)
        db.commit()
        try:
            max_items = int(get_effective_setting(db, "search_max_results_per_keyword") or 5)
            recent_days = int(get_effective_setting(db, "search_recent_days") or 14)
            if keyword:
                try:
                    max_items = int((keyword.metadata_json or {}).get("max_items") or max_items)
                except (TypeError, ValueError):
                    max_items = int(get_effective_setting(db, "search_max_results_per_keyword") or 5)
            search_queries = _keyword_search_queries(keyword, search_query)
            collected = _collect_search_results(
                search_queries,
                max_items=max(1, min(max_items, 30)),
                per_query_limit=max(3, min(max_items, 10)),
                recent_days=recent_days,
            )
            issue = _ensure_search_issue(db, keyword=keyword) if keyword and collected else None
            created_count = 0
            parse_job_count = 0
            article_ids: list[str] = []
            for item in collected:
                article, created = upsert_collected_article_record(
                    db,
                    collected=item,
                    issue_id=issue.id if issue else None,
                )
                if issue and not article.issue_id:
                    should_attach, _ = should_attach_article_to_issue(db, article=article, issue=issue)
                    if not should_attach:
                        article_ids.append(article.id)
                        created_count += int(created)
                        continue
                    article.issue_id = issue.id
                    _link_and_select_article_image_candidates(db, article=article, issue_id=issue.id)
                should_parse = not issue or article.issue_id == issue.id
                if should_parse and (created or not _article_has_claims(db, article_id=article.id)) and _enqueue_parse_article_job(
                    db,
                    article_id=article.id,
                ):
                    parse_job_count += 1
                article_ids.append(article.id)
                created_count += int(created)
            if issue:
                refresh_issue_cache(db, issue_id=issue.id)
                _enqueue_issue_enrichment_jobs(db, issue_id=issue.id)
            if keyword:
                keyword.issue_id = issue.id if issue else keyword.issue_id
                keyword.last_new_article_count = created_count
                keyword.last_result_count = len(collected)
                keyword.last_searched_at = models.now_utc()
                keyword.updated_at = models.now_utc()
                if keyword.source == "quality_retry" and keyword.issue_id:
                    _enqueue_quality_job(db, issue_id=keyword.issue_id)
            run.status = "completed"
            run.article_count = created_count
            run.finished_at = models.now_utc()
            run.output_json = {
                "article_ids": article_ids,
                "collected": len(collected),
                "created": created_count,
                "issue_id": issue.id if issue else None,
                "parse_jobs": parse_job_count,
                "query": search_query,
                "search_queries": search_queries,
            }
            db.commit()
            return run.output_json | {"status": "completed", "article_count": created_count}
        except Exception as exc:
            run.status = "failed"
            run.error_message = str(exc)
            run.finished_at = models.now_utc()
            if keyword:
                keyword.last_searched_at = models.now_utc()
                keyword.last_result_count = 0
                keyword.last_new_article_count = 0
                keyword.updated_at = models.now_utc()
            db.commit()
            return {"status": "failed", "article_count": 0, "error": str(exc), "query": search_query}
    finally:
        db.close()


def backfill_issue_sources(issue_id: str | None = None, *, force: bool = False, limit: int | None = None) -> dict:
    db = SessionLocal()
    try:
        min_sources = int(get_effective_setting(db, "issue_min_sources_for_public") or 1)
        max_issues = int(limit or get_effective_setting(db, "issue_source_backfill_limit") or 8)
        recent_days = int(get_effective_setting(db, "search_recent_days") or 14)
        if issue_id:
            issue = db.get(models.Issue, issue_id)
            issues = [issue] if issue else []
        else:
            issues = db.scalars(
                select(models.Issue)
                .where(
                    models.Issue.status != "숨김",
                    models.Issue.article_count < min_sources,
                )
                .order_by(models.Issue.updated_at.desc())
                .limit(max_issues),
            ).all()

        processed: list[dict] = []
        for issue in issues:
            actual_count = _issue_article_count(db, issue_id=issue.id)
            if actual_count >= min_sources and not force:
                issue.is_public = True
                if issue.status == "출처 보강 필요":
                    issue.status = "검증 진행"
                refresh_issue_cache(db, issue_id=issue.id)
                _enqueue_issue_enrichment_jobs(db, issue_id=issue.id)
                processed.append(
                    {
                        "issue_id": issue.id,
                        "status": "already_sourced",
                        "article_count": actual_count,
                    },
                )
                continue

            queries = _issue_backfill_queries(issue)
            max_items = max(min_sources * 4, int(get_effective_setting(db, "search_max_results_per_keyword") or 5))
            if force:
                max_items = max(max_items, 12)
            collected = _collect_search_results(
                queries,
                max_items=max(5, min(max_items, 30)),
                per_query_limit=8,
                recent_days=recent_days,
            )
            created_count = 0
            linked_count = 0
            parse_job_count = 0
            article_ids: list[str] = []
            for item in collected:
                article, created = upsert_collected_article_record(db, collected=item, issue_id=issue.id)
                if article.issue_id != issue.id:
                    should_attach, _ = should_attach_article_to_issue(db, article=article, issue=issue)
                    if not should_attach:
                        created_count += int(created)
                        article_ids.append(article.id)
                        continue
                    article.issue_id = issue.id
                    _link_and_select_article_image_candidates(db, article=article, issue_id=issue.id)
                    linked_count += 1
                created_count += int(created)
                article_ids.append(article.id)
                if _enqueue_parse_article_job(db, article_id=article.id):
                    parse_job_count += 1

            for query in queries[:6]:
                keyword = upsert_search_keyword(
                    db,
                    interval_minutes=30,
                    issue_id=issue.id,
                    priority="high" if query == issue.title else "normal",
                    query=query,
                    seed_query=issue.title,
                    source="issue_followup" if force else "source_backfill",
                    topic=issue.topic,
                    metadata={
                        "backfill_issue_id": issue.id,
                        "forced_followup": force,
                        "search_queries": queries,
                    },
                )
                _enqueue_search_news_job(db, keyword_id=keyword.id)

            refresh_issue_cache(db, issue_id=issue.id)
            _enqueue_issue_enrichment_jobs(db, issue_id=issue.id)
            final_count = _issue_article_count(db, issue_id=issue.id)
            if final_count >= min_sources:
                issue.is_public = True
                if issue.status == "출처 보강 필요":
                    issue.status = "검증 진행"
            else:
                issue.is_public = False
                issue.status = "출처 보강 필요"
            issue.updated_at = models.now_utc()
            processed.append(
                {
                    "article_count": final_count,
                    "article_ids": article_ids,
                    "collected": len(collected),
                    "created": created_count,
                    "issue_id": issue.id,
                    "linked": linked_count,
                    "parse_jobs": parse_job_count,
                    "queries": queries,
                    "status": "completed" if final_count >= min_sources else "needs_source",
                },
            )

        db.commit()
        return {
            "status": "completed",
            "processed": processed,
            "processed_count": len(processed),
        }
    except Exception as exc:
        db.rollback()
        return {"status": "failed", "error": str(exc), "processed": []}
    finally:
        db.close()


def discover_topic(topic_id: str) -> dict:
    db = SessionLocal()
    try:
        topic = db.get(models.DiscoveryTopic, topic_id)
        if not topic:
            return {"status": "not_found", "candidate_count": 0}
        queries = [str(query).strip() for query in (topic.base_queries_json or [topic.name]) if str(query).strip()]
        expanded_queries: list[str] = []
        for query in queries:
            expanded_queries.append(query)
            expanded_queries.extend(fallback_keyword_variants(query)[:8])
        seen_queries: set[str] = set()
        expanded_queries = [
            query
            for query in expanded_queries
            if query not in seen_queries and not seen_queries.add(query)
        ][:24]
        run = models.CollectorRun(
            collector="discovery",
            id=new_id("collector"),
            source_id=topic.id,
            status="running",
            output_json={"queries": queries, "expanded_queries": expanded_queries},
        )
        db.add(run)
        db.commit()
        try:
            recent_days = int(get_effective_setting(db, "search_recent_days") or 14)
            collected = _collect_search_results(
                expanded_queries or queries,
                max_items=max(8, min(topic.max_results_per_query * 4, 60)),
                per_query_limit=max(1, min(topic.max_results_per_query, 30)),
                recent_days=recent_days,
            )
            clusters = [
                cluster
                for cluster in cluster_collected_articles(collected)
                if len(cluster) >= max(1, topic.min_cluster_size)
            ]
            promoted: list[dict] = []
            for cluster in clusters[:8]:
                definition = define_incident(
                    db,
                    articles=cluster,
                    topic=topic.topic,
                    topic_name=topic.name,
                )
                article_ids: list[str] = []
                article_rows: list[models.Article] = []
                new_articles = 0
                for item in cluster:
                    article, created = upsert_collected_article_record(db, collected=item)
                    article_rows.append(article)
                    article_ids.append(article.id)
                    new_articles += int(created)

                existing_incident = db.get(
                    models.DiscoveredIncident,
                    f"incident_{hash_text('|'.join(sorted(article_ids)))[:16]}",
                )
                issue = _ensure_discovery_issue(
                    db,
                    definition=definition,
                    existing_issue_id=existing_incident.issue_id if existing_incident else None,
                    priority=topic.priority,
                )
                research_job_queued = _enqueue_research_issue_job(
                    db,
                    issue_id=issue.id,
                    seed_query=str(definition.get("title") or issue.title),
                    trigger_type="discovery_burst",
                )
                for article in article_rows:
                    if article.issue_id != issue.id:
                        should_attach, _ = should_attach_article_to_issue(db, article=article, issue=issue)
                        if not should_attach:
                            continue
                        article.issue_id = issue.id
                        _link_and_select_article_image_candidates(db, article=article, issue_id=issue.id)

                keyword_ids: list[str] = []
                search_job_count = 0
                for keyword in [definition["title"], *(definition.get("keywords") or [])][:10]:
                    row = upsert_search_keyword(
                        db,
                        interval_minutes=max(15, topic.discovery_interval_minutes),
                        issue_id=issue.id,
                        priority="high" if definition.get("score", 0) >= 75 else "normal",
                        query=str(keyword),
                        seed_query=definition["title"],
                        source="discovery",
                        topic=issue.topic,
                        metadata={"discovery_topic_id": topic.id},
                    )
                    keyword_ids.append(row.id)
                    if len(keyword_ids) <= 3:
                        search_job_count += int(_enqueue_search_news_job(db, keyword_id=row.id))
                parse_job_count = 0
                for article in article_rows:
                    if _enqueue_parse_article_job(db, article_id=article.id):
                        parse_job_count += 1
                incident = upsert_discovered_incident(
                    db,
                    article_ids=article_ids,
                    definition=definition,
                    discovery_topic_id=topic.id,
                    issue_id=issue.id,
                    keyword_ids=keyword_ids,
                )
                refresh_issue_cache(db, issue_id=issue.id)
                _enqueue_issue_enrichment_jobs(db, issue_id=issue.id)
                promoted.append(
                    {
                        "article_count": len(article_ids),
                        "incident_id": incident.id,
                        "issue_id": issue.id,
                        "new_articles": new_articles,
                        "parse_jobs": parse_job_count,
                        "research_job": research_job_queued,
                        "score": definition.get("score"),
                        "search_jobs": search_job_count,
                        "title": definition.get("title"),
                    },
                )

            topic.last_candidate_count = len(promoted)
            topic.last_discovered_at = models.now_utc()
            topic.last_result_count = len(collected)
            topic.updated_at = models.now_utc()
            run.status = "completed"
            run.article_count = sum(item["new_articles"] for item in promoted)
            run.finished_at = models.now_utc()
            run.output_json = {
                "candidate_count": len(promoted),
                "collected": len(collected),
                "expanded_queries": expanded_queries,
                "promoted": promoted,
                "queries": queries,
            }
            record_agent_run(
                db,
                agent="Discovery",
                output_json=run.output_json,
                status="completed",
                target=topic.name,
            )
            db.commit()
            return run.output_json | {"status": "completed"}
        except Exception as exc:
            run.status = "failed"
            run.error_message = str(exc)
            run.finished_at = models.now_utc()
            topic.last_discovered_at = models.now_utc()
            topic.last_candidate_count = 0
            topic.last_result_count = 0
            topic.updated_at = models.now_utc()
            db.commit()
            return {"status": "failed", "candidate_count": 0, "error": str(exc)}
    finally:
        db.close()


def collect_sources(source_ids: list[str] | None = None) -> dict:
    db = SessionLocal()
    try:
        query = select(models.SourceDomain).where(models.SourceDomain.is_active.is_(True))
        if source_ids:
            query = query.where(models.SourceDomain.id.in_(source_ids))
        sources = db.scalars(query).all()
    finally:
        db.close()

    results = [collect_source(source.id) for source in sources]
    return {
        "status": "completed",
        "source_count": len(results),
        "article_count": sum(item.get("article_count", 0) for item in results),
        "results": results,
    }


def research_issue(
    issue_id: str | None = None,
    *,
    keyword_id: str | None = None,
    missing_signals: list[str] | None = None,
    round_index: int = 1,
    seed_query: str = "",
    trigger_type: str = "manual",
) -> dict:
    from app.services.research.executor import execute_research_plan

    db = SessionLocal()
    try:
        issue = db.get(models.Issue, issue_id) if issue_id else None
        if issue_id and not issue:
            return {"article_count": 0, "created": 0, "status": "not_found"}
        if issue and not missing_signals:
            missing_signals = list((issue.quality_report_json or {}).get("missingSignals") or [])
        result = execute_research_plan(
            db,
            issue=issue,
            keyword_id=keyword_id,
            missing_signals=missing_signals or [],
            round_index=round_index,
            seed_query=seed_query,
            trigger_type=trigger_type,
        )
        if issue:
            refresh_issue_cache(db, issue_id=issue.id)
            _enqueue_issue_enrichment_jobs(db, issue_id=issue.id)
        db.commit()
        return result
    except Exception as exc:
        db.rollback()
        return {"article_count": 0, "created": 0, "error": str(exc), "status": "failed"}
    finally:
        db.close()


def parse_article(article_id: str) -> dict:
    db = SessionLocal()
    try:
        article = db.get(models.Article, article_id)
        if not article:
            return {"status": "not_found"}
        remote_image_candidates = _hydrate_remote_article_assets(db, article=article)
        issue = _prepare_article_for_claim_extraction(db, article=article)
        if not issue:
            db.commit()
            return {"status": "needs_review", "stage": "parsed", "extract_job": False}
        extract_job = _enqueue_target_job(
            db,
            input_json={"article_id": article.id},
            job_type="extract_claims",
            target_id=article.id,
        )
        issue_id = issue.id
        db.commit()
        refresh_issue_cache(db, issue_id=issue_id)
        _enqueue_issue_enrichment_jobs(db, issue_id=issue_id)
        db.commit()
        return {
            "status": "completed",
            "stage": "parsed",
            "issue_id": issue_id,
            "extract_job": extract_job,
            "remote_image_candidates": remote_image_candidates,
        }
    finally:
        db.close()


def deduplicate_article(article_id: str) -> dict:
    db = SessionLocal()
    try:
        article = db.get(models.Article, article_id)
        if not article:
            return {"status": "not_found"}
        duplicate = db.scalar(
            select(models.Article).where(
                models.Article.dedup_hash == article.dedup_hash,
                models.Article.id != article.id,
            ),
        )
        if duplicate:
            db.delete(article)
            db.commit()
            return {"status": "duplicate_removed", "kept": duplicate.id}
        return {"status": "unique"}
    finally:
        db.close()


def detect_issue(article_ids: list[str]) -> dict:
    db = SessionLocal()
    try:
        matched = 0
        for article_id in article_ids:
            article = db.get(models.Article, article_id)
            issue = detect_or_match_issue(db, article=article) if article else None
            if article and issue:
                _link_and_select_article_image_candidates(db, article=article, issue_id=issue.id)
                matched += 1
        db.commit()
        return {"status": "completed", "matched": matched}
    finally:
        db.close()


def match_issue(article_id: str) -> dict:
    return detect_issue([article_id])


def extract_claims(article_id: str) -> dict:
    db = SessionLocal()
    try:
        article = db.get(models.Article, article_id)
        if not article:
            return {"status": "not_found", "stage": "claims_extracted"}
        if not article.issue_id:
            issue = _prepare_article_for_claim_extraction(db, article=article)
            if not issue:
                db.commit()
                return {"status": "needs_review", "stage": "claims_extracted", "claim_count": 0}
        claims = extract_claims_for_article(db, article=article)
        retrieve_jobs = 0
        for claim in claims:
            retrieve_jobs += int(
                _enqueue_target_job(
                    db,
                    input_json={"claim_id": claim.id},
                    job_type="retrieve_evidence",
                    target_id=claim.id,
                ),
            )
        issue_id = article.issue_id
        is_official_article = article.source_type.startswith(("official", "public"))
        if is_official_article and issue_id:
            existing_claims = db.scalars(select(models.Claim).where(models.Claim.issue_id == issue_id)).all()
            for claim in existing_claims:
                retrieve_jobs += int(
                    _enqueue_target_job(
                        db,
                        input_json={"claim_id": claim.id},
                        job_type="retrieve_evidence",
                        target_id=claim.id,
                    ),
                )
        if issue_id:
            notes = article.ai_notes or {}
            if not notes.get("claims_update_logged"):
                create_update_log(
                    db,
                    description=f"새 기사에서 {len(claims)}개 주장을 추출했습니다.",
                    issue_id=issue_id,
                    related_article_id=article.id,
                    title="새 기사 반영",
                    update_type="new_article",
                )
                article.ai_notes = {**notes, "claims_update_logged": True}
        db.commit()
        if issue_id:
            rebuild_perspectives(db, issue_id=issue_id)
            db.commit()
            refresh_issue_cache(db, issue_id=issue_id)
            _enqueue_issue_enrichment_jobs(db, issue_id=issue_id)
            db.commit()
        return {
            "status": "completed",
            "stage": "claims_extracted",
            "claim_count": len(claims),
            "retrieve_jobs": retrieve_jobs,
        }
    finally:
        db.close()


def cluster_claim(claim_id: str) -> dict:
    db = SessionLocal()
    try:
        claim = db.get(models.Claim, claim_id)
        if not claim:
            return {"status": "not_found"}
        from app.services.claims.clusterer import assign_cluster

        cluster = assign_cluster(db, claim=claim)
        db.commit()
        return {"status": "completed", "cluster_id": cluster.id}
    finally:
        db.close()


def retrieve_evidence(claim_id: str) -> dict:
    db = SessionLocal()
    try:
        claim = db.get(models.Claim, claim_id)
        if not claim:
            return {"status": "not_found"}
        from app.services.evidence.retriever import retrieve_evidence_for_claim

        evidences = retrieve_evidence_for_claim(db, claim=claim)
        verify_job = _enqueue_target_job(
            db,
            input_json={"claim_id": claim.id},
            job_type="verify_claim",
            target_id=claim.id,
        )
        db.commit()
        return {
            "status": "completed",
            "stage": "evidence_retrieved",
            "evidence_count": len(evidences),
            "verify_job": verify_job,
        }
    finally:
        db.close()


def verify_claim(claim_id: str) -> dict:
    db = SessionLocal()
    try:
        claim = db.get(models.Claim, claim_id)
        if not claim:
            return {"status": "not_found"}
        verify_claim_record(db, claim=claim)
        issue_id = claim.issue_id
        db.commit()
        if issue_id:
            rebuild_perspectives(db, issue_id=issue_id)
            db.commit()
            refresh_issue_cache(db, issue_id=issue_id)
            _enqueue_issue_enrichment_jobs(db, issue_id=issue_id)
            db.commit()
        return {"status": "completed", "verdict": claim.verdict}
    finally:
        db.close()


def update_issue_page(issue_id: str) -> dict:
    db = SessionLocal()
    try:
        issue = refresh_issue_cache(db, issue_id=issue_id)
        db.commit()
        return {"status": "completed" if issue else "not_found"}
    finally:
        db.close()


def assess_issue_quality_job(issue_id: str) -> dict:
    db = SessionLocal()
    try:
        from app.services.issues.quality import assess_issue_quality

        result = assess_issue_quality(db, issue_id=issue_id)
        issue = db.get(models.Issue, issue_id)
        if issue and result.get("status") == "needs_retry":
            _enqueue_research_issue_job(
                db,
                issue_id=issue.id,
                missing_signals=list(result.get("missingSignals") or []),
                round_index=int(issue.quality_attempts or 1),
                seed_query=issue.title,
                trigger_type="quality_gap",
            )
        db.commit()
        return result
    finally:
        db.close()


def select_representative_image_job(issue_id: str) -> dict:
    db = SessionLocal()
    try:
        hydrated_image_candidates = _hydrate_issue_article_images(db, issue_id=issue_id)
        selected = select_representative_image(db, issue_id=issue_id)
        db.commit()
        return {
            "hydrated_image_candidates": hydrated_image_candidates,
            "status": "completed" if selected else "needs_candidate",
            "image_id": selected.id if selected else None,
        }
    finally:
        db.close()


def send_issue_notifications(issue_id: str, update_log_id: str) -> dict:
    db = SessionLocal()
    try:
        log = db.get(models.UpdateLog, update_log_id)
        if not log:
            return {"status": "not_found"}
        notifications = notify_update_log(db, update_log=log)
        db.commit()
        return {"status": "completed", "notification_count": len(notifications)}
    finally:
        db.close()
