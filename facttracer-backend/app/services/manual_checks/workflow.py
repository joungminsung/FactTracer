from __future__ import annotations

from sqlalchemy.orm import Session

from app import models
from app.db.session import SessionLocal
from app.services.articles.deduplicator import upsert_article
from app.services.articles.parser import fetch_and_parse_url, parse_article_content
from app.services.audit.logger import record_agent_run
from app.services.files.parser import extract_text_from_file
from app.services.manual_checks.input_parser import validate_manual_input
from app.services.manual_checks.youtube import fetch_youtube_transcript
from app.utils import new_id
from app.workers.issue_jobs import process_article


def create_manual_check(
    db: Session,
    *,
    content: str,
    input_type: str,
    issue_id: str | None = None,
    user_id: str | None = None,
) -> models.VerificationRequest:
    ok, reason = validate_manual_input(content=content, input_type=input_type)
    request = models.VerificationRequest(
        article_url=content if input_type == "url" else "",
        content=content,
        id=new_id("check"),
        input_type=input_type,
        issue_id=issue_id,
        status="queued" if ok else "rejected",
        user_id=user_id,
    )
    if not ok:
        request.ai_status = "rejected"
        request.ai_summary = reason
        db.add(request)
        db.flush()
        return request

    db.add(request)
    db.flush()
    return request


def process_manual_check_request(check_id: str) -> None:
    db = SessionLocal()
    try:
        request = db.get(models.VerificationRequest, check_id)
        if not request or request.status in {"cancelled", "rejected"}:
            return

        request.status = "running"
        request.ai_status = "processing"
        db.commit()

        input_type = request.input_type
        content = request.content
        issue_id = request.issue_id

        if input_type == "url":
            parsed = fetch_and_parse_url(content)
            article, _ = upsert_article(db, issue_id=issue_id, parsed=parsed, source_type="manual", url=content)
            request.matched_issue_id = article.issue_id
            request.result_issue_id = article.issue_id
            process_article(db, article=article)
        elif input_type == "text":
            parsed = parse_article_content(body_text=content, title=content[:80], url=f"manual://{request.id}")
            article, _ = upsert_article(
                db,
                issue_id=issue_id,
                parsed=parsed,
                source_type="manual_text",
                url=f"manual://{request.id}",
            )
            request.standalone_result_id = article.id
            process_article(db, article=article)
        elif input_type == "youtube":
            transcript, parse_status = fetch_youtube_transcript(content)
            parsed = parse_article_content(
                body_text=transcript,
                title=f"YouTube 검증 입력: {content}",
                url=content,
            )
            article, _ = upsert_article(
                db,
                issue_id=issue_id,
                parsed=parsed,
                source_type=f"youtube:{parse_status}",
                url=content,
            )
            request.parsed_content = {"transcriptStatus": parse_status, "textLength": len(transcript)}
            request.standalone_result_id = article.id
            process_article(db, article=article)
        elif input_type in {"image", "pdf", "file"}:
            uploaded = db.get(models.UploadedFile, content)
            if uploaded:
                text, parse_status = extract_text_from_file(
                    content_type=uploaded.content_type,
                    storage_url=uploaded.storage_url,
                )
                uploaded.extracted_text = text
                uploaded.parse_status = parse_status
                parsed = parse_article_content(
                    body_text=text,
                    title=uploaded.filename,
                    url=f"file://{uploaded.id}",
                )
                article, _ = upsert_article(
                    db,
                    issue_id=issue_id,
                    parsed=parsed,
                    source_type=f"file:{uploaded.content_type}",
                    url=f"file://{uploaded.id}",
                )
                request.uploaded_file_id = uploaded.id
                request.parsed_content = {"parseStatus": parse_status, "textLength": len(text)}
                request.standalone_result_id = article.id
                process_article(db, article=article)

        request.status = "completed"
        request.ai_status = "processed"
        db.commit()
    except Exception as exc:
        db.rollback()
        request = db.get(models.VerificationRequest, check_id)
        if request:
            request.status = "needs_review"
            request.ai_status = "failed"
            request.ai_summary = "자동 처리 중 일시 오류가 발생해 수동 검토로 전환했습니다."
        record_agent_run(
            db,
            agent="Manual Check Processor",
            error_message=str(exc),
            status="needs_review",
            target=check_id,
        )
        db.commit()
    finally:
        db.close()
