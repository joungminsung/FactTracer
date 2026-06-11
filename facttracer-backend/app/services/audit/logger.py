from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app import models
from app.utils import new_id


def record_agent_run(
    db: Session,
    *,
    agent: str,
    article_id: str | None = None,
    claim_id: str | None = None,
    error_message: str = "",
    failure_reason: str = "",
    input_json: dict | None = None,
    issue_id: str | None = None,
    output_json: dict | None = None,
    started_at: datetime | None = None,
    status: str,
    target: str = "",
) -> models.AgentRun:
    finished_at = datetime.now(UTC)
    started = started_at or finished_at
    run = models.AgentRun(
        agent=agent,
        agent_name=agent,
        article_id=article_id,
        claim_id=claim_id,
        duration_ms=max(0, int((finished_at - started).total_seconds() * 1000)),
        error_message=error_message or failure_reason,
        failure_reason=failure_reason or error_message,
        finished_at=finished_at,
        id=new_id("run"),
        input_json=input_json or {},
        issue_id=issue_id,
        output_json=output_json or {},
        started_at=started,
        status=status,
        target=target,
    )
    db.add(run)
    db.flush()
    return run
