from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models


DEFAULT_SOURCE_DOMAINS: tuple[dict, ...] = (
    {
        "collection_url": "https://www.korea.kr",
        "credibility": 0.9,
        "domain": "korea.kr",
        "name": "대한민국 정책브리핑",
        "note": "정부 공식 정책자료",
        "source_type": "public",
    },
    {
        "collection_url": "https://www.law.go.kr",
        "credibility": 0.95,
        "domain": "law.go.kr",
        "name": "국가법령정보센터",
        "note": "법령 및 행정규칙",
        "source_type": "law",
    },
    {
        "collection_url": "https://www.data.go.kr",
        "credibility": 0.88,
        "domain": "data.go.kr",
        "name": "공공데이터포털",
        "note": "공공 데이터",
        "source_type": "public",
    },
    {
        "collection_url": "https://kostat.go.kr",
        "credibility": 0.95,
        "domain": "kostat.go.kr",
        "name": "통계청",
        "note": "국가 통계",
        "source_type": "statistics",
    },
    {
        "collection_url": "https://www.nec.go.kr",
        "credibility": 0.95,
        "domain": "nec.go.kr",
        "name": "중앙선거관리위원회",
        "note": "선거 공식자료",
        "source_type": "official",
    },
    {
        "collection_url": "https://www.mohw.go.kr",
        "credibility": 0.93,
        "domain": "mohw.go.kr",
        "name": "보건복지부",
        "note": "보건복지 공식자료",
        "source_type": "official",
    },
    {
        "collection_url": "https://www.kdca.go.kr",
        "credibility": 0.93,
        "domain": "kdca.go.kr",
        "name": "질병관리청",
        "note": "감염병 및 보건 통계",
        "source_type": "official",
    },
    {
        "collection_url": "https://www.moef.go.kr",
        "credibility": 0.92,
        "domain": "moef.go.kr",
        "name": "기획재정부",
        "note": "경제정책 공식자료",
        "source_type": "official",
    },
    {
        "collection_url": "https://www.bok.or.kr",
        "credibility": 0.94,
        "domain": "bok.or.kr",
        "name": "한국은행",
        "note": "경제 통계 및 금융 자료",
        "source_type": "statistics",
    },
    {
        "collection_url": "https://www.molit.go.kr",
        "credibility": 0.92,
        "domain": "molit.go.kr",
        "name": "국토교통부",
        "note": "부동산·교통 공식자료",
        "source_type": "official",
    },
    {
        "collection_url": "https://www.mofa.go.kr",
        "credibility": 0.92,
        "domain": "mofa.go.kr",
        "name": "외교부",
        "note": "외교 공식자료",
        "source_type": "official",
    },
    {
        "collection_url": "https://www.police.go.kr",
        "credibility": 0.9,
        "domain": "police.go.kr",
        "name": "경찰청",
        "note": "수사·치안 공식자료",
        "source_type": "official",
    },
    {
        "collection_url": "https://www.nfa.go.kr",
        "credibility": 0.9,
        "domain": "nfa.go.kr",
        "name": "소방청",
        "note": "재난·소방 공식자료",
        "source_type": "official",
    },
    {
        "collection_url": "https://www.fsc.go.kr",
        "credibility": 0.91,
        "domain": "fsc.go.kr",
        "name": "금융위원회",
        "note": "금융정책 공식자료",
        "source_type": "official",
    },
    {
        "collection_url": "https://www.ftc.go.kr",
        "credibility": 0.91,
        "domain": "ftc.go.kr",
        "name": "공정거래위원회",
        "note": "시장·기업 공정거래 공식자료",
        "source_type": "official",
    },
)


def _source_id(domain: str) -> str:
    return f"source_{domain.replace('.', '_').replace('-', '_')}"


def seed_default_source_domains(db: Session) -> int:
    created = 0
    for row in DEFAULT_SOURCE_DOMAINS:
        existing = db.scalar(select(models.SourceDomain).where(models.SourceDomain.domain == row["domain"]))
        if existing:
            continue
        db.add(
            models.SourceDomain(
                collection_url=row["collection_url"],
                credibility=row["credibility"],
                domain=row["domain"],
                id=_source_id(row["domain"]),
                is_active=True,
                name=row["name"],
                note=row["note"],
                source_type=row["source_type"],
                status="watch",
            ),
        )
        created += 1
    db.flush()
    return created
