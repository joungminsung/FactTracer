from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app.services.admin.settings import get_effective_setting
from app.services.bootstrap.sources import seed_default_source_domains
from app.services.discovery.incident_detector import upsert_discovery_topic


DEFAULT_DISCOVERY_TOPICS = (
    {
        "base_queries": ["정치 논란 정부 발표", "국회 법안 논란", "선거 투표 논란", "정당 후보 논란", "정부 국회 발표"],
        "name": "정치 주요 이슈",
        "priority": "high",
        "topic": "정치",
    },
    {
        "base_queries": ["사회 사건 사고 논란", "공공기관 발표 논란", "수사 조사 발표"],
        "name": "사회 주요 이슈",
        "priority": "high",
        "topic": "사회",
    },
    {
        "base_queries": ["경제 정책 물가 논란", "부동산 금융 발표", "기업 실적 고용 논란"],
        "name": "경제 주요 이슈",
        "priority": "normal",
        "topic": "경제",
    },
    {
        "base_queries": ["국제 외교 분쟁 발표", "해외 선거 분쟁", "국제 제재 협상"],
        "name": "국제 주요 이슈",
        "priority": "normal",
        "topic": "국제",
    },
    {
        "base_queries": ["재난 사고 피해 발표", "화재 지진 폭우 피해", "안전 사고 원인 조사"],
        "name": "재난 안전 이슈",
        "priority": "high",
        "topic": "재난",
    },
    {
        "base_queries": ["보건 의료 질병 발표", "의료 정책 논란", "식품 의약품 안전 발표"],
        "name": "보건 주요 이슈",
        "priority": "normal",
        "topic": "보건",
    },
    {
        "base_queries": ["AI 기술 정책 논란", "반도체 플랫폼 보안 발표", "과학기술 통신 정책"],
        "name": "IT 과학기술 주요 이슈",
        "priority": "normal",
        "topic": "IT",
    },
)


def bootstrap_default_discovery(db: Session) -> list[models.DiscoveryTopic]:
    if not get_effective_setting(db, "bootstrap_default_discovery_enabled"):
        return []
    seed_default_source_domains(db)
    existing = db.scalar(select(func.count()).select_from(models.DiscoveryTopic))
    if existing:
        return []

    rows: list[models.DiscoveryTopic] = []
    for item in DEFAULT_DISCOVERY_TOPICS:
        rows.append(
            upsert_discovery_topic(
                db,
                base_queries=item["base_queries"],
                interval_minutes=30,
                max_results_per_query=8,
                min_cluster_size=2,
                name=item["name"],
                priority=item["priority"],
                status="active",
                topic=item["topic"],
            ),
        )
    db.flush()
    return rows
