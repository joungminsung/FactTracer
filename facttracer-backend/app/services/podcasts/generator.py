from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.services.admin.settings import get_effective_setting
from app.services.issues.page_builder import build_issue_cache_payload
from app.services.podcasts.script_ai import OpenAIPodcastScriptGenerator
from app.services.issues.ranking import issue_ranking_signals, score_issue
from app.services.topics import normalize_topic, normalize_topic_filter
from app.utils import new_id


FEED_SORT_MODES = {
    "category": "recommended",
    "daily": "latest",
    "featured": "highImpact",
    "urgent": "needsReview",
    "latest": "latest",
    "personalized": "personalized",
    "ranking": "highImpact",
    "recommended": "recommended",
}

CATEGORY_FEED_TOPICS = ["정치", "경제", "사회", "국제", "재난", "보건", "IT"]
SENSITIVE_TOPICS = {"정치", "재난", "보건", "범죄", "선거"}
SUPPORTED_VARIANTS = {"short", "standard", "deep"}
VARIANT_LABELS = {
    "short": "짧은 브리핑",
    "standard": "표준 회차",
    "deep": "심층 정리",
}
SPECULATIVE_TERMS = ["확정적으로", "무조건", "조작이 분명", "고의가 분명", "범인"]
RISKY_EXPRESSION_PATTERNS: list[tuple[str, str]] = [
    (r"(무조건|반드시|틀림없이|100%|백퍼)", "absolute_claim"),
    (r"(조작|고의|은폐|사기).{0,12}(분명|확실|명백)", "unverified_intent"),
    (r"(분명|확실|명백).{0,12}(조작|고의|은폐|사기)", "unverified_intent"),
    (r"(범인|주범|배후|공범)", "identity_label"),
    (r"(확정|단정).{0,12}(범죄|위법|불법)", "legal_conclusion"),
]

DOMAIN_SOURCE_LABELS = {
    "law.go.kr": "국가법령정보센터",
    "kostat.go.kr": "통계청",
    "mofa.go.kr": "외교부",
    "nec.go.kr": "중앙선거관리위원회",
    "news.google.com": "구글 뉴스",
}

HOST_PRESETS = {
    "경제": [
        ("anchor", "서연", "진행", "숫자와 생활 영향을 차분히 정리"),
        ("analyst", "도윤", "경제 해설", "수치와 기준을 비교"),
        ("reporter", "하린", "현장 맥락", "정책 변화의 맥락을 보강"),
    ],
    "국제": [
        ("anchor", "민재", "진행", "국제 이슈를 균형 있게 정리"),
        ("analyst", "유진", "외신 검증", "출처와 이해관계를 비교"),
        ("reporter", "태오", "지역 맥락", "현지 시점과 배경을 보강"),
    ],
    "재난": [
        ("anchor", "지우", "진행", "피해와 안전 정보를 우선 정리"),
        ("analyst", "현우", "자료 검증", "공식 발표와 숫자를 확인"),
        ("reporter", "서아", "현장 브리핑", "확인된 사실과 미확인 정보를 분리"),
    ],
    "정치": [
        ("anchor", "지민", "진행", "발언과 공식 기록을 분리"),
        ("analyst", "준호", "팩트체크", "주장과 근거를 대조"),
        ("reporter", "나윤", "맥락 정리", "제도와 절차를 설명"),
    ],
    "IT": [
        ("anchor", "유하", "진행", "기술 발표와 생활 영향을 연결"),
        ("analyst", "태린", "기술 검증", "제품, 정책, 보안 근거를 대조"),
        ("reporter", "이준", "산업 맥락", "시장과 이용자 영향을 보강"),
    ],
}

DEFAULT_HOSTS = [
    ("anchor", "은서", "진행", "핵심 사실을 간결하게 정리"),
    ("analyst", "시우", "검증", "근거와 반론을 비교"),
    ("reporter", "라온", "맥락", "일상 영향과 후속 확인점을 보강"),
]


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _feed_sort(feed: str, *, user: models.User | None = None) -> str:
    mode = FEED_SORT_MODES.get(feed, "recommended")
    if mode == "personalized" and user is None:
        return "recommended"
    return mode


def _float_setting(db: Session, key: str, default: float) -> float:
    try:
        return float(get_effective_setting(db, key, default) or 0)
    except (TypeError, ValueError):
        return default


def _podcast_recommendation_weights(db: Session) -> dict[str, float]:
    weights = {
        "controversy": max(0.0, _float_setting(db, "podcast_recommendation_controversy_weight", 0.10)),
        "freshness": max(0.0, _float_setting(db, "podcast_recommendation_freshness_weight", 0.20)),
        "impact": max(0.0, _float_setting(db, "podcast_recommendation_impact_weight", 0.35)),
        "momentum": max(0.0, _float_setting(db, "podcast_recommendation_momentum_weight", 0.10)),
        "verification": max(0.0, _float_setting(db, "podcast_recommendation_verification_weight", 0.25)),
    }
    total = sum(weights.values())
    if total <= 0:
        return {
            "controversy": 0.10,
            "freshness": 0.20,
            "impact": 0.35,
            "momentum": 0.10,
            "verification": 0.25,
        }
    return {key: value / total for key, value in weights.items()}


def _weighted_score(signals: dict[str, float], weights: dict[str, float]) -> float:
    return sum(float(signals.get(key) or 0) * weight for key, weight in weights.items())


def _podcast_score_issue(
    db: Session,
    issue: models.Issue,
    *,
    interest_profile: models.UserInterestProfile | None,
    sort: str,
    user: models.User | None,
) -> tuple[float, str, dict[str, Any]]:
    signals = issue_ranking_signals(issue, interest_profile=interest_profile, user=user)
    if sort == "recommended":
        weights = _podcast_recommendation_weights(db)
        score = _weighted_score(signals, weights)
        return (
            round(score, 3),
            "사회적 영향도, 검증 필요도, 최신성 우선",
            {"signals": signals, "weights": weights},
        )
    if sort == "personalized":
        weights = _podcast_recommendation_weights(db)
        interest_weight = max(0.0, min(1.0, _float_setting(db, "podcast_personalization_interest_weight", 0.35)))
        base_score = _weighted_score(signals, weights)
        score = (base_score * (1 - interest_weight)) + (signals["personal"] * interest_weight)
        return (
            round(score, 3),
            "관심사와 공익성 신호를 함께 반영",
            {
                "interestWeight": interest_weight,
                "signals": signals,
                "weights": weights,
            },
        )
    score, reason = score_issue(issue, interest_profile=interest_profile, sort=sort, user=user)
    return score, reason, {"signals": signals}


def _rank_podcast_issues(
    db: Session,
    issues: list[models.Issue],
    *,
    interest_profile: models.UserInterestProfile | None = None,
    sort: str = "recommended",
    user: models.User | None = None,
) -> list[models.Issue]:
    ranked: list[tuple[float, models.Issue]] = []
    for issue in issues:
        score, reason, metadata = _podcast_score_issue(
            db,
            issue,
            interest_profile=interest_profile,
            sort=sort,
            user=user,
        )
        issue._rank_metadata = {
            "rankMode": sort,
            "rankReason": reason,
            "rankScore": score,
            "rankedAt": _now_iso(),
            **metadata,
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


def _episode_format(issue: models.Issue, requested: str | None = None) -> str:
    if requested in {"solo", "panel_2", "panel_3"}:
        return requested
    if issue.changed_claims > 0 or issue.needs_review_count >= 6 or issue.issue_score >= 90:
        return "panel_3"
    if normalize_topic(issue.topic) in {"정치", "경제", "국제", "재난", "IT"}:
        return "panel_2"
    return "solo"


def _hosts(issue: models.Issue, episode_format: str) -> list[dict[str, str]]:
    presets = HOST_PRESETS.get(normalize_topic(issue.topic), DEFAULT_HOSTS)
    count = 1 if episode_format == "solo" else 2 if episode_format == "panel_2" else 3
    return [
        {
            "id": host_id,
            "name": name,
            "role": role,
            "tone": tone,
        }
        for host_id, name, role, tone in presets[:count]
    ]


def _source_rows(issue: models.Issue, cache: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = cache.get("source_documents") or issue.source_documents or []
    if not candidates:
        candidates = cache.get("evidences") or issue.evidences or []
    if not candidates:
        candidates = cache.get("articles") or issue.articles or []

    rows: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for index, source in enumerate(candidates):
        if not isinstance(source, dict):
            continue
        url = str(source.get("url") or "").strip()
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        rows.append(
            {
                "id": str(source.get("id") or f"source_{index + 1}"),
                "title": str(source.get("title") or source.get("label") or "원문 자료"),
                "publisher": str(source.get("publisher") or source.get("source") or source.get("outlet") or ""),
                "url": url,
                "sourceType": str(source.get("sourceType") or source.get("source_type") or "media"),
                "credibility": float(source.get("credibility") or 0.55),
            },
        )
        if len(rows) >= 6:
            break
    return rows


def _source_label(source: dict[str, Any] | None) -> str:
    if not isinstance(source, dict):
        return "원문 자료"
    title = str(source.get("title") or "").strip()
    raw_publisher = str(source.get("publisher") or source.get("source") or source.get("outlet") or "").strip()
    compact_publisher = raw_publisher.removeprefix("www.").lower()
    if compact_publisher == "news.google.com" and " - " in title:
        outlet = title.rsplit(" - ", 1)[-1].strip()
        if outlet:
            return outlet
    label = DOMAIN_SOURCE_LABELS.get(compact_publisher, raw_publisher or title)
    return label or "원문 자료"


def _source_attribution(sources: list[dict[str, Any]]) -> str:
    preferred = next(
        (
            source
            for source in sources
            if str(source.get("sourceType") or "").lower() in {"media", "news", "news_search", "rss"}
        ),
        sources[0] if sources else None,
    )
    return f"{_source_label(preferred)}에 따르면"


def _source_list_text(sources: list[dict[str, Any]], *, limit: int = 4) -> str:
    labels: list[str] = []
    for source in sources:
        label = _source_label(source)
        if label not in labels:
            labels.append(label)
        if len(labels) >= limit:
            break
    if not labels:
        return "연결된 원문 자료"
    if len(labels) == 1:
        return labels[0]
    return ", ".join(labels[:-1]) + f", {labels[-1]}"


def _source_is_official(source: dict[str, Any]) -> bool:
    return str(source.get("sourceType") or "").lower() in {"official", "public", "statistics", "law"}


def _episode_variant(requested: str | None = None) -> str:
    return requested if requested in SUPPORTED_VARIANTS else "standard"


def _script_version(variant: str) -> str:
    return f"deterministic-v3-talkshow-{variant}"


def _ai_script_version(variant: str) -> str:
    return f"openai-ai-v1-{variant}"


def _expression_risk_findings(text: str) -> list[dict[str, str]]:
    compact = " ".join(text.split())
    findings: list[dict[str, str]] = []
    for term in SPECULATIVE_TERMS:
        if term in compact:
            findings.append({"category": "speculative_term", "match": term})
    for pattern, category in RISKY_EXPRESSION_PATTERNS:
        for match in re.finditer(pattern, compact):
            findings.append({"category": category, "match": match.group(0)})
    deduped: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for finding in findings:
        key = (finding["category"], finding["match"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(finding)
    return deduped


def _sanitize_script_text(text: str) -> tuple[str, list[dict[str, str]]]:
    cleaned = " ".join(text.split())
    findings = _expression_risk_findings(cleaned)
    for term in SPECULATIVE_TERMS:
        cleaned = cleaned.replace(term, "확인 필요")
    cleaned = re.sub(r"(무조건|반드시|틀림없이|100%|백퍼)", "확인된 근거 범위에서", cleaned)
    cleaned = re.sub(r"(조작|고의|은폐|사기)(.{0,12})(분명|확실|명백)", r"\1 여부는 확인 필요", cleaned)
    cleaned = re.sub(r"(분명|확실|명백)(.{0,12})(조작|고의|은폐|사기)", r"\3 여부는 확인 필요", cleaned)
    return cleaned, findings


def _clean_script_text(text: str) -> str:
    cleaned, _ = _sanitize_script_text(text)
    return cleaned


def _spoken_polite(text: str) -> str:
    cleaned = " ".join(str(text or "").split()).strip()
    if not cleaned:
        return ""
    cleaned = cleaned.rstrip()
    if cleaned.endswith(("습니다.", "습니까?", "세요.", "세요?", "이에요.", "예요.", "입니다.", "입니다?", "니다.", "까요?", "네요.", "죠.", "요.", "요?")):
        return cleaned

    replacements = [
        (r"했다\.?$", "했습니다."),
        (r"하였다\.?$", "했습니다."),
        (r"됐다\.?$", "됐습니다."),
        (r"되었다\.?$", "됐습니다."),
        (r"진행됐다\.?$", "진행됐습니다."),
        (r"재현되었다\.?$", "재현됐습니다."),
        (r"운영 중이다\.?$", "운영 중입니다."),
        (r"제기됨\.?$", "제기되고 있습니다."),
        (r"가능성이 제기됨\.?$", "가능성이 제기되고 있습니다."),
        (r"논란\.?$", "논란입니다."),
        (r"발표\.?$", "발표했습니다."),
        (r"보인다\.?$", "보입니다."),
        (r"필요하다\.?$", "필요합니다."),
        (r"중이다\.?$", "중입니다."),
        (r"있다\.?$", "있습니다."),
        (r"없다\.?$", "없습니다."),
        (r"아니다\.?$", "아닙니다."),
        (r"된다\.?$", "됩니다."),
    ]
    for pattern, replacement in replacements:
        updated = re.sub(pattern, replacement, cleaned)
        if updated != cleaned:
            return updated
    if cleaned.endswith("?"):
        return cleaned
    return f"{cleaned.rstrip('.')}입니다."


def _source_refs(
    sources: list[dict[str, Any]],
    *,
    limit: int = 3,
    reason: str,
    prefer_official: bool = False,
) -> list[dict[str, Any]]:
    ordered = sorted(
        sources,
        key=lambda source: (
            0 if prefer_official and _source_is_official(source) else 1,
            -float(source.get("credibility") or 0),
        ),
    )
    refs: list[dict[str, Any]] = []
    for source in ordered[:limit]:
        source_id = str(source.get("id") or "").strip()
        if not source_id:
            continue
        refs.append(
            {
                "publisher": str(source.get("publisher") or ""),
                "reason": reason,
                "sourceId": source_id,
                "sourceType": str(source.get("sourceType") or "media"),
            },
        )
    return refs


def _ai_source_ids(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value] if value.strip() else []
    if not isinstance(value, list):
        return []
    ids: list[str] = []
    for item in value:
        source_id = str(item or "").strip()
        if source_id and source_id not in ids:
            ids.append(source_id)
    return ids


def _ai_source_refs(
    source_ids: list[str],
    *,
    fallback_sources: list[dict[str, Any]],
    reason: str,
    source_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for source_id in source_ids:
        source = source_by_id.get(source_id)
        if not source:
            continue
        refs.append(
            {
                "publisher": str(source.get("publisher") or ""),
                "reason": reason,
                "sourceId": source_id,
                "sourceType": str(source.get("sourceType") or "media"),
            },
        )
    if refs:
        return refs[:4]
    return _source_refs(fallback_sources, reason=reason, limit=3, prefer_official=True)


def _normalize_ai_script(
    payload: dict[str, Any] | None,
    *,
    fallback_sources: list[dict[str, Any]],
    hosts: list[dict[str, str]],
    issue_source_ids: dict[str, set[str]] | None = None,
    min_source_attributions: int = 1,
    reason: str,
    required_issue_ids: list[str] | None = None,
    sources: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    raw_script = payload.get("script")
    if not isinstance(raw_script, list):
        return []

    host_by_id = {host["id"]: host for host in hosts if host.get("id")}
    source_by_id = {
        str(source.get("id") or ""): source
        for source in sources
        if isinstance(source, dict) and str(source.get("id") or "").strip()
    }
    segments: list[dict[str, Any]] = []
    required_issues = {issue_id for issue_id in (required_issue_ids or []) if issue_id}
    source_ids_by_issue = issue_source_ids or {}
    issue_attributions: set[str] = set()
    used_speakers: set[str] = set()
    source_attribution_count = 0
    cursor = 0

    for index, row in enumerate(raw_script):
        if not isinstance(row, dict):
            continue
        text = str(row.get("text") or "").strip()
        if not text:
            continue
        if index == 0 and "국민의 알 권리" not in text:
            text = f"국민의 알 권리를 위해 오늘 이슈를 차분히 짚어보겠습니다. {text}"
        source_ids = _ai_source_ids(row.get("sourceIds") or row.get("source_ids") or row.get("sourceId"))
        row_issue_id = str(row.get("issueId") or row.get("issue_id") or "").strip()
        if (
            row_issue_id in required_issues
            and row_issue_id not in issue_attributions
            and "에 따르면" not in text
            and source_ids
        ):
            source = source_by_id.get(source_ids[0])
            source_label = _source_label(source)
            text = f"{text.rstrip()} 이 내용은 {source_label}에 따르면 연결된 원문 기준으로 확인됩니다."
        attribution_count = text.count("에 따르면")
        source_attribution_count += attribution_count
        if attribution_count > 0:
            if row_issue_id in required_issues:
                issue_attributions.add(row_issue_id)
            for issue_id, mapped_source_ids in source_ids_by_issue.items():
                if set(source_ids).intersection(mapped_source_ids):
                    issue_attributions.add(issue_id)

        speaker_id = str(row.get("speakerId") or "").strip()
        speaker = host_by_id.get(speaker_id)
        if speaker is None:
            speaker = hosts[len(segments) % len(hosts)] if hosts else {"id": "anchor", "name": "진행자", "role": "진행"}
            speaker_id = speaker["id"]
        used_speakers.add(speaker_id)

        source_refs = _ai_source_refs(
            source_ids,
            fallback_sources=fallback_sources,
            reason=reason,
            source_by_id=source_by_id,
        )
        cleaned, expression_findings = _sanitize_script_text(_spoken_polite(text))
        if not cleaned:
            continue
        segments.append(
            {
                "expressionReview": {
                    "findings": expression_findings,
                    "status": "needs_review" if expression_findings else "passed",
                },
                "role": speaker["role"],
                "speakerId": speaker_id,
                "speakerName": speaker["name"],
                "sourceRefs": source_refs,
                "startsAt": cursor,
                "text": cleaned,
            },
        )
        cursor += max(12, len(cleaned) // 8)

    if len(hosts) >= 2 and len(used_speakers) < 2:
        return []
    if sources and source_attribution_count < min_source_attributions:
        return []
    if required_issues and issue_attributions != required_issues:
        return []
    return segments


def _expression_findings_from_script(script: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, segment in enumerate(script):
        review = segment.get("expressionReview") if isinstance(segment, dict) else None
        findings = review.get("findings") if isinstance(review, dict) else None
        if not findings:
            continue
        rows.append(
            {
                "segmentIndex": index,
                "speakerId": segment.get("speakerId"),
                "findings": findings,
            },
        )
    return rows


def _quality_gate(
    db: Session,
    *,
    issue: models.Issue | None,
    issues: list[models.Issue],
    script: list[dict[str, Any]],
    sources: list[dict[str, Any]],
) -> dict[str, Any]:
    min_sources = int(get_effective_setting(db, "podcast_min_sources_for_publish", 1) or 1)
    min_quality_score = int(get_effective_setting(db, "podcast_min_publish_quality_score", 70) or 70)
    require_official = bool(get_effective_setting(db, "podcast_sensitive_topics_require_official_source", False))
    missing: list[str] = []
    warnings: list[str] = []

    if len(sources) < min_sources:
        missing.append("sourceCount")
    if not script:
        missing.append("script")

    topics = {normalize_topic(row.topic) for row in issues}
    if issue:
        topics.add(normalize_topic(issue.topic))
    if require_official and topics.intersection(SENSITIVE_TOPICS) and not any(_source_is_official(source) for source in sources):
        missing.append("officialSource")

    expression_findings = _expression_findings_from_script(script)
    if expression_findings:
        warnings.append("riskyExpression")

    score = 100
    score -= max(0, min_sources - len(sources)) * 30
    score -= len(missing) * 20
    score -= len(warnings) * 8
    score = max(0, min(100, score))
    status = "publishable" if not missing and score >= min_quality_score else "blocked"
    return {
        "checkedAt": _now_iso(),
        "missingSignals": missing,
        "minPublishQualityScore": min_quality_score,
        "minSources": min_sources,
        "expressionFindings": expression_findings[:10],
        "qualityScore": score,
        "sensitiveTopicsRequireOfficialSource": require_official,
        "status": status,
        "warnings": warnings,
    }


def _notation_review(issue: models.Issue) -> dict[str, Any]:
    raw_terms = [
        part.strip(" '\"“”‘’()[]{}.,")
        for part in issue.title.replace("·", " ").replace("-", " ").split()
    ]
    terms = []
    for term in raw_terms:
        if len(term) < 2:
            continue
        if any(char.isdigit() for char in term):
            continue
        if term not in terms and len(terms) < 12:
            terms.append(term)
    return {
        "status": "review_candidates_ready" if terms else "no_candidates",
        "terms": terms,
    }


def _correction_policy(issue: models.Issue) -> dict[str, Any]:
    if issue.changed_claims > 0:
        return {
            "action": "prioritize_follow_up",
            "reason": "changed_claims_detected",
            "requiresUpdateEpisode": True,
        }
    return {
        "action": "monitor",
        "reason": "no_changed_claims",
        "requiresUpdateEpisode": False,
    }


def _summary_line(issue: models.Issue, cache: dict[str, Any]) -> str:
    summary = issue.summary or str(cache.get("computed_summary") or "")
    if not summary:
        return f"{issue.title}의 사실관계와 후속 확인점을 정리합니다."
    return summary.strip()


def _fact_lines(issue: models.Issue, cache: dict[str, Any]) -> list[str]:
    facts = cache.get("confirmed_facts") or issue.confirmed_facts or []
    rows: list[str] = []
    for fact in facts:
        if not isinstance(fact, dict):
            continue
        text = str(fact.get("text") or "").strip()
        verdict = str(fact.get("verdict") or "").strip()
        if text:
            rows.append(f"{text} 판정 기준은 {verdict or '근거 확인 중'}입니다.")
    return rows[:3]


def _cluster_lines(issue: models.Issue, cache: dict[str, Any]) -> list[str]:
    clusters = cache.get("claim_clusters") or issue.claim_clusters or []
    rows: list[str] = []
    for cluster in clusters:
        if not isinstance(cluster, dict):
            continue
        title = str(cluster.get("title") or "쟁점").strip()
        conflict = str(cluster.get("conflict") or "").strip()
        common = str(cluster.get("commonGround") or cluster.get("common_ground") or "").strip()
        if conflict or common:
            rows.append(f"{title}에서는 {conflict or common}")
    return rows[:3]


def _script_segments(
    issue: models.Issue,
    cache: dict[str, Any],
    *,
    episode_format: str,
    hosts: list[dict[str, str]],
    sources: list[dict[str, Any]],
    variant: str,
) -> list[dict[str, Any]]:
    anchor = hosts[0]
    analyst = hosts[1] if len(hosts) > 1 else anchor
    reporter = hosts[2] if len(hosts) > 2 else analyst
    fact_lines = _fact_lines(issue, cache)
    cluster_lines = _cluster_lines(issue, cache)
    source_text = _source_list_text(sources, limit=3)

    issue_context_refs = _source_refs(sources, reason="issue_context", limit=2)
    evidence_refs = _source_refs(sources, reason="evidence_support", limit=3, prefer_official=True)
    source_disclosure_refs = _source_refs(sources, reason="source_disclosure", limit=6)

    if episode_format == "solo":
        raw_segments = [
            (
                anchor,
                f"안녕하세요. 국민의 알 권리를 위해 오늘은 {issue.title}을 헷갈리지 않게 짚어보겠습니다. {_source_attribution(sources)} {_spoken_polite(_summary_line(issue, cache))}",
                issue_context_refs,
            ),
        ]
    else:
        raw_segments = [
            (
                anchor,
                f"국민의 알 권리를 위해 오늘 이야기할 주제는 {issue.title}입니다. {analyst['name']}님, 먼저 확인된 내용부터 잡아볼까요?",
                issue_context_refs,
            ),
            (
                analyst,
                f"네. {_source_attribution(sources)} {_spoken_polite(_summary_line(issue, cache))} 여기서 중요한 점은 확인된 사실과 아직 더 봐야 할 해석을 나눠 듣는 것입니다.",
                evidence_refs,
            ),
        ]
    fact_limit = 2 if variant == "short" else 5 if variant == "deep" else 3
    cluster_limit = 1 if variant == "short" else 5 if variant == "deep" else 3
    for line in fact_lines[:fact_limit]:
        speaker = anchor if episode_format == "solo" else analyst
        prefix = "확인된 근거를 보면" if episode_format == "solo" else "그 부분은 자료 기준으로 보면"
        raw_segments.append((speaker, f"{prefix} {_spoken_polite(line)}", evidence_refs))
    for line in cluster_lines[:cluster_limit]:
        speaker = anchor if episode_format == "solo" else reporter
        prefix = "쟁점은" if episode_format == "solo" else f"{reporter['name']}님이 보기에 쟁점은"
        raw_segments.append((speaker, f"{prefix} {_spoken_polite(line)}", evidence_refs))
    if variant == "deep":
        raw_segments.append(
            (
                anchor if episode_format == "solo" else analyst,
                "그래서 이 사안은 확인된 사실, 해석이 필요한 주장, 추가 공식자료가 필요한 부분을 분리해서 들어야 합니다.",
                evidence_refs,
            ),
        )
    raw_segments.extend(
        [
            (
                anchor if episode_format == "solo" else reporter,
                f"오늘 인용한 자료는 {source_text}입니다. 링크는 회차의 출처 영역에서 바로 확인할 수 있습니다.",
                source_disclosure_refs,
            ),
            (
                anchor,
                "정리하면, 단정은 원문 근거가 확인될 때까지 보류하고 새 공식자료가 나오면 후속 회차에서 다시 업데이트하겠습니다.",
                evidence_refs,
            ),
        ],
    )

    segments: list[dict[str, Any]] = []
    cursor = 0
    for speaker, text, source_refs in raw_segments:
        cleaned, expression_findings = _sanitize_script_text(text)
        if not cleaned:
            continue
        segments.append(
            {
                "expressionReview": {
                    "findings": expression_findings,
                    "status": "needs_review" if expression_findings else "passed",
                },
                "role": speaker["role"],
                "speakerId": speaker["id"],
                "speakerName": speaker["name"],
                "sourceRefs": source_refs,
                "startsAt": cursor,
                "text": cleaned,
            },
        )
        cursor += max(12, len(cleaned) // 8)
    return segments


def _duration_seconds(script: list[dict[str, Any]], *, variant: str = "standard") -> int:
    if not script:
        return 0
    estimated = sum(max(12, len(str(segment.get("text") or "")) // 8) for segment in script)
    minimum = 60 if variant == "short" else 180 if variant == "deep" else 90
    return max(minimum, estimated)


def _episode_type(feed: str, issue: models.Issue) -> str:
    if feed == "daily":
        return "daily"
    if feed == "urgent" or issue.changed_claims > 0 or issue.needs_review_count >= 6:
        return "urgent"
    if feed == "featured" or issue.issue_score >= 85 or issue.risk in {"고영향", "높음", "high"}:
        return "featured"
    return "issue"


def _episode_title(issue: models.Issue, episode_type: str, variant: str = "standard") -> str:
    if episode_type == "featured":
        prefix = "특집 팟캐스트"
    elif episode_type == "urgent":
        prefix = "긴급 팟캐스트"
    else:
        prefix = "오늘의 팟캐스트"
    suffix = "" if variant == "standard" else f" · {VARIANT_LABELS[variant]}"
    return f"{prefix}: {issue.title}{suffix}"


def _issue_candidates(
    db: Session,
    *,
    issue_id: str | None = None,
    topic: str | None = None,
) -> list[models.Issue]:
    query = select(models.Issue).where(
        models.Issue.is_public.is_(True),
        models.Issue.status.notin_(["숨김", "병합됨"]),
    )
    rows = db.scalars(query).all()
    if issue_id:
        rows = [issue for issue in rows if issue.id == issue_id]
    requested_topic = normalize_topic_filter(topic)
    if not requested_topic:
        return rows
    return [issue for issue in rows if normalize_topic(issue.topic) == requested_topic]


def _build_episode(
    db: Session,
    *,
    episode_format: str,
    feed: str,
    issue: models.Issue,
    rank_metadata: dict[str, Any],
    variant: str,
) -> models.PodcastEpisode:
    _, cache = build_issue_cache_payload(db, issue_id=issue.id)
    sources = _source_rows(issue, cache)
    hosts = _hosts(issue, episode_format)
    script_generator = OpenAIPodcastScriptGenerator(db)
    ai_payload: dict[str, Any] | None = None
    script: list[dict[str, Any]] = []
    script_attempt_count = 0
    validation_feedback: str | None = None
    for _ in range(2 if script_generator.enabled else 1):
        ai_payload = script_generator.generate_issue_script(
            cache=cache,
            episode_format=episode_format,
            hosts=hosts,
            issue=issue,
            sources=sources,
            validation_feedback=validation_feedback,
            variant=variant,
        )
        script_attempt_count += 1
        script = _normalize_ai_script(
            ai_payload,
            fallback_sources=sources,
            hosts=hosts,
            issue_source_ids={issue.id: {str(source.get("id") or "") for source in sources}},
            min_source_attributions=1,
            reason="ai_issue_script_source",
            required_issue_ids=[issue.id],
            sources=sources,
        )
        if script or not script_generator.enabled:
            break
        validation_feedback = "이전 응답은 대화/출처 검증을 통과하지 못했습니다. 모든 대사에 issueId를 넣고, 핵심 설명에 '출처명에 따르면' 표현을 넣으며, 두 명 이상이 자연스럽게 대화하게 다시 작성하세요."
    script_provider = "openai" if script else "fallback"
    script_fallback_reason = None if script else script_generator.last_error or "ai_script_validation_failed"
    if not script:
        script = _script_segments(issue, cache, episode_format=episode_format, hosts=hosts, sources=sources, variant=variant)
    episode_type = _episode_type(feed, issue)
    quality = _quality_gate(db, issue=issue, issues=[issue], script=script, sources=sources)
    is_publishable = quality["status"] == "publishable"
    summary = str(ai_payload.get("summary") or "").strip() if isinstance(ai_payload, dict) else ""
    return models.PodcastEpisode(
        audio_url="",
        auto_published=is_publishable,
        category=normalize_topic(issue.topic),
        duration_seconds=_duration_seconds(script, variant=variant),
        episode_format=episode_format,
        episode_type=episode_type,
        generation_json={
            "correctionPolicy": _correction_policy(issue),
            "feed": feed,
            "generatedAt": _now_iso(),
            "issueScore": issue.issue_score,
            "issueTitle": issue.title,
            "notationReview": _notation_review(issue),
            "publicationGate": quality,
            "scriptFallbackReason": script_fallback_reason,
            "scriptAttemptCount": script_attempt_count,
            "scriptModel": script_generator.model if script_provider == "openai" else None,
            "scriptProvider": script_provider,
            "scriptVersion": _ai_script_version(variant) if script_provider == "openai" else _script_version(variant),
            "sourceCount": len(sources),
            "ttsStatus": "script_ready",
            "variant": variant,
        },
        host_profiles_json=hosts,
        id=new_id("podcast"),
        issue_id=issue.id,
        published_at=models.now_utc(),
        rank_json=rank_metadata,
        script_json=script,
        source_json=sources,
        status="published" if is_publishable else "draft",
        subtitle=f"{normalize_topic(issue.topic)} · {rank_metadata.get('rankReason') or '주요 이슈 정리'}",
        summary=summary or _summary_line(issue, cache),
        thumbnail_url=issue.representative_image_url or "",
        title=_episode_title(issue, episode_type, variant),
        variant=variant,
    )


def _merge_sources(source_groups: list[list[dict[str, Any]]], *, limit: int = 10) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for sources in source_groups:
        for source in sources:
            url = str(source.get("url") or "").strip()
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            rows.append(source)
            if len(rows) >= limit:
                return rows
    return rows


def _daily_script_issue_limit(variant: str) -> int:
    if variant == "short":
        return 3
    if variant == "deep":
        return 6
    return 4


def _korean_ordinal(index: int) -> str:
    labels = ["첫 번째", "두 번째", "세 번째", "네 번째", "다섯 번째", "여섯 번째"]
    if 1 <= index <= len(labels):
        return labels[index - 1]
    return f"{index}번째"


def _daily_script_segments(
    *,
    hosts: list[dict[str, str]],
    issue_payloads: list[tuple[models.Issue, dict[str, Any], list[dict[str, Any]]]],
    sources: list[dict[str, Any]],
    variant: str,
) -> list[dict[str, Any]]:
    anchor = hosts[0]
    analyst = hosts[1] if len(hosts) > 1 else anchor
    reporter = hosts[2] if len(hosts) > 2 else analyst
    source_text = _source_list_text(sources, limit=5)
    max_issues = _daily_script_issue_limit(variant)
    selected = issue_payloads[:max_issues]
    issue_refs = _source_refs(sources, reason="daily_issue_context", limit=4)
    evidence_refs = _source_refs(sources, reason="daily_evidence_support", limit=4, prefer_official=True)
    disclosure_refs = _source_refs(sources, reason="daily_source_disclosure", limit=8)
    raw_segments: list[tuple[dict[str, str], str, list[dict[str, Any]]]] = [
        (
            anchor,
            "안녕하세요. 국민의 알 권리를 위해 오늘은 핵심 사건을 한 번에 듣는 종합 팟캐스트입니다. 여러 이슈를 빠르게 훑되, 확인된 내용과 더 봐야 할 부분을 나눠보겠습니다.",
            issue_refs,
        ),
        (
            analyst,
            f"좋습니다. 오늘은 {len(selected)}개 사건을 묶었습니다. 말은 편하게 이어가되, 근거는 출처가 확인된 자료 안에서만 짚어보겠습니다.",
            issue_refs,
        ),
    ]

    for index, (issue, cache, issue_sources) in enumerate(selected, start=1):
        issue_source_refs = _source_refs(issue_sources, reason="daily_issue_evidence", limit=3, prefer_official=True)
        if not issue_source_refs:
            issue_source_refs = evidence_refs
        ordinal = _korean_ordinal(index)
        question_speaker = anchor
        answer_speaker = analyst if index % 2 else reporter
        follow_speaker = reporter if answer_speaker["id"] != reporter["id"] else analyst
        fact_lines = _fact_lines(issue, cache)
        cluster_lines = _cluster_lines(issue, cache)
        raw_segments.append(
            (
                question_speaker,
                f"{ordinal} 이슈로 볼 사건은 {issue.title}입니다. {answer_speaker['name']}님, 이 사안은 어떤 내용인가요?",
                issue_source_refs,
            ),
        )
        raw_segments.append(
            (
                answer_speaker,
                f"{_source_attribution(issue_sources)} {_spoken_polite(_summary_line(issue, cache))}",
                issue_source_refs,
            ),
        )
        if fact_lines:
            raw_segments.append(
                (
                    follow_speaker,
                    f"청취자가 바로 기억하실 지점은 이 부분입니다. {_spoken_polite(fact_lines[0])}",
                    issue_source_refs,
                ),
            )
        elif cluster_lines:
            raw_segments.append(
                (
                    follow_speaker,
                    f"쟁점은 이 부분입니다. {_spoken_polite(cluster_lines[0])}",
                    issue_source_refs,
                ),
            )
        else:
            raw_segments.append(
                (
                    follow_speaker,
                    "그러면 지금은 단정하기보다 후속 자료가 어떤 기준으로 나오는지 보는 게 중요하겠네요.",
                    issue_source_refs,
                ),
            )
        if variant == "deep":
            extra = cluster_lines[0] if cluster_lines else ""
            if extra:
                raw_segments.append((reporter, f"조금 더 들어가면 {_spoken_polite(extra)}", issue_source_refs))

    raw_segments.extend(
        [
            (
                reporter,
                f"오늘 언급한 출처는 {source_text} 등입니다. 각 원문 링크는 회차 하단 출처 목록에 묶어두겠습니다.",
                disclosure_refs,
            ),
            (
                anchor,
                "오늘의 종합 팟캐스트는 여기까지입니다. 중요한 건 빠르게 듣되, 판단은 출처와 함께 하는 겁니다. 새 자료가 나오면 다시 업데이트하겠습니다.",
                evidence_refs,
            ),
        ],
    )

    segments: list[dict[str, Any]] = []
    cursor = 0
    for speaker, text, source_refs in raw_segments:
        cleaned, expression_findings = _sanitize_script_text(text)
        if not cleaned:
            continue
        segments.append(
            {
                "expressionReview": {
                    "findings": expression_findings,
                    "status": "needs_review" if expression_findings else "passed",
                },
                "role": speaker["role"],
                "speakerId": speaker["id"],
                "speakerName": speaker["name"],
                "sourceRefs": source_refs,
                "startsAt": cursor,
                "text": cleaned,
            },
        )
        cursor += max(12, len(cleaned) // 8)
    return segments


def _daily_episode_for_date(
    db: Session,
    *,
    daily_date: str,
    topic: str | None,
    variant: str,
) -> models.PodcastEpisode | None:
    rows = db.scalars(
        select(models.PodcastEpisode).where(
            models.PodcastEpisode.episode_type == "daily",
            models.PodcastEpisode.status != "archived",
        ),
    ).all()
    requested_topic = normalize_topic_filter(topic) or "사회"
    for episode in rows:
        generation = episode.generation_json if isinstance(episode.generation_json, dict) else {}
        if (
            generation.get("dailyDate") == daily_date
            and generation.get("variant") == variant
            and normalize_topic(episode.category) == requested_topic
        ):
            return episode
    return None


def _build_daily_episode(
    db: Session,
    *,
    issues: list[models.Issue],
    rank_metadata: dict[str, Any],
    topic: str | None,
    variant: str,
) -> models.PodcastEpisode:
    issue_payloads: list[tuple[models.Issue, dict[str, Any], list[dict[str, Any]]]] = []
    source_groups: list[list[dict[str, Any]]] = []
    for issue in issues:
        _, cache = build_issue_cache_payload(db, issue_id=issue.id)
        issue_sources = _source_rows(issue, cache)
        issue_payloads.append((issue, cache, issue_sources))
        source_groups.append(issue_sources)

    category = normalize_topic_filter(topic) or "사회"
    hosts = [
        {"id": host_id, "name": name, "role": role, "tone": tone}
        for host_id, name, role, tone in DEFAULT_HOSTS[:3]
    ]
    sources = _merge_sources(source_groups, limit=12)
    source_by_url = {
        str(source.get("url") or ""): source
        for source in sources
        if isinstance(source, dict)
    }
    normalized_issue_payloads = []
    for issue, cache, issue_sources in issue_payloads:
        normalized_sources = [
            source_by_url[str(source.get("url") or "")]
            for source in issue_sources
            if str(source.get("url") or "") in source_by_url
        ]
        normalized_issue_payloads.append((issue, cache, normalized_sources))
    selected_issue_payloads = normalized_issue_payloads[: _daily_script_issue_limit(variant)]
    script_generator = OpenAIPodcastScriptGenerator(db)
    ai_payload: dict[str, Any] | None = None
    script: list[dict[str, Any]] = []
    script_attempt_count = 0
    validation_feedback = None
    min_source_attributions = max(1, len(selected_issue_payloads))
    issue_source_ids = {
        issue.id: {
            str(source.get("id") or "")
            for source in issue_sources
            if str(source.get("id") or "").strip()
        }
        for issue, _, issue_sources in selected_issue_payloads
    }
    for _ in range(2 if script_generator.enabled else 1):
        ai_payload = script_generator.generate_daily_script(
            hosts=hosts,
            issue_payloads=selected_issue_payloads,
            sources=sources,
            validation_feedback=validation_feedback,
            variant=variant,
        )
        script_attempt_count += 1
        script = _normalize_ai_script(
            ai_payload,
            fallback_sources=sources,
            hosts=hosts,
            issue_source_ids=issue_source_ids,
            min_source_attributions=min_source_attributions,
            reason="ai_daily_script_source",
            required_issue_ids=[issue.id for issue, _, _ in selected_issue_payloads],
            sources=sources,
        )
        if script or not script_generator.enabled:
            break
        validation_feedback = (
            f"이전 응답은 출처 인용이 부족했습니다. 이번 daily 회차에는 {len(selected_issue_payloads)}개 issue가 있으므로 "
            "모든 대사에 해당 issueId를 넣고, 각 issue 설명마다 반드시 '출처명에 따르면' 문장을 하나 이상 넣으며, 모든 issue를 빠뜨리지 마세요."
        )
    script_provider = "openai" if script else "fallback"
    script_fallback_reason = None if script else script_generator.last_error or "ai_script_validation_failed"
    if not script:
        script = _daily_script_segments(
            hosts=hosts,
            issue_payloads=normalized_issue_payloads,
            sources=sources,
            variant=variant,
        )
    quality = _quality_gate(db, issue=None, issues=issues, script=script, sources=sources)
    is_publishable = quality["status"] == "publishable"
    daily_date = datetime.now(UTC).date().isoformat()
    titles = [issue.title for issue in issues[:4]]
    ai_summary = str(ai_payload.get("summary") or "").strip() if isinstance(ai_payload, dict) else ""
    summary = ai_summary or " / ".join(titles)
    suffix = "" if variant == "standard" else f" · {VARIANT_LABELS[variant]}"
    return models.PodcastEpisode(
        audio_url="",
        auto_published=is_publishable,
        category=category,
        duration_seconds=_duration_seconds(script, variant=variant),
        episode_format="panel_3",
        episode_type="daily",
        generation_json={
            "dailyDate": daily_date,
            "feed": "daily",
            "generatedAt": _now_iso(),
            "issueIds": [issue.id for issue in issues],
            "maxScriptIssues": _daily_script_issue_limit(variant),
            "podcastKind": "comprehensive",
            "publicationGate": quality,
            "scriptFallbackReason": script_fallback_reason,
            "scriptAttemptCount": script_attempt_count,
            "scriptModel": script_generator.model if script_provider == "openai" else None,
            "scriptProvider": script_provider,
            "scriptVersion": _ai_script_version(variant) if script_provider == "openai" else _script_version(variant),
            "scriptIssueCount": min(len(issues), _daily_script_issue_limit(variant)),
            "sourceCount": len(sources),
            "ttsStatus": "script_ready",
            "variant": variant,
        },
        host_profiles_json=hosts,
        id=new_id("podcast"),
        issue_id=None,
        published_at=models.now_utc(),
        rank_json=rank_metadata,
        script_json=script,
        source_json=sources,
        status="published" if is_publishable else "draft",
        subtitle=f"종합 · 오늘 핵심 사건 {len(issues)}개",
        summary=summary,
        thumbnail_url=issues[0].representative_image_url if issues else "",
        title=f"종합 팟캐스트: 오늘의 핵심 사건{suffix}",
        variant=variant,
    )


def generate_podcast_episodes(
    db: Session,
    *,
    episode_format: str | None = None,
    feed: str = "recommended",
    force: bool = False,
    issue_id: str | None = None,
    limit: int = 6,
    topic: str | None = None,
    user: models.User | None = None,
    variant: str | None = None,
) -> list[models.PodcastEpisode]:
    sort = _feed_sort(feed, user=user)
    selected_variant = _episode_variant(variant)
    interest_profile = db.get(models.UserInterestProfile, user.id) if user else None
    ranked_issues = _rank_podcast_issues(
        db,
        _issue_candidates(db, issue_id=issue_id, topic=topic),
        interest_profile=interest_profile,
        sort=sort,
        user=user,
    )

    if feed == "daily":
        selected_issues = ranked_issues[: max(1, min(limit, 8))]
        if not selected_issues:
            return []
        daily_date = datetime.now(UTC).date().isoformat()
        existing_daily = _daily_episode_for_date(
            db,
            daily_date=daily_date,
            topic=topic,
            variant=selected_variant,
        )
        rank_metadata = {
            "feed": feed,
            "rankMode": sort,
            "rankReason": "오늘 핵심 사건을 묶은 종합 팟캐스트",
            "rankScore": round(sum(float(getattr(issue, "_rank_metadata", {}).get("rankScore") or 0) for issue in selected_issues), 3),
            "rankedAt": _now_iso(),
        }
        if existing_daily and not force:
            existing_daily.rank_json = {**(existing_daily.rank_json or {}), **rank_metadata}
            existing_daily.updated_at = models.now_utc()
            db.flush()
            return [existing_daily]
        if existing_daily:
            db.delete(existing_daily)
            db.flush()
        episode = _build_daily_episode(
            db,
            issues=selected_issues,
            rank_metadata=rank_metadata,
            topic=topic,
            variant=selected_variant,
        )
        db.add(episode)
        db.flush()
        return [episode]

    episodes: list[models.PodcastEpisode] = []
    for issue in ranked_issues:
        if episode_format:
            selected_format = _episode_format(issue, episode_format)
        elif selected_variant == "short":
            selected_format = "solo"
        elif selected_variant == "deep":
            selected_format = "panel_3"
        else:
            selected_format = _episode_format(issue)
        existing = db.scalar(
            select(models.PodcastEpisode).where(
                models.PodcastEpisode.issue_id == issue.id,
                models.PodcastEpisode.episode_format == selected_format,
                models.PodcastEpisode.variant == selected_variant,
                models.PodcastEpisode.status != "archived",
            ),
        )
        rank_metadata = dict(getattr(issue, "_rank_metadata", {}) or {})
        rank_metadata["feed"] = feed
        rank_metadata["variant"] = selected_variant
        if existing and not force:
            existing.rank_json = {**(existing.rank_json or {}), **rank_metadata}
            existing.updated_at = models.now_utc()
            episodes.append(existing)
        else:
            if existing:
                db.delete(existing)
                db.flush()
            episode = _build_episode(
                db,
                episode_format=selected_format,
                feed=feed,
                issue=issue,
                rank_metadata=rank_metadata,
                variant=selected_variant,
            )
            db.add(episode)
            db.flush()
            episodes.append(episode)
        if len(episodes) >= limit:
            break
    db.flush()
    return episodes


def list_podcast_episodes(
    db: Session,
    *,
    exclude_episode_id: str | None = None,
    feed: str = "recommended",
    limit: int = 20,
    topic: str | None = None,
    user: models.User | None = None,
) -> list[models.PodcastEpisode]:
    query = select(models.PodcastEpisode).where(models.PodcastEpisode.status == "published")
    if exclude_episode_id:
        query = query.where(models.PodcastEpisode.id != exclude_episode_id)
    rows = db.scalars(query.order_by(models.PodcastEpisode.published_at.desc())).all()
    if feed == "daily":
        rows = [episode for episode in rows if episode.episode_type == "daily"]
    elif feed == "featured":
        rows = [episode for episode in rows if episode.episode_type == "featured"]
    elif feed == "urgent":
        rows = [episode for episode in rows if episode.episode_type == "urgent"]
    requested_topic = normalize_topic_filter(topic)
    if requested_topic:
        rows = [episode for episode in rows if normalize_topic(episode.category) == requested_topic]

    issue_ids = [episode.issue_id for episode in rows if episode.issue_id]
    issues = (
        db.scalars(select(models.Issue).where(models.Issue.id.in_(issue_ids))).all()
        if issue_ids
        else []
    )
    issue_by_id = {issue.id: issue for issue in issues}

    sort = _feed_sort(feed, user=user)
    interest_profile = db.get(models.UserInterestProfile, user.id) if user else None
    ranked_issues = _rank_podcast_issues(
        db,
        list(issue_by_id.values()),
        interest_profile=interest_profile,
        sort=sort,
        user=user,
    )
    rank_by_issue_id = {issue.id: index for index, issue in enumerate(ranked_issues)}
    metadata_by_issue_id = {
        issue.id: dict(getattr(issue, "_rank_metadata", {}) or {})
        for issue in ranked_issues
    }

    if feed in {"personalized", "recommended", "ranking", "featured", "category"}:
        rows = sorted(
            rows,
            key=lambda episode: (
                rank_by_issue_id.get(episode.issue_id or "", len(rows) + 1),
                -(episode.published_at.timestamp() if episode.published_at else 0),
            ),
        )
        for episode in rows:
            if episode.issue_id in metadata_by_issue_id:
                episode.rank_json = {**(episode.rank_json or {}), **metadata_by_issue_id[episode.issue_id], "feed": feed}

    return rows[:limit]


def get_episode_issue(db: Session, episode: models.PodcastEpisode) -> models.Issue | None:
    return db.get(models.Issue, episode.issue_id) if episode.issue_id else None
