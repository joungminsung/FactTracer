from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app.services.articles.normalizer import normalize_whitespace, token_set
from app.services.issues.matcher import incident_similarity
from app.services.issues.publisher import slugify
from app.services.topics import normalize_topic
from app.utils import new_id


ELECTION_MAJOR_TOPIC_NAME = "2026 지방선거"
EVENT_GROUP_REUSE_THRESHOLD = 0.62

ELECTION_TERMS = (
    "선거",
    "선관위",
    "중앙선관위",
    "중앙선거관리위원회",
    "투표",
    "사전투표",
    "개표",
    "득표",
)
EQUAL_VOTE_TERMS = (
    "동일득표",
    "동일한득표",
    "득표동일",
    "득표수동일",
    "득표수가동일",
    "득표수치가동일",
    "같은득표",
    "같은표",
    "동수득표",
    "동수",
    "동률",
)
HIDDEN_OR_MERGED_STATUSES = ("숨김", "병합됨")


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", normalize_whitespace(text).lower())


def _compact_key(text: str) -> str:
    return re.sub(r"[^0-9a-zA-Z가-힣]+", "", normalize_whitespace(text).lower())


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    compact_text = _compact(text)
    return any(term.lower().replace(" ", "") in compact_text for term in terms)


def _is_ballot_shortage(text: str) -> bool:
    compact_text = _compact(text)
    has_ballot_term = "투표용지" in compact_text or "투표지" in compact_text
    return "선관위" in compact_text and has_ballot_term and "부족" in compact_text


def _is_incheon_equal_vote(text: str) -> bool:
    compact_text = _compact(text)
    return "인천" in compact_text and any(term in compact_text for term in EQUAL_VOTE_TERMS)


def _is_ready_korea_training(text: str) -> bool:
    compact_text = _compact_key(text)
    has_training = "훈련" in compact_text
    has_derailment = "탈선" in compact_text
    has_fuel_or_explosion = any(term in compact_text for term in ("유류누출", "항공유", "폭발"))
    has_context = any(term in compact_text for term in ("레디코리아", "행안부", "화물열차", "복합재난"))
    return has_training and has_derailment and has_fuel_or_explosion and has_context


def _fallback_event_group_name(text: str) -> str:
    normalized = normalize_whitespace(text)
    if not normalized:
        return "미분류 사건"

    first_sentence = re.split(r"[.!?。！？\n]", normalized, maxsplit=1)[0]
    words = first_sentence.split()
    if len(words) > 12:
        first_sentence = " ".join(words[:12])

    return first_sentence[:120].strip(" -:·,") or "미분류 사건"


def infer_taxonomy_topic(major_topic_name: str, text: str) -> str:
    if major_topic_name == ELECTION_MAJOR_TOPIC_NAME:
        return "정치"
    if normalize_whitespace(major_topic_name):
        return normalize_topic(major_topic_name)
    return normalize_topic(text)


def _keywords_for(text: str, *, max_items: int = 12) -> list[str]:
    tokens = sorted(token_set(text))
    return tokens[:max_items]


def _stable_id(db: Session, model: type, *, prefix: str, value: str) -> str:
    candidate = f"{prefix}_{slugify(value)[:64]}"
    row = db.get(model, candidate)
    if row is None:
        return candidate
    if getattr(row, "name", None) == value:
        return candidate
    return new_id(prefix)


def _merged_signal(existing: dict | None, additions: dict) -> tuple[dict, bool]:
    signal = dict(existing or {})
    changed = False
    for key, value in additions.items():
        if signal.get(key) != value:
            signal[key] = value
            changed = True
    return signal, changed


def infer_major_topic_name(text: str, *, now: datetime | None = None) -> str:
    _ = now
    normalized = normalize_whitespace(text)
    if _contains_any(normalized, ELECTION_TERMS):
        return ELECTION_MAJOR_TOPIC_NAME
    return f"{normalize_topic(normalized)} 주요 이슈"


def infer_event_group_name(text: str) -> str:
    normalized = normalize_whitespace(text)
    if _is_ballot_shortage(normalized):
        return "선관위 투표용지 부족 사태"
    if _is_incheon_equal_vote(normalized):
        return "인천 사전투표 동일 득표 논란"
    if _is_ready_korea_training(normalized):
        return "레디코리아 열차 탈선 항공유 폭발 대응 훈련"
    return _fallback_event_group_name(normalized)


def refresh_group_counts(db: Session, *, event_group: models.EventGroup) -> None:
    issue_ids = select(models.Issue.id).where(
        models.Issue.event_group_id == event_group.id,
        models.Issue.status.notin_(HIDDEN_OR_MERGED_STATUSES),
    )
    issue_count = int(
        db.scalar(
            select(func.count(models.Issue.id)).where(
                models.Issue.event_group_id == event_group.id,
                models.Issue.status.notin_(HIDDEN_OR_MERGED_STATUSES),
            ),
        )
        or 0,
    )
    article_count = int(
        db.scalar(select(func.count(models.Article.id)).where(models.Article.issue_id.in_(issue_ids))) or 0,
    )
    if event_group.issue_count != issue_count or event_group.article_count != article_count:
        event_group.issue_count = issue_count
        event_group.article_count = article_count
        event_group.updated_at = datetime.now(UTC)


def _issue_text(issue: models.Issue, *, title: str = "", summary: str = "") -> str:
    parts = [
        title,
        issue.title,
        summary,
        issue.summary,
        issue.topic,
    ]
    return normalize_whitespace(" ".join(part for part in parts if part))


def _get_or_create_major_topic(
    db: Session,
    *,
    name: str,
    text: str,
    topic: str,
    timestamp: datetime,
) -> tuple[models.MajorTopic, bool]:
    major_topic = db.scalar(select(models.MajorTopic).where(models.MajorTopic.name == name))
    keywords = ELECTION_TERMS if name == ELECTION_MAJOR_TOPIC_NAME else tuple(_keywords_for(text))
    if not major_topic:
        major_topic = models.MajorTopic(
            aliases_json=["지방선거"] if name == ELECTION_MAJOR_TOPIC_NAME else [],
            created_at=timestamp,
            id=_stable_id(db, models.MajorTopic, prefix="major", value=name),
            keywords_json=list(keywords),
            last_seen_at=timestamp,
            name=name,
            signal_json={"classifier": "deterministic", "matched": name},
            slug=slugify(name),
            summary=f"{name} 관련 이슈를 묶습니다.",
            topic=topic,
            updated_at=timestamp,
        )
        db.add(major_topic)
        db.flush()
        return major_topic, True

    changed = False
    if major_topic.topic != topic:
        major_topic.topic = topic
        changed = True
    if not major_topic.keywords_json:
        major_topic.keywords_json = list(keywords)
        changed = True
    if name == ELECTION_MAJOR_TOPIC_NAME and not major_topic.aliases_json:
        major_topic.aliases_json = ["지방선거"]
        changed = True
    signal, signal_changed = _merged_signal(
        major_topic.signal_json,
        {"classifier": "deterministic", "matched": name},
    )
    if signal_changed:
        major_topic.signal_json = signal
        changed = True
    if major_topic.status != "active":
        major_topic.status = "active"
        changed = True
    if changed:
        major_topic.updated_at = timestamp
        major_topic.last_seen_at = timestamp
    return major_topic, changed


def _event_group_similarity_text(event_group: models.EventGroup) -> str:
    parts = [
        event_group.name,
        event_group.summary,
        " ".join(str(item) for item in event_group.keywords_json or []),
        " ".join(str(item) for item in event_group.aliases_json or []),
    ]
    return normalize_whitespace(" ".join(part for part in parts if part))


def _find_reusable_event_group(
    db: Session,
    *,
    event_name: str,
    major_topic: models.MajorTopic,
    text: str,
) -> models.EventGroup | None:
    exact = db.scalar(
        select(models.EventGroup).where(
            models.EventGroup.major_topic_id == major_topic.id,
            models.EventGroup.name == event_name,
            models.EventGroup.status.notin_(HIDDEN_OR_MERGED_STATUSES),
        ),
    )
    if exact:
        return exact

    candidates = db.scalars(
        select(models.EventGroup).where(
            models.EventGroup.major_topic_id == major_topic.id,
            models.EventGroup.status.notin_(HIDDEN_OR_MERGED_STATUSES),
        ),
    ).all()
    left_text = normalize_whitespace(f"{event_name} {text}")
    best_group: models.EventGroup | None = None
    best_score = 0.0
    for candidate in candidates:
        score = incident_similarity(left_text, _event_group_similarity_text(candidate))
        if score > best_score:
            best_group = candidate
            best_score = score
    if best_group and best_score >= EVENT_GROUP_REUSE_THRESHOLD:
        return best_group
    return None


def _get_or_create_event_group(
    db: Session,
    *,
    event_name: str,
    major_topic: models.MajorTopic,
    text: str,
    topic: str,
    timestamp: datetime,
) -> tuple[models.EventGroup, bool]:
    event_group = _find_reusable_event_group(
        db,
        event_name=event_name,
        major_topic=major_topic,
        text=text,
    )
    if not event_group:
        event_group = models.EventGroup(
            aliases_json=[],
            created_at=timestamp,
            id=_stable_id(db, models.EventGroup, prefix="event", value=f"{major_topic.id}-{event_name}"),
            keywords_json=_keywords_for(text),
            last_seen_at=timestamp,
            major_topic_id=major_topic.id,
            name=event_name,
            signal_json={"classifier": "deterministic", "matched": event_name},
            slug=slugify(event_name),
            summary=text[:500],
            topic=topic,
            updated_at=timestamp,
        )
        db.add(event_group)
        db.flush()
        return event_group, True

    changed = False
    if event_group.major_topic_id != major_topic.id:
        event_group.major_topic_id = major_topic.id
        changed = True
    if event_group.topic != topic:
        event_group.topic = topic
        changed = True
    if not event_group.summary:
        event_group.summary = text[:500]
        changed = True
    if not event_group.keywords_json:
        event_group.keywords_json = _keywords_for(text)
        changed = True
    signal, signal_changed = _merged_signal(
        event_group.signal_json,
        {"classifier": "deterministic", "matched": event_name},
    )
    if signal_changed:
        event_group.signal_json = signal
        changed = True
    if event_group.status != "active":
        event_group.status = "active"
        changed = True
    if changed:
        event_group.updated_at = timestamp
        event_group.last_seen_at = timestamp
    return event_group, changed


def classify_issue_taxonomy(
    db: Session,
    *,
    event_group_name: str | None = None,
    issue: models.Issue,
    major_topic_name: str | None = None,
    title: str = "",
    summary: str = "",
) -> tuple[models.MajorTopic, models.EventGroup]:
    timestamp = datetime.now(UTC)
    text = _issue_text(issue, title=title, summary=summary)
    resolved_major_topic_name = normalize_whitespace(major_topic_name or "")[:200] or infer_major_topic_name(text, now=timestamp)
    resolved_event_group_name = normalize_whitespace(event_group_name or "")[:240] or infer_event_group_name(text)
    taxonomy_topic = infer_taxonomy_topic(resolved_major_topic_name, f"{text} {resolved_event_group_name}")
    previous_major_topic_id = issue.major_topic_id
    previous_event_group_id = issue.event_group_id

    major_topic, _ = _get_or_create_major_topic(
        db,
        name=resolved_major_topic_name,
        text=text,
        topic=taxonomy_topic,
        timestamp=timestamp,
    )
    event_group, _ = _get_or_create_event_group(
        db,
        event_name=resolved_event_group_name,
        major_topic=major_topic,
        text=text,
        topic=taxonomy_topic,
        timestamp=timestamp,
    )

    issue_changed = False
    issue_updates = {
        "event_group_id": event_group.id,
        "event_group_name": event_group.name,
        "major_topic_id": major_topic.id,
        "major_topic_name": major_topic.name,
        "topic": taxonomy_topic,
    }
    for field, value in issue_updates.items():
        if getattr(issue, field) != value:
            setattr(issue, field, value)
            issue_changed = True
    if issue_changed:
        issue.updated_at = timestamp
        issue.last_updated_at = timestamp

    db.flush()
    assignment_changed = (
        previous_major_topic_id != major_topic.id
        or previous_event_group_id != event_group.id
    )
    if assignment_changed:
        refresh_group_counts(db, event_group=event_group)
    if assignment_changed and previous_event_group_id and previous_event_group_id != event_group.id:
        previous_event_group = db.get(models.EventGroup, previous_event_group_id)
        if previous_event_group:
            refresh_group_counts(db, event_group=previous_event_group)
    db.flush()
    return major_topic, event_group
