from __future__ import annotations

from collections import defaultdict

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app import models
from app.services.ai.deepseek_client import DeepSeekAnalysisService
from app.services.safety.label_filter import sanitize_public_label
from app.utils import new_id


PERSPECTIVE_NAMES = {
    "수치 주장": "수치 기준 확인 관점",
    "원인 해석": "원인 분석 관점",
    "책임 주장": "관리 책임 검토 관점",
    "법적 주장": "법적 절차 검토 관점",
    "요구 사항": "후속 조치 요구 관점",
    "의혹 주장": "근거 필요 의혹 관점",
    "운동 전략": "메시지 전략 관점",
    "낙인 표현": "위험 표현 정제 관점",
}


def _list_from_ai(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def rebuild_perspectives(db: Session, *, issue_id: str) -> list[models.Perspective]:
    issue = db.get(models.Issue, issue_id)
    claims = db.scalars(select(models.Claim).where(models.Claim.issue_id == issue_id)).all()
    ai_rows = DeepSeekAnalysisService(db).build_perspectives(
        issue_title=issue.title if issue else issue_id,
        claims=[
            {
                "id": claim.id,
                "text": claim.sanitized_text or claim.claim_text,
                "claim_type": claim.claim_type,
                "verdict": claim.verdict,
                "confidence": claim.confidence,
            }
            for claim in claims
        ],
    )
    if ai_rows:
        db.execute(delete(models.Perspective).where(models.Perspective.issue_id == issue_id))
        perspectives: list[models.Perspective] = []
        for row in ai_rows[:8]:
            perspective = models.Perspective(
                common_ground_json=_list_from_ai(row.get("common_ground") or row.get("commonGround"))[:5],
                conflicts_json=_list_from_ai(row.get("conflicts"))[:5],
                core_arguments_json=_list_from_ai(row.get("core_arguments") or row.get("coreArguments"))[:5],
                id=new_id("perspective"),
                issue_id=issue_id,
                name=sanitize_public_label(str(row.get("name") or "검증 관점"))[:200],
                summary=str(row.get("summary") or "")[:1200],
            )
            db.add(perspective)
            perspectives.append(perspective)
        db.flush()
        return perspectives

    grouped: dict[str, list[models.Claim]] = defaultdict(list)
    for claim in claims:
        grouped[claim.claim_type].append(claim)
    db.execute(delete(models.Perspective).where(models.Perspective.issue_id == issue_id))
    perspectives: list[models.Perspective] = []
    for claim_type, rows in grouped.items():
        name = sanitize_public_label(PERSPECTIVE_NAMES.get(claim_type, f"{claim_type} 관점"))
        arguments = [row.sanitized_text or row.claim_text for row in rows[:5]]
        conflicts = [
            row.sanitized_text or row.claim_text
            for row in rows
            if row.verdict in {"근거 부족", "단정 불가", "업데이트 필요", "법적 판단 필요"}
        ][:5]
        perspective = models.Perspective(
            common_ground_json=["검증 가능한 주장 단위로 근거를 확인해야 합니다."],
            conflicts_json=conflicts,
            core_arguments_json=arguments,
            id=new_id("perspective"),
            issue_id=issue_id,
            name=name,
            summary=arguments[0] if arguments else "관련 주장을 수집 중입니다.",
        )
        db.add(perspective)
        perspectives.append(perspective)
    db.flush()
    return perspectives
