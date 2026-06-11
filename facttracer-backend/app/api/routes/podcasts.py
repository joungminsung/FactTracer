from typing import Annotated
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.api.dependencies import optional_public_current_user, reviewer_user
from app.db.session import get_db
from app.schemas import (
    PodcastDetailResponse,
    PodcastFeedResponse,
    PodcastGenerateResponse,
    PodcastHomeResponse,
    PodcastSection,
)
from app.serializers import podcast_episode_card, podcast_episode_detail
from app.services.podcasts.generator import generate_podcast_episodes, get_episode_issue, list_podcast_episodes
from app.services.podcasts.tts import episode_audio_mime_type, render_episode_audio

router = APIRouter(prefix="/podcasts", tags=["podcasts"])


def _issue_map(db: Session, episodes: list[models.PodcastEpisode]) -> dict[str, models.Issue]:
    issue_ids = {episode.issue_id for episode in episodes if episode.issue_id}
    if not issue_ids:
        return {}
    rows = db.scalars(select(models.Issue).where(models.Issue.id.in_(issue_ids))).all()
    return {issue.id: issue for issue in rows}


def _cards(db: Session, episodes: list[models.PodcastEpisode]) -> list:
    issues = _issue_map(db, episodes)
    return [podcast_episode_card(episode, issues.get(episode.issue_id or "")) for episode in episodes]


def _section(
    db: Session,
    *,
    description: str,
    episodes: list[models.PodcastEpisode],
    section_id: str,
    title: str,
) -> PodcastSection:
    return PodcastSection(
        description=description,
        episodes=_cards(db, episodes),
        id=section_id,
        title=title,
    )


def _without_episode_type(
    episodes: list[models.PodcastEpisode],
    episode_type: str,
) -> list[models.PodcastEpisode]:
    return [episode for episode in episodes if episode.episode_type != episode_type]


def _take_unique(
    episodes: list[models.PodcastEpisode],
    seen_episode_ids: set[str],
    *,
    mark_seen: bool = True,
    skip_seen: bool = True,
) -> list[models.PodcastEpisode]:
    unique: list[models.PodcastEpisode] = []
    local_seen: set[str] = set()
    for episode in episodes:
        if episode.id in local_seen or (skip_seen and episode.id in seen_episode_ids):
            continue
        local_seen.add(episode.id)
        if mark_seen:
            seen_episode_ids.add(episode.id)
        unique.append(episode)
    return unique


@router.get("/home", response_model=PodcastHomeResponse)
def podcast_home(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[models.User | None, Depends(optional_public_current_user)] = None,
) -> PodcastHomeResponse:
    personalized_title = (
        f"{user.name}님만을 위한 오늘의 팟캐스트예요"
        if user
        else "오늘의 추천 팟캐스트"
    )
    personalized = list_podcast_episodes(db, feed="personalized", limit=8, user=user)
    personalized = _without_episode_type(personalized, "daily")
    daily = list_podcast_episodes(db, feed="daily", limit=8, user=user)
    featured = list_podcast_episodes(db, feed="featured", limit=8, user=user)
    urgent = list_podcast_episodes(db, feed="urgent", limit=8, user=user)
    latest = list_podcast_episodes(db, feed="latest", limit=8, user=user)
    ranking = list_podcast_episodes(db, feed="ranking", limit=8, user=user)
    politics = list_podcast_episodes(db, feed="category", limit=8, topic="정치", user=user)
    economy = list_podcast_episodes(db, feed="category", limit=8, topic="경제", user=user)
    society = list_podcast_episodes(db, feed="category", limit=8, topic="사회", user=user)
    international = list_podcast_episodes(db, feed="category", limit=8, topic="국제", user=user)
    disaster = list_podcast_episodes(db, feed="category", limit=8, topic="재난", user=user)
    technology = list_podcast_episodes(db, feed="category", limit=8, topic="IT", user=user)

    seen_section_episode_ids: set[str] = set()
    sections = [
        _section(
            db,
            description="관심사와 이슈 신호를 함께 반영합니다.",
            episodes=_take_unique(personalized, seen_section_episode_ids, mark_seen=False),
            section_id="personalized",
            title=personalized_title,
        ),
        _section(
            db,
            description="오늘 핵심 사건 여러 개를 한 번에 듣는 종합 회차입니다.",
            episodes=_take_unique(daily, seen_section_episode_ids),
            section_id="daily",
            title="종합 팟캐스트",
        ),
        _section(
            db,
            description="큰 사건, 선거, 재난처럼 사회적 영향이 큰 이슈입니다.",
            episodes=_take_unique(featured, seen_section_episode_ids),
            section_id="featured",
            title="특집 팟캐스트",
        ),
        _section(
            db,
            description="후속 검증과 정정 가능성을 빠르게 확인해야 하는 회차입니다.",
            episodes=_take_unique(urgent, seen_section_episode_ids),
            section_id="urgent",
            title="긴급 확인",
        ),
        _section(
            db,
            description="방금 공개되었거나 업데이트된 회차입니다.",
            episodes=_take_unique(latest, seen_section_episode_ids, mark_seen=False),
            section_id="latest",
            title="최신 회차",
        ),
        _section(
            db,
            description="영향도와 확산 신호가 큰 회차입니다.",
            episodes=_take_unique(ranking, seen_section_episode_ids, mark_seen=False),
            section_id="ranking",
            title="많이 확인하는 이슈",
        ),
        _section(
            db,
            description="선거, 국회, 정책 발언의 사실관계를 정리합니다.",
            episodes=_take_unique(politics, seen_section_episode_ids),
            section_id="politics",
            title="정치",
        ),
        _section(
            db,
            description="물가, 금리, 지원금, 시장 지표를 생활 기준으로 풉니다.",
            episodes=_take_unique(economy, seen_section_episode_ids),
            section_id="economy",
            title="경제",
        ),
        _section(
            db,
            description="사회적 파장과 생활 영향을 함께 확인합니다.",
            episodes=_take_unique(society, seen_section_episode_ids),
            section_id="society",
            title="사회",
        ),
        _section(
            db,
            description="해외 주요 이슈를 국내 영향과 함께 정리합니다.",
            episodes=_take_unique(international, seen_section_episode_ids),
            section_id="international",
            title="국제",
        ),
        _section(
            db,
            description="안전, 피해, 공식 안내를 우선 확인합니다.",
            episodes=_take_unique(disaster, seen_section_episode_ids),
            section_id="disaster",
            title="재난",
        ),
        _section(
            db,
            description="AI, 플랫폼, 반도체, 보안 이슈를 근거 중심으로 정리합니다.",
            episodes=_take_unique(technology, seen_section_episode_ids),
            section_id="technology",
            title="IT/과학",
        ),
    ]
    now_playing = (
        personalized
        or daily
        or urgent
        or latest
        or featured
        or ranking
        or politics
        or economy
        or technology
        or [None]
    )[0]
    return PodcastHomeResponse(
        nowPlaying=podcast_episode_card(now_playing, get_episode_issue(db, now_playing)) if now_playing else None,
        sections=sections,
    )


@router.get("", response_model=PodcastFeedResponse)
def podcast_feed(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[models.User | None, Depends(optional_public_current_user)] = None,
    feed: str = "recommended",
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    topic: str | None = None,
) -> PodcastFeedResponse:
    episodes = list_podcast_episodes(db, feed=feed, limit=limit, topic=topic, user=user)
    return PodcastFeedResponse(episodes=_cards(db, episodes))


@router.post("/generate", response_model=PodcastGenerateResponse)
def generate_podcast_feed(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[models.User, Depends(reviewer_user)],
    episode_format: Annotated[str | None, Query(alias="format")] = None,
    feed: str = "recommended",
    force: bool = False,
    issue_id: Annotated[str | None, Query(alias="issueId")] = None,
    limit: Annotated[int, Query(ge=1, le=30)] = 6,
    render_audio: Annotated[bool, Query(alias="renderAudio")] = True,
    topic: str | None = None,
    variant: str | None = None,
) -> PodcastGenerateResponse:
    episodes = generate_podcast_episodes(
        db,
        episode_format=episode_format,
        feed=feed,
        force=force,
        issue_id=issue_id,
        limit=limit,
        topic=topic,
        variant=variant,
    )
    if render_audio:
        episodes = [render_episode_audio(db, episode=episode, force=force) for episode in episodes]
    db.commit()
    return PodcastGenerateResponse(
        episodes=_cards(db, episodes),
        generatedCount=len(episodes),
    )


@router.post("/{episode_id}/render-audio", response_model=PodcastDetailResponse)
def render_podcast_audio(
    episode_id: str,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[models.User, Depends(reviewer_user)],
    force: bool = False,
) -> PodcastDetailResponse:
    episode = db.get(models.PodcastEpisode, episode_id)
    if not episode:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "해당 팟캐스트를 찾을 수 없습니다.", "code": "NOT_FOUND"},
        )
    episode = render_episode_audio(db, episode=episode, force=force)
    db.commit()
    return PodcastDetailResponse(
        episode=podcast_episode_detail(episode, get_episode_issue(db, episode)),
        nextQueue=_cards(
            db,
            list_podcast_episodes(db, exclude_episode_id=episode.id, feed="recommended", limit=12),
        ),
    )


@router.get("/{episode_id}/audio")
def podcast_audio(
    episode_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> FileResponse:
    episode = db.get(models.PodcastEpisode, episode_id)
    if not episode or not episode.audio_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "팟캐스트 오디오 파일을 찾을 수 없습니다.", "code": "NOT_FOUND"},
        )
    audio_path = Path(episode.audio_url)
    if not audio_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "팟캐스트 오디오 파일을 찾을 수 없습니다.", "code": "NOT_FOUND"},
        )
    return FileResponse(
        audio_path,
        filename=f"{episode.id}.{str((episode.generation_json or {}).get('ttsResponseFormat') or 'wav')}",
        media_type=episode_audio_mime_type(episode),
    )


@router.get("/{episode_id}", response_model=PodcastDetailResponse)
def podcast_detail(
    episode_id: str,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[models.User | None, Depends(optional_public_current_user)] = None,
) -> PodcastDetailResponse:
    episode = db.get(models.PodcastEpisode, episode_id)
    if not episode or episode.status != "published":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "해당 팟캐스트를 찾을 수 없습니다.", "code": "NOT_FOUND"},
        )
    issue = get_episode_issue(db, episode)
    next_queue = list_podcast_episodes(
        db,
        exclude_episode_id=episode.id,
        feed="recommended",
        limit=12,
        topic=episode.category,
        user=user,
    )
    if not next_queue:
        next_queue = list_podcast_episodes(
            db,
            exclude_episode_id=episode.id,
            feed="recommended",
            limit=12,
            user=user,
        )
    return PodcastDetailResponse(
        episode=podcast_episode_detail(episode, issue),
        nextQueue=_cards(db, next_queue),
    )
