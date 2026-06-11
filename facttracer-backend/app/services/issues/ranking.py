from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any

from app import models
from app.services.topics import normalize_topic

SORT_MODES = {
    "recommended",
    "latest",
    "controversial",
    "highImpact",
    "needsReview",
    "officialUpdated",
    "personalized",
}


def _safe_number(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return number if math.isfinite(number) else 0.0


def _clamp(value: float, lower: float = 0.0, upper: float = 100.0) -> float:
    return max(lower, min(upper, value))


def _freshness_score(issue: models.Issue) -> float:
    updated_at = issue.updated_at
    if not updated_at:
        return 0.0
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=UTC)
    age_hours = max((datetime.now(UTC) - updated_at).total_seconds() / 3600, 0.0)
    return _clamp(100 - (age_hours * 4))


def _controversy_score(issue: models.Issue) -> float:
    return _clamp(
        (_safe_number(issue.needs_review_count) * 8)
        + (_safe_number(issue.changed_claims) * 10)
        + (_safe_number(issue.cluster_count) * 3)
        + min(_safe_number(issue.article_count), 40)
        + (_safe_number(issue.issue_score) * 0.2),
    )


def _impact_score(issue: models.Issue) -> float:
    topic = normalize_topic(issue.topic)
    topic_bonus = 12 if topic in {"정치", "경제", "사회", "재난", "보건", "국제", "IT"} else 0
    risk_bonus = 12 if issue.risk in {"고영향", "높음", "high"} else 0
    taxonomy_bonus = 8 if issue.major_topic_name or issue.event_group_name else 0
    return _clamp(_safe_number(issue.issue_score) + topic_bonus + risk_bonus + taxonomy_bonus)


def _verification_score(issue: models.Issue) -> float:
    review_pressure = min(_safe_number(issue.needs_review_count) * 12, 60)
    unresolved_ratio = 0.0
    cluster_count = _safe_number(issue.cluster_count)
    if cluster_count:
        unresolved_ratio = max(cluster_count - _safe_number(issue.verified_count), 0) / cluster_count
    return _clamp(review_pressure + (unresolved_ratio * 25) + (_safe_number(issue.changed_claims) * 5))


def _quality_penalty(issue: models.Issue) -> float:
    penalty = 0.0
    if issue.quality_status and issue.quality_status != "sufficient":
        penalty += 18
    if _safe_number(issue.cluster_count) == 0:
        penalty += 16
    if _safe_number(issue.verified_count) == 0:
        penalty += 10
    if _safe_number(issue.article_count) >= 50 and _safe_number(issue.cluster_count) <= 1:
        penalty += min(_safe_number(issue.article_count) / 10, 28)
    if issue.quality_score and _safe_number(issue.quality_score) < 80:
        penalty += (80 - _safe_number(issue.quality_score)) * 0.35
    return _clamp(penalty, upper=70)


def _momentum_score(issue: models.Issue) -> float:
    return _clamp(
        (_safe_number(issue.changed_claims) * 18)
        + min(_safe_number(issue.article_count) * 2, 50)
        + (_safe_number(issue.issue_score) * 0.15),
    )


def _official_update_score(issue: models.Issue) -> float:
    documents = issue.source_documents if isinstance(issue.source_documents, list) else []
    official_count = sum(
        1
        for source in documents
        if isinstance(source, dict)
        and str(source.get("sourceType", "")).lower() in {"official", "public", "statistics", "law"}
    )
    return _clamp(
        (official_count * 30)
        + (_safe_number(issue.changed_claims) * 10)
        + (_safe_number(issue.issue_score) * 0.2),
    )


def _weight_lookup(weights: Any, *keys: str | None) -> float:
    if not isinstance(weights, dict):
        return 0.0
    for key in keys:
        if key and key in weights:
            return _safe_number(weights[key])
    return 0.0


def _personal_preference_score(
    issue: models.Issue,
    user: models.User | None,
    interest_profile: models.UserInterestProfile | None = None,
) -> float:
    preferences = user.preferences if user and isinstance(user.preferences, dict) else {}
    topic_weights = preferences.get("topicWeights") or preferences.get("topic_weights") or {}
    major_weights = preferences.get("majorTopicWeights") or preferences.get("major_topic_weights") or {}
    event_weights = preferences.get("eventGroupWeights") or preferences.get("event_group_weights") or {}
    profile_topic_weights = interest_profile.topic_weights_json if interest_profile else {}
    profile_major_weights = interest_profile.major_topic_weights_json if interest_profile else {}
    profile_event_weights = interest_profile.event_group_weights_json if interest_profile else {}
    profile_publisher_weights = interest_profile.publisher_weights_json if interest_profile else {}
    publisher_weights = preferences.get("publisherWeights") or preferences.get("publisher_weights") or {}
    article_publishers = [
        str(article.get("publisher") or "")
        for article in (issue.articles if isinstance(issue.articles, list) else [])
        if isinstance(article, dict)
    ]
    publisher_score = max(
        [
            _weight_lookup(publisher_weights, publisher)
            + _weight_lookup(profile_publisher_weights, publisher)
            for publisher in article_publishers
        ],
        default=0.0,
    )
    score = (
        (
            _weight_lookup(topic_weights, normalize_topic(issue.topic), issue.topic)
            + _weight_lookup(profile_topic_weights, normalize_topic(issue.topic), issue.topic)
        )
        * 12
        + (
            _weight_lookup(major_weights, issue.major_topic_id, issue.major_topic_name)
            + _weight_lookup(profile_major_weights, issue.major_topic_id, issue.major_topic_name)
        )
        * 14
        + (
            _weight_lookup(event_weights, issue.event_group_id, issue.event_group_name)
            + _weight_lookup(profile_event_weights, issue.event_group_id, issue.event_group_name)
        )
        * 16
        + publisher_score * 6
    )
    return _clamp(score)


def issue_ranking_signals(
    issue: models.Issue,
    *,
    interest_profile: models.UserInterestProfile | None = None,
    user: models.User | None = None,
) -> dict[str, float]:
    return {
        "controversy": _controversy_score(issue),
        "freshness": _freshness_score(issue),
        "impact": _impact_score(issue),
        "momentum": _momentum_score(issue),
        "officialUpdate": _official_update_score(issue),
        "personal": _personal_preference_score(issue, user, interest_profile),
        "qualityPenalty": _quality_penalty(issue),
        "verification": _verification_score(issue),
    }


def score_issue(
    issue: models.Issue,
    *,
    interest_profile: models.UserInterestProfile | None = None,
    sort: str,
    user: models.User | None = None,
) -> tuple[float, str]:
    mode = sort if sort in SORT_MODES else "recommended"
    signals = issue_ranking_signals(issue, interest_profile=interest_profile, user=user)
    freshness = signals["freshness"]
    controversy = signals["controversy"]
    impact = signals["impact"]
    verification = signals["verification"]
    momentum = signals["momentum"]
    official_update = signals["officialUpdate"]
    personal = signals["personal"]
    quality_penalty = signals["qualityPenalty"]

    if mode == "latest":
        score = freshness
        reason = "최근 업데이트"
    elif mode == "controversial":
        score = controversy + (impact * 0.2) + (freshness * 0.1)
        reason = "충돌 신호와 검토 필요도가 높음"
    elif mode == "highImpact":
        score = impact + (controversy * 0.25)
        reason = "사회적 영향도와 확산 신호가 큼"
    elif mode == "needsReview":
        score = verification + (controversy * 0.2)
        reason = "검토 대기 주장과 미검증 쟁점이 많음"
    elif mode == "officialUpdated":
        score = official_update + (freshness * 0.2)
        reason = "공식 자료 또는 공공 데이터 업데이트 반영"
    elif mode == "personalized":
        score = (
            (impact * 0.25)
            + (controversy * 0.2)
            + (freshness * 0.2)
            + (momentum * 0.15)
            + personal
        )
        reason = "관심사와 이슈 신호를 함께 반영"
    else:
        score = (
            (impact * 0.3)
            + (controversy * 0.25)
            + (freshness * 0.2)
            + (verification * 0.15)
            + (momentum * 0.1)
        )
        reason = "영향도, 논란도, 최신성 종합"

    return round(_clamp(score - quality_penalty), 3), reason


def rank_issues(
    issues: list[models.Issue],
    *,
    interest_profile: models.UserInterestProfile | None = None,
    sort: str = "recommended",
    user: models.User | None = None,
) -> list[models.Issue]:
    mode = sort if sort in SORT_MODES else "recommended"
    ranked: list[tuple[float, models.Issue]] = []
    for issue in issues:
        score, reason = score_issue(issue, interest_profile=interest_profile, sort=mode, user=user)
        issue._rank_metadata = {
            "rankScore": score,
            "rankReason": reason,
            "rankMode": mode,
            "rankedAt": datetime.now(UTC).isoformat(),
        }
        ranked.append((score, issue))
    return [
        issue
        for _, issue in sorted(
            ranked,
            key=lambda item: (
                item[0],
                item[1].updated_at or datetime.min.replace(tzinfo=UTC),
                item[1].id,
            ),
            reverse=True,
        )
    ]
