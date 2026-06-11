from sqlalchemy.orm import Session

from app import models
from app.db.session import SessionLocal
from app.services.admin.recheck import reverify_issue_claims
from app.services.admin.settings import get_effective_setting
from app.services.articles.deduplicator import upsert_article
from app.services.articles.parser import fetch_and_parse_url, parse_article_content
from app.services.audit.logger import record_agent_run
from app.services.ai.deepseek_client import DeepSeekAnalysisService
from app.services.ai.openai_embeddings import OpenAIEmbeddingService
from app.services.claims.workflow import ingest_submitted_claim
from app.utils import new_id
from app.workers.issue_jobs import process_article


def process_verification_request(request_id: str) -> None:
    db = SessionLocal()
    try:
        if not get_effective_setting(db, "ai_processing_enabled"):
            return
        request = db.get(models.VerificationRequest, request_id)
        if not request:
            return

        embedding_service = OpenAIEmbeddingService(db)
        deepseek_service = DeepSeekAnalysisService(db)

        if not embedding_service.enabled and not deepseek_service.enabled:
            request.ai_status = "waiting_for_api_keys"
            record_agent_run(
                db,
                agent="Verification Processor",
                failure_reason="자동 처리 연결 정보가 없어 수동 검토로 전환했습니다.",
                status="needs_review",
                target=request.article_url,
            )
            db.commit()
            return

        analysis = deepseek_service.analyze_article_reference(request.article_url)
        embedding = embedding_service.embed_text(request.article_url)
        if request.input_type == "url" and request.article_url:
            parsed = fetch_and_parse_url(request.article_url)
            article, _ = upsert_article(
                db,
                issue_id=request.issue_id,
                parsed=parsed,
                source_type="manual",
                url=request.article_url,
            )
            process_article(db, article=article)
            request.matched_issue_id = article.issue_id or request.matched_issue_id
            request.result_issue_id = article.issue_id
        elif request.input_type == "text" and request.content:
            parsed = parse_article_content(
                body_text=request.content,
                title=request.content[:80],
                url=f"manual://{request.id}",
            )
            article, _ = upsert_article(
                db,
                issue_id=request.issue_id,
                parsed=parsed,
                source_type="manual_text",
                url=f"manual://{request.id}",
            )
            process_article(db, article=article)
            request.standalone_result_id = article.id
        request.ai_status = "processed"
        request.ai_summary = str(analysis or {})
        request.status = "completed"
        record_agent_run(
            db,
            agent="Verification Processor",
            input_json={"request_id": request.id, "input_type": request.input_type},
            issue_id=request.result_issue_id or request.matched_issue_id,
            output_json={"embedding_created": bool(embedding), "analysis": analysis or {}},
            status="completed",
            target=request.article_url,
        )
        db.commit()
    except Exception:
        record_agent_run(
            db,
            agent="Verification Processor",
            failure_reason="자동 처리 중 일시 오류가 발생해 수동 검토로 전환했습니다.",
            status="needs_review",
            target=request_id,
        )
        db.commit()
    finally:
        db.close()


def process_submitted_claim(claim_id: str) -> None:
    db = SessionLocal()
    try:
        if not get_effective_setting(db, "ai_processing_enabled"):
            return
        claim = db.get(models.SubmittedClaim, claim_id)
        if not claim:
            return

        embedding_service = OpenAIEmbeddingService(db)
        deepseek_service = DeepSeekAnalysisService(db)

        if embedding_service.enabled:
            claim.embedding = embedding_service.embed_text(
                f"{claim.claim_text}\n{claim.reason}\n{claim.refutable_point}",
            )
        if deepseek_service.enabled:
            structured = deepseek_service.structure_claim(claim.claim_text, claim.reason) or {}
            if structured:
                claim.ai_notes = structured
                claim.claim_type = str(structured.get("claim_type") or claim.claim_type)[:80]
                claim.refutable_point = str(structured.get("refutable_point") or claim.refutable_point)
            claim.status = "needs_review"
        normalized_claim = ingest_submitted_claim(db, submitted_claim=claim)

        if not embedding_service.enabled and not deepseek_service.enabled:
            record_agent_run(
                db,
                agent="Claim Structurer",
                failure_reason="자동 처리 연결 정보가 없어 수동 검토로 전환했습니다.",
                status="needs_review",
                target=claim.issue_id,
            )
        else:
            record_agent_run(
                db,
                agent="Claim Structurer",
                claim_id=normalized_claim.id,
                input_json={"submitted_claim_id": claim.id},
                issue_id=claim.issue_id,
                output_json={"cluster_id": normalized_claim.cluster_id, "moderation": claim.moderation_status},
                status="completed",
                target=claim.issue_id,
            )
        db.commit()
    except Exception:
        record_agent_run(
            db,
            agent="Claim Structurer",
            failure_reason="자동 처리 중 일시 오류가 발생해 수동 검토로 전환했습니다.",
            status="needs_review",
            target=claim_id,
        )
        db.commit()
    finally:
        db.close()


def process_reverification_request(issue_id: str, *, memo: str | None, priority: str) -> None:
    db = SessionLocal()
    try:
        if not get_effective_setting(db, "ai_processing_enabled"):
            return
        issue = db.get(models.Issue, issue_id)
        queue_item = db.get(models.AdminQueueItem, issue_id)
        title = issue.title if issue else queue_item.title if queue_item else issue_id
        deepseek_service = DeepSeekAnalysisService(db)

        if not deepseek_service.enabled:
            record_agent_run(
                db,
                agent="Reverification",
                failure_reason="자동 처리 연결 정보가 없어 수동 검토로 전환했습니다.",
                status="needs_review",
                target=issue_id,
            )
            db.commit()
            return

        review = deepseek_service.review_issue_reverification(
            issue_title=title,
            memo=memo,
            priority=priority,
        )
        claim_count = reverify_issue_claims(db, issue_id=issue_id)
        record_agent_run(
            db,
            agent="Reverification",
            input_json={"memo": memo, "priority": priority},
            issue_id=issue_id,
            output_json={"review": review or {}, "claim_count": claim_count},
            status="completed",
            target=issue_id,
        )
        db.commit()
    except Exception:
        record_agent_run(
            db,
            agent="Reverification",
            failure_reason="자동 처리 중 일시 오류가 발생해 수동 검토로 전환했습니다.",
            status="needs_review",
            target=issue_id,
        )
        db.commit()
    finally:
        db.close()
