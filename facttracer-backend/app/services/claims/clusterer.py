from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.services.admin.settings import get_effective_setting
from app.services.articles.normalizer import jaccard_similarity
from app.utils import new_id


def _cluster_metadata(claim_text: str, claim_type: str) -> tuple[str, str, str]:
    text = claim_text.strip()
    if claim_type == "수치 주장" or any(keyword in text for keyword in ("곳", "명", "건", "개", "원", "%", "증가", "감소")):
        return "발생 규모와 수치", "발생 규모와 수치는 어느 기준으로 봐야 하는가?", "수치 주장"
    if claim_type == "책임 주장" or any(keyword in text for keyword in ("책임", "문책", "사과", "관리 부실", "감사")):
        return "책임 소재", "누가 어떤 책임을 져야 한다고 주장하는가?", "책임 주장"
    if claim_type == "원인 해석" or any(keyword in text for keyword in ("원인", "때문", "예측", "배분", "실패", "부실")):
        return "원인", "문제의 원인을 무엇으로 보는가?", "원인 해석"
    if claim_type == "법적 주장" or any(keyword in text for keyword in ("위법", "소송", "재판", "헌법", "무효", "재선거")):
        return "법적 쟁점", "법적 판단이 필요한 지점은 무엇인가?", "법적 주장"
    if claim_type == "요구 사항" or any(keyword in text for keyword in ("요구", "촉구", "개선", "조사", "규명", "재발 방지")):
        return "요구 사항", "어떤 후속 조치를 요구하는가?", "요구 사항"
    if claim_type == "의혹 주장" or any(keyword in text for keyword in ("의혹", "고의", "조작", "개입", "침투")):
        return "의혹과 검증 필요 주장", "확인 가능한 근거가 필요한 의혹은 무엇인가?", "의혹 주장"
    if claim_type == "운동 전략" or any(keyword in text for keyword in ("전략", "메시지", "프레임", "구호")):
        return "운동 전략", "어떤 메시지나 행동 전략을 주장하는가?", "운동 전략"
    if claim_type == "낙인 표현":
        return "위험 표현과 낙인", "공개 확산을 제한해야 할 표현은 무엇인가?", "낙인 표현"
    if any(keyword in text for keyword in ("사퇴", "사의", "위원장", "진상규명위", "출범", "대책")):
        return "기관 대응", "기관은 어떤 대응을 했는가?", "사실 주장"
    return "사실관계 확인", "현재 확인된 사실관계는 무엇인가?", claim_type


def _cluster_title(claim_text: str, claim_type: str) -> str:
    bucket_title, _, _ = _cluster_metadata(claim_text, claim_type)
    if bucket_title:
        return bucket_title
    compact = claim_text.strip()
    if len(compact) > 42:
        compact = compact[:39].rstrip() + "..."
    return compact or claim_type


def _bucket_cluster_for_claim(db: Session, *, claim: models.Claim) -> models.ClaimCluster:
    claim_text = claim.sanitized_text or claim.claim_text
    title, question, cluster_type = _cluster_metadata(claim_text, claim.claim_type)
    cluster = db.scalar(
        select(models.ClaimCluster).where(
            models.ClaimCluster.issue_id == claim.issue_id,
            models.ClaimCluster.title == title,
            models.ClaimCluster.cluster_type == cluster_type,
        ),
    )
    if cluster:
        cluster.canonical_question = cluster.canonical_question or question
        cluster.confidence = max(cluster.confidence, 0.72)
        cluster.status = "active"
        cluster.updated_at = models.now_utc()
        return cluster

    cluster = models.ClaimCluster(
        canonical_question=question,
        cluster_type=cluster_type,
        confidence=0.72,
        description="",
        id=new_id("cluster"),
        issue_id=claim.issue_id,
        status="active",
        title=title or _cluster_title(claim_text, claim.claim_type),
    )
    db.add(cluster)
    db.flush()
    return cluster


def find_similar_cluster(db: Session, *, issue_id: str, text: str) -> tuple[models.ClaimCluster | None, float]:
    threshold = get_effective_setting(db, "claim_similarity_threshold")
    clusters = db.scalars(select(models.ClaimCluster).where(models.ClaimCluster.issue_id == issue_id)).all()
    best: tuple[models.ClaimCluster | None, float] = (None, 0.0)
    for cluster in clusters:
        score = max(
            jaccard_similarity(text, cluster.title),
            jaccard_similarity(text, cluster.canonical_question),
            jaccard_similarity(text, cluster.description),
        )
        if score > best[1]:
            best = (cluster, score)
    if best[1] >= threshold:
        return best
    return None, best[1]


def assign_cluster(db: Session, *, claim: models.Claim) -> models.ClaimCluster:
    cluster = _bucket_cluster_for_claim(db, claim=claim)
    claim.cluster_id = cluster.id
    db.flush()
    return cluster


def rebuild_issue_claim_clusters(db: Session, *, issue_id: str) -> list[models.ClaimCluster]:
    claims = db.scalars(select(models.Claim).where(models.Claim.issue_id == issue_id)).all()
    used_cluster_ids: set[str] = set()
    for claim in claims:
        cluster = _bucket_cluster_for_claim(db, claim=claim)
        claim.cluster_id = cluster.id
        used_cluster_ids.add(cluster.id)

    clusters = db.scalars(select(models.ClaimCluster).where(models.ClaimCluster.issue_id == issue_id)).all()
    for cluster in clusters:
        if cluster.id not in used_cluster_ids:
            db.delete(cluster)
    db.flush()
    return [cluster for cluster in clusters if cluster.id in used_cluster_ids]
