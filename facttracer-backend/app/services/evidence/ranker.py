from __future__ import annotations

from app import models


SOURCE_BONUS = {
    "official": 0.2,
    "public": 0.16,
    "factcheck": 0.12,
    "news": 0.04,
}


def rank_evidence(evidence: models.Evidence) -> float:
    score = evidence.credibility_score * 0.55 + evidence.relevance_score * 0.35
    score += SOURCE_BONUS.get(evidence.source_type, 0.0)
    return max(0.0, min(score, 1.0))


def sort_evidences(evidences: list[models.Evidence]) -> list[models.Evidence]:
    return sorted(evidences, key=rank_evidence, reverse=True)
