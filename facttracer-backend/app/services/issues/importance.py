from __future__ import annotations

from app import models


HIGH_SENSITIVITY_TOPICS = {"정치", "재난", "보건", "경제"}


def _safe_number(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def calculate_issue_importance(issue: models.Issue) -> int:
    article_count = _safe_number(issue.article_count)
    cluster_count = _safe_number(issue.cluster_count)
    verified_count = _safe_number(issue.verified_count)
    quality_score = _safe_number(issue.quality_score)
    base_score = _safe_number(issue.issue_score)

    score = 20.0
    score += min(article_count, 80) * 0.35
    score += min(cluster_count * 10, 25)
    score += min(verified_count * 4, 20)
    score += min(base_score * 0.15, 15)
    score += max(0, quality_score - 70) * 0.15
    if issue.topic in HIGH_SENSITIVITY_TOPICS:
        score += 8
    elif issue.topic == "국제":
        score += 5

    if issue.quality_status and issue.quality_status != "sufficient":
        score -= 10
    if quality_score and quality_score < 70:
        score -= 12
    if cluster_count == 0:
        score -= 25
    if verified_count == 0:
        score -= 10
    if article_count < 4:
        score -= 8

    return max(0, min(100, int(round(score))))


def apply_issue_importance(issue: models.Issue) -> int:
    score = calculate_issue_importance(issue)
    issue.issue_score = score
    issue.risk = "고영향" if score >= 75 else "일반"
    return score
