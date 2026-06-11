from __future__ import annotations

from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.services.ai.deepseek_client import DeepSeekAnalysisService
from app.utils import new_id


def _local_documents(db: Session, *, claim: models.Claim) -> list[dict]:
    documents: list[dict] = []
    articles = db.scalars(
        select(models.Article)
        .where(models.Article.issue_id == claim.issue_id)
        .order_by(models.Article.collected_at.desc())
        .limit(12),
    ).all()
    for article in articles:
        documents.append(
            {
                "document_id": f"article:{article.id}",
                "title": article.title,
                "url": article.url,
                "publisher": article.publisher,
                "source_type": article.source_type,
                "text": f"{article.summary}\n{article.body_text[:1500]}".strip(),
                "published_at": article.published_at.isoformat() if article.published_at else None,
                "document_kind": "article",
            },
        )

    sources = db.scalars(
        select(models.SourceDomain)
        .where(models.SourceDomain.status.in_(["trusted", "watch"]))
        .order_by(models.SourceDomain.credibility.desc())
        .limit(8),
    ).all()
    for source in sources:
        documents.append(
            {
                "document_id": f"source:{source.id}",
                "title": source.name,
                "url": source.collection_url or f"https://{source.domain}",
                "publisher": source.name,
                "source_type": source.source_type,
                "text": source.note or f"{source.name} ({source.domain})",
                "credibility": source.credibility,
                "document_kind": "source_registry",
            },
        )
    return documents


def _document_by_id(documents: list[dict]) -> dict[str, dict]:
    return {str(document.get("document_id")): document for document in documents}


def _bounded_float(value: object, *, default: float = 0.0) -> float:
    try:
        number = float(value if value is not None else default)
    except (TypeError, ValueError):
        number = default
    return max(0.0, min(number, 1.0))


def retrieve_evidence_for_claim(db: Session, *, claim: models.Claim) -> list[models.Evidence]:
    existing = db.scalars(select(models.Evidence).where(models.Evidence.claim_id == claim.id)).all()

    documents = _local_documents(db, claim=claim)
    document_map = _document_by_id(documents)
    existing_document_ids = {
        str((evidence.retrieval_json or {}).get("documentId") or "")
        for evidence in existing
    }
    existing_urls = {evidence.url for evidence in existing if evidence.url}
    ai_rows = DeepSeekAnalysisService(db).generate_evidence_candidates(
        claim_text=claim.sanitized_text or claim.claim_text,
        claim_type=claim.claim_type,
        entities_json=claim.entities_json or {},
        local_documents=documents,
    )
    evidences: list[models.Evidence] = []
    for row in ai_rows[:6]:
        document_id = str(row.get("document_id") or "")
        if document_id.startswith("source:"):
            continue
        document = document_map.get(document_id)
        if not document:
            continue
        if document_id in existing_document_ids or str(document.get("url") or "") in existing_urls:
            continue
        source_id = document_id.split(":", 1)[1] if ":" in document_id else ""
        source_type = document.get("source_type") or "news"
        credibility = 0.5
        published_at = None
        if document_id.startswith("article:"):
            article = db.get(models.Article, source_id)
            published_at = article.published_at if article else None
            credibility = 0.65 if source_type in {"official", "public"} else 0.52
        evidence = models.Evidence(
            claim_id=claim.id,
            credibility_score=credibility,
            evidence_text=str(row.get("evidence_text") or document.get("text") or "")[:2000],
            id=new_id("evidence"),
            published_at=published_at,
            relevance_score=_bounded_float(row.get("relevance_score")),
            retrieval_json={
                "documentId": document_id,
                "missingContext": row.get("missing_context"),
                "supports": row.get("supports"),
                "conflicts": row.get("conflicts"),
                "source": "deepseek",
            },
            source_domain=urlparse(str(document.get("url") or "")).netloc or str(document.get("publisher") or ""),
            source_type=str(source_type),
            title=str(row.get("title") or document.get("title") or "근거 후보")[:500],
            url=str(document.get("url") or ""),
        )
        db.add(evidence)
        evidences.append(evidence)
    if evidences:
        return [*existing, *evidences]

    source_domains = db.scalars(
        select(models.SourceDomain)
        .where(models.SourceDomain.status.in_(["trusted", "watch"]))
        .order_by(models.SourceDomain.credibility.desc())
        .limit(3),
    ).all()
    for source in source_domains:
        if not source.collection_url and source.source_type not in {"official", "public", "factcheck"}:
            continue
        source_url = source.collection_url or f"https://{source.domain}"
        if source_url in existing_urls:
            continue
        evidence = models.Evidence(
            claim_id=claim.id,
            credibility_score=source.credibility,
            evidence_text=f"{source.name} 출처에서 확인이 필요한 주장입니다.",
            id=new_id("evidence"),
            relevance_score=0.62 if source.source_type in {"official", "public"} else 0.48,
            source_domain=source.domain,
            source_type=source.source_type,
            title=f"{source.name} 근거 후보",
            url=source_url,
        )
        db.add(evidence)
        evidences.append(evidence)

    if claim.article_id:
        article = db.get(models.Article, claim.article_id)
        if article and article.url not in existing_urls:
            domain = urlparse(article.url).netloc
            evidence = models.Evidence(
                claim_id=claim.id,
                credibility_score=0.52,
                evidence_text=article.summary or article.title,
                id=new_id("evidence"),
                published_at=article.published_at,
                relevance_score=0.72,
                source_domain=domain,
                source_type=article.source_type,
                title=article.title,
                url=article.url,
            )
            db.add(evidence)
            evidences.append(evidence)
    return [*existing, *evidences]
