# FactTracer Podcast System Design

작성일: 2026-06-10  
문서 범위: 팟캐스트 제품, 자동 생성 파이프라인, 백엔드, OpenAI TTS, 프론트, 운영 설계  
관련 코드:

- Backend: `facttracer-backend`
- Frontend: `facttracer-next`
- UI demo: `qa/podcast-demo`

## 1. 한 줄 정의

FactTracer 팟캐스트는 자동 수집·검증된 이슈를 **대사, 출처, 다음 재생 목록, 실제 오디오**가 있는 독립 오디오 콘텐츠로 변환해 제공하는 서비스다.

핵심 목적은 단순한 뉴스 요약이 아니라 **국민의 알 권리**다. 사용자는 음악 서비스처럼 다양한 회차를 고르고 이어 들을 수 있지만, 모든 회차는 FactTracer의 검증 데이터와 원문 근거에 연결되어야 한다.

## 2. 제품 원칙

### 2.1 목적

팟캐스트는 기사 상세 안에 들어가는 부가 기능이 아니다. 별도 탐색면, 별도 플레이어, 별도 큐를 가진 제품 표면이다.

제공해야 하는 가치:

- 복잡한 이슈를 듣기 좋은 흐름으로 전달한다.
- 사용자가 화면을 계속 보지 않아도 주요 사실관계를 파악하게 한다.
- 출처와 대사를 함께 제공해 “무엇을 근거로 말했는지” 확인 가능하게 한다.
- 개인화 추천으로 사용자가 관심 있는 이슈를 먼저 듣게 한다.
- 특집, 데일리, 카테고리, 랭킹 등 다양한 콘텐츠 레일을 제공한다.

### 2.2 금지할 방향

- 뉴스 기사 내부의 “오디오 읽기” 버튼 수준으로 축소하지 않는다.
- 출처 없는 AI 요약 오디오를 만들지 않는다.
- 진행자가 사실과 해석을 섞어 단정하지 않는다.
- 유튜브 뮤직 같은 다크/음악 앱 디자인을 그대로 복제하지 않는다.
- 패널이나 캐릭터를 고정 IP처럼 운영하지 않는다. 주제와 포맷에 따라 달라질 수 있어야 한다.

### 2.3 콘텐츠 철학

```text
팩트는 검증하고,
의견은 분리하고,
쟁점은 구조화하고,
오디오는 출처와 함께 제공한다.
```

## 3. 사용자 경험 개요

### 3.1 주요 사용자 시나리오

1. 사용자가 `/podcasts` 페이지에 들어온다.
2. 상단에는 개인화 추천 회차가 먼저 보인다.
3. 아래에는 특집 팟캐스트, 최신 회차, 랭킹, 정치/경제/국제/재난 등 카테고리 레일이 보인다.
4. 사용자가 회차를 선택하면 하단 미니 플레이어가 열린다.
5. 사용자가 미니 플레이어를 확장하면 전체 화면에 가까운 플레이어 시트가 올라온다.
6. 플레이어 시트에서 오디오, 대사, 출처, 다음 재생 목록을 본다.
7. 다음 회차를 누르면 같은 플레이어 안에서 이어 재생된다.

### 3.2 화면 구조

```text
/podcasts
├─ 팟캐스트 홈
│  ├─ 개인화 추천
│  ├─ 특집 팟캐스트
│  ├─ 최신 회차
│  ├─ 랭킹
│  └─ 카테고리별 회차
├─ 하단 미니 플레이어
└─ 확장 플레이어 시트
   ├─ 오디오 컨트롤
   ├─ 대사
   ├─ 다음 재생
   └─ 출처
```

## 4. 콘텐츠 유형

### 4.1 특집 팟캐스트

큰 사건, 선거, 재난, 정책 변화처럼 사회적 영향도가 높은 이슈를 다룬다.

선정 기준:

- `issue_score`가 높다.
- `risk`가 고영향이다.
- 정치, 재난, 보건, 경제, 국제처럼 영향도가 큰 분야다.
- 기사 수, 쟁점 수, 검토 필요도, 변경 이력이 크다.

예시:

- 선거 관리 논란 특집
- 재난 대응 공식자료 업데이트
- 금리/물가 정책 발표 검증

### 4.2 사용자 맞춤 팟캐스트

사용자 관심사와 기존 이슈 랭킹 신호를 함께 반영한다.

예시 제목:

```text
민서님만을 위한 오늘의 팟캐스트예요
```

선정 기준:

- `UserInterestProfile.topic_weights_json`
- 사용자 preferences
- 저장 이슈, 관심 분야, 출처 선호도
- 기존 이슈 랭킹 신호와 팟캐스트 개인화 가중치

### 4.3 카테고리별 팟캐스트

정치, 경제, 국제, 재난, 보건, 사회 등 분야별로 제공한다.

초기 카테고리:

- 정치
- 사회
- 경제
- 국제
- 재난
- 보건

추후 확장:

- 데일리 브리핑
- 선거
- 지역
- 정책
- 과학/기술
- 라이프

### 4.4 데일리 팟캐스트

하루의 주요 이슈를 짧게 묶는다. 초기 구현에서는 `latest` feed로 대체하고, 추후 복수 이슈를 하나의 episode로 합치는 별도 타입을 추가한다.

## 5. 진행 포맷

### 5.1 포맷 종류

| 포맷 | 설명 | 사용 상황 |
| --- | --- | --- |
| `solo` | 1인 진행 | 짧은 일상 뉴스, 단순 확인 이슈 |
| `panel_2` | 2인 대화 | 정치, 경제, 국제, 재난처럼 설명이 필요한 이슈 |
| `panel_3` | 3인 패널 | 충돌 주장, 검토 필요도, 변경 이력이 높은 이슈 |

### 5.2 포맷 결정 로직

기본 로직:

```text
changed_claims > 0 또는 needs_review_count >= 6
→ panel_3

topic ∈ 정치, 경제, 국제, 재난
→ panel_2

그 외
→ solo
```

관리자 또는 작업 payload에서 `solo`, `panel_2`, `panel_3`를 강제할 수 있다.

### 5.3 캐릭터/진행자 원칙

진행자는 고정 패널이 아니다. 주제와 포맷에 따라 달라지는 캐릭터형 진행자다.

원칙:

- 같은 서비스 톤은 유지한다.
- 주제별 역할은 바뀔 수 있다.
- 정치/경제/재난/국제 등은 진행자 톤을 다르게 설정한다.
- 진행자는 의견을 생산하는 인물이 아니라 정보 전달 역할이다.

현재 백엔드 기본 preset:

| 분야 | 역할 |
| --- | --- |
| 정치 | 진행, 팩트체크, 맥락 정리 |
| 경제 | 진행, 경제 해설, 현장 맥락 |
| 국제 | 진행, 외신 검증, 지역 맥락 |
| 재난 | 진행, 자료 검증, 현장 브리핑 |
| 기본 | 진행, 검증, 맥락 |

## 6. 전체 시스템 구조

```text
News/Search/RSS/Official/Social/YouTube Collectors
        ↓
Article
        ↓
Claim Extraction / Evidence Retrieval / Verification
        ↓
Issue Cache
        ↓
Existing Issue Ranking & Personalization
        ↓
Podcast Episode Generator
        ↓
Script + Hosts + Sources + Queue Metadata
        ↓
OpenAI TTS Renderer
        ↓
Audio File Storage
        ↓
Podcast API
        ↓
Frontend Podcast Home / Player
```

핵심 결정:

- 팟캐스트 추천 알고리즘은 기존 이슈 랭킹 신호를 재사용하되, 팟캐스트 전용 운영 가중치를 적용한다.
- 팟캐스트 생성은 `Issue`와 issue cache를 입력으로 삼는다.
- 오디오는 OpenAI TTS로 생성한다.
- 프론트는 오디오와 대사/출처를 함께 보여준다.

## 7. 백엔드 설계

### 7.1 주요 모듈

```text
facttracer-backend/app/models.py
└─ PodcastEpisode

facttracer-backend/app/services/podcasts/generator.py
└─ episode selection
└─ script generation
└─ feed listing

facttracer-backend/app/services/podcasts/tts.py
└─ OpenAI TTS rendering
└─ segment audio merge
└─ audio storage metadata

facttracer-backend/app/api/routes/podcasts.py
└─ public podcast APIs
└─ admin generation/render APIs

facttracer-backend/app/workers/podcast_jobs.py
└─ background jobs

facttracer-backend/app/services/jobs.py
└─ job registration
└─ scheduler hook
```

### 7.2 데이터 모델

`PodcastEpisode`

| 필드 | 설명 |
| --- | --- |
| `id` | episode id |
| `issue_id` | 연결된 이슈 |
| `title` | 회차 제목 |
| `subtitle` | 메타/추천 사유 |
| `summary` | 회차 요약 |
| `category` | 정치/경제/사회 등 |
| `episode_type` | issue, featured, daily |
| `episode_format` | solo, panel_2, panel_3 |
| `status` | published, archived 등 |
| `audio_url` | 저장된 오디오 파일 경로 |
| `thumbnail_url` | 대표 이미지 |
| `duration_seconds` | 재생 시간 |
| `host_profiles_json` | 진행자 정보 |
| `script_json` | 대사 세그먼트. 각 세그먼트는 `sourceRefs`, `expressionReview`를 포함 |
| `source_json` | 출처 목록 |
| `rank_json` | 추천 점수/사유 |
| `generation_json` | 생성/TTS 상태 |
| `auto_published` | 자동 발행 여부 |
| `published_at` | 공개 시각 |

데일리 회차의 `generation_json`은 `scriptIssueCount`, `maxScriptIssues`를 포함한다. 표준 회차 기본값은 실제 대본에서 최대 4개 이슈만 다룬다.

중복 방지:

```text
Unique(issue_id, episode_format, variant)
```

같은 이슈와 같은 포맷, 같은 길이 유형은 중복 발행하지 않는다.

### 7.3 Episode 생성 로직

입력:

- feed
- topic
- user
- limit
- force
- episode_format

처리:

1. public issue 후보 조회
2. topic filter 적용
3. 기존 이슈 랭킹 신호와 팟캐스트 전용 가중치로 후보 정렬
4. 각 issue별 포맷 결정
5. 기존 episode 중복 확인
6. issue cache 생성/조회
7. host profile 생성
8. script segment 생성. 세그먼트별 출처 근거와 위험 표현 검수 결과를 함께 기록
9. source list 생성
10. `PodcastEpisode` 저장

### 7.4 기존 랭킹 신호 재사용

feed별 sort mode:

| Podcast feed | Issue ranking sort |
| --- | --- |
| personalized | personalized |
| featured | highImpact |
| latest | latest |
| ranking | highImpact |
| category | recommended |
| recommended | recommended |

`recommended`와 `personalized`는 팟캐스트 전용 운영 가중치를 적용한다.

기본 비로그인 추천 가중치:

| 신호 | 기본 비중 |
| --- | --- |
| 사회적 영향도 | 0.35 |
| 검증 필요도 | 0.25 |
| 최신성 | 0.20 |
| 논란도 | 0.10 |
| 모멘텀 | 0.10 |

개인화는 위 공익성 기반 점수에 `UserInterestProfile`과 `User.preferences`의 관심사 점수를 0.35 비중으로 섞는다. 운영자는 관리자 설정 또는 환경변수로 각 비중을 조정할 수 있다.

`rank_json`에는 `rankScore`, `rankReason`, `rankMode`와 함께 계산에 사용된 `signals`, `weights`, 개인화일 경우 `interestWeight`를 저장한다.

### 7.5 대본 생성

대본은 현재 deterministic template 기반이다.

입력 데이터:

- `Issue.title`
- `Issue.summary`
- `confirmed_facts`
- `claim_clusters`
- `source_documents`
- `evidences`
- `articles`
- ranking metadata

대본 구성:

```text
도입
→ 이슈 요약
→ 확인된 사실
→ 쟁점/충돌 지점
→ 출처 안내
→ 후속 업데이트 예고
```

대사 세그먼트 예시:

```json
{
  "speakerId": "anchor",
  "speakerName": "지민",
  "role": "진행",
  "startsAt": 0,
  "text": "오늘의 팟캐스트는 선거 관리 쟁점입니다..."
}
```

주의:

- 사실과 추정은 분리한다.
- 검증 중인 내용은 단정하지 않는다.
- 출처를 포함한 공개 자료 기반임을 밝힌다.
- 낙인 표현과 선정적 표현은 피한다.

## 8. OpenAI TTS 설계

### 8.1 사용 모델

기본값:

```text
OPENAI_TTS_MODEL=gpt-4o-mini-tts
OPENAI_TTS_RESPONSE_FORMAT=wav
OPENAI_TTS_SPEED=1.0
OPENAI_TTS_TIMEOUT_SECONDS=120
```

API key:

```text
OPENAI_API_KEY
```

TTS는 `FACTTRACER_AI_PROCESSING_ENABLED=true`와 `FACTTRACER_PODCAST_TTS_ENABLED=true`일 때 동작한다.

### 8.2 렌더링 방식

1. episode의 `script_json`을 읽는다.
2. 세그먼트별로 OpenAI TTS를 호출한다.
3. speaker별로 voice를 매핑한다.
4. WAV 세그먼트를 하나의 WAV 파일로 합친다.
5. `storage/podcasts/{episodeId}.wav`에 저장한다.
6. episode `audio_url`과 `generation_json`을 업데이트한다.

각 세그먼트는 최대 2회 시도한다. 실패와 재시도 결과는 `generation_json.ttsAttempts`에 세그먼트 인덱스, voice, attempt, status, 오류 메시지 형태로 남긴다.

### 8.3 Voice 매핑

현재 기본 매핑:

| speakerId | voice |
| --- | --- |
| anchor | marin |
| analyst | cedar |
| reporter | coral |

구형 `tts-*` 모델을 쓰는 경우 fallback:

| preferred | fallback |
| --- | --- |
| marin | alloy |
| cedar | verse |
| coral | nova |

### 8.4 TTS 상태

`generation_json.ttsStatus`

| 상태 | 의미 |
| --- | --- |
| `script_ready` | 대본만 생성됨 |
| `completed` | 오디오 생성 완료 |
| `skipped_unconfigured` | API key 또는 TTS 설정 없음 |
| `failed` | 렌더링 실패 |

추가 metadata:

- `ttsProvider`
- `ttsModel`
- `ttsResponseFormat`
- `ttsAttemptCount`
- `ttsAttempts`
- `ttsSegmentCount`
- `voiceMap`
- `audioBytes`
- `audioMimeType`
- `audioStoragePath`
- `renderedAt`

### 8.5 오디오 서빙

공개 API:

```text
GET /v1/podcasts/{episodeId}/audio
```

응답:

- `audio/wav` 또는 `audio/mpeg`
- 내부 파일 경로를 노출하지 않는다.
- 프론트는 episode detail의 `audioUrl`을 API base URL과 결합해 재생한다.

## 9. API 설계

### 9.1 Public APIs

```text
GET /v1/podcasts/home
```

팟캐스트 홈 섹션을 반환한다.

```json
{
  "sections": [
    {
      "id": "personalized",
      "title": "민서님만을 위한 오늘의 팟캐스트예요",
      "description": "관심사와 이슈 신호를 함께 반영합니다.",
      "episodes": []
    }
  ],
  "nowPlaying": null
}
```

```text
GET /v1/podcasts?feed=latest&topic=정치&limit=20
```

feed별 목록을 반환한다.

```text
GET /v1/podcasts/{episodeId}
```

플레이어 상세를 반환한다.

```json
{
  "episode": {
    "id": "podcast_abc",
    "title": "특집 팟캐스트: 선거 관리 쟁점",
    "script": [],
    "sources": [],
    "audioUrl": "/v1/podcasts/podcast_abc/audio",
    "ttsStatus": "completed"
  },
  "nextQueue": []
}
```

```text
GET /v1/podcasts/{episodeId}/audio
```

오디오 파일을 반환한다.

### 9.2 Admin/Reviewer APIs

```text
POST /v1/podcasts/generate
```

쿼리:

- `feed`
- `topic`
- `limit`
- `format`
- `force`
- `renderAudio`

역할:

- 기존 이슈에서 팟캐스트 회차를 생성한다.
- `renderAudio=true`이면 생성 직후 TTS를 실행한다.

```text
POST /v1/podcasts/{episodeId}/render-audio
```

기존 회차를 OpenAI TTS로 다시 렌더링한다.

## 10. Job / Scheduler 설계

### 10.1 Job types

```text
generate_podcasts
render_podcast_audio
```

`generate_podcasts` payload:

```json
{
  "feed": "recommended",
  "limit": 6,
  "topic": "정치",
  "episode_format": "panel_2",
  "force": false,
  "render_audio": true,
  "user_id": null
}
```

`render_podcast_audio` payload:

```json
{
  "episode_id": "podcast_abc",
  "force": true
}
```

### 10.2 Scheduler

스케줄러는 주기적으로 `schedule_due_podcast_jobs`를 실행한다.

조건:

- `podcast_generation_enabled=true`
- 공개 이슈가 1개 이상 존재
- 기존 queued/running `generate_podcasts` job 없음
- 마지막 completed job 이후 interval 경과

설정:

```text
FACTTRACER_PODCAST_GENERATION_ENABLED=true
FACTTRACER_PODCAST_GENERATION_INTERVAL_MINUTES=60
FACTTRACER_PODCAST_GENERATION_LIMIT=6
FACTTRACER_PODCAST_TTS_RENDER_ON_GENERATE=true
```

스케줄러 결과:

```json
{
  "scheduledPodcasts": 1
}
```

운영 지표:

```text
facttracer_podcast_draft_episodes
facttracer_podcast_jobs_failed
facttracer_podcast_tts_pending
```

팟캐스트 알림은 별도 푸시/슬랙 알림보다 `/metrics` 기반 모니터링을 우선 붙인다. 스테이징에서는 위 지표가 실제 실패 작업과 보류 회차를 반영하는지 확인한다.

## 11. 프론트엔드 설계

프론트 전용 상세 문서는 다음 파일을 기준으로 한다.

```text
facttracer-next/docs/PODCAST_FRONTEND_DESIGN.md
```

이 문서에서는 전체 구조만 요약한다.

### 11.1 신규 라우트

```text
/podcasts
```

역할:

- 팟캐스트 탐색
- 섹션별 회차 노출
- 하단 미니 플레이어
- 확장 플레이어 시트

### 11.2 API client

추가 예정:

```text
src/lib/api/podcasts.ts
```

함수:

```ts
getPodcastHome({ token })
getPodcastFeed({ feed, topic, limit, token })
getPodcastDetail(episodeId, token?)
buildPodcastAudioUrl(audioUrl)
```

### 11.3 컴포넌트

```text
src/app/podcasts/page.tsx
src/components/podcast/podcast-home-client.tsx
src/components/podcast/podcast-section.tsx
src/components/podcast/podcast-episode-card.tsx
src/components/podcast/podcast-player-provider.tsx
src/components/podcast/podcast-mini-player.tsx
src/components/podcast/podcast-player-sheet.tsx
src/components/podcast/podcast-transcript.tsx
src/components/podcast/podcast-queue.tsx
src/components/podcast/podcast-sources.tsx
```

### 11.4 미니 플레이어

하단 고정.

구성:

- play/pause
- episode title
- progress
- next
- speed
- expand

### 11.5 확장 플레이어

전체 화면에 가까운 sheet.

구성:

- 오디오 컨트롤
- 대사
- 출처
- 다음 재생
- 관련 이슈 링크

### 11.6 디자인 방향

YouTube Music의 “아래 바에서 올라오는 구조”만 참고한다. 디자인 정서는 FactTracer v2를 따른다.

원칙:

- light UI
- white background
- restrained borders
- no dark music clone
- transcript/source visibility
- card nesting 금지

## 12. 운영 콘솔 설계

초기에는 API만 제공한다. 추후 admin UI에 다음 기능을 추가한다.

### 12.1 운영 기능

- 특정 issue에서 podcast 생성
- episode format 선택
- force regenerate
- render audio
- TTS 실패 재시도
- episode archive
- script preview
- source check

### 12.2 운영 화면 후보

```text
/admin/podcasts
/admin/issues/{issueId} 내 "팟캐스트 생성" action
```

초기 우선순위:

1. `/admin/issues/{issueId}`에서 단일 이슈 팟캐스트 생성
2. `/admin/podcasts`에서 생성된 episode 목록/상태 확인
3. TTS 재렌더링 버튼

## 13. 안전성 / 신뢰 설계

### 13.1 콘텐츠 안전

팟캐스트는 검증 서비스의 공개 콘텐츠이므로 다음을 지킨다.

- 사실과 해석을 분리한다.
- 근거 없는 고의성, 배후, 범죄성 단정을 피한다.
- 검증 중인 내용은 “확인 중”으로 말한다.
- 출처가 없는 주장은 확정 표현으로 읽지 않는다.
- 특정 집단 낙인 표현을 사용하지 않는다.
- 선거, 정치, 재난, 보건, 범죄 등 민감 주제는 기본적으로 공식 출처가 있어야 자동 발행된다.
- 자동 발행 최소 품질 점수 기본값은 70점이며, 운영 설정 `podcast_min_publish_quality_score`로 조정한다.

### 13.2 출처 투명성

모든 episode는 `source_json`을 가져야 한다.

프론트는 다음을 표시한다.

- 출처 제목
- publisher
- sourceType
- 원문 링크
- credibility 또는 교차 확인 신호

### 13.3 대사 투명성

사용자는 오디오와 함께 전체 대사를 볼 수 있어야 한다.

필수:

- speaker
- role
- text
- startsAt

## 14. 개인화 설계

### 14.1 현재 개인화 입력

- `User.preferences`
- `UserInterestProfile.topic_weights_json`
- `major_topic_weights_json`
- `event_group_weights_json`
- `publisher_weights_json`

### 14.2 현재 점수화

기존 이슈 랭킹 신호를 팟캐스트 전용 가중치로 점수화한다.

요소:

- impact
- controversy
- freshness
- verification
- momentum
- personal preference

비로그인 기본 추천은 영향도, 검증 필요도, 최신성을 우선한다. 로그인 개인화 추천은 이 공익성 점수를 유지하면서 관심 토픽, 주요 주제, 이벤트 그룹, 매체 선호를 추가 반영한다.

### 14.3 추후 개선

추가 이벤트:

- episode impression
- episode play
- completion
- skip
- replay
- source click
- issue follow

추후 `ProductMetricEvent` 또는 별도 `PodcastPlayEvent`로 저장 가능하다.

## 15. 설정값

### 15.1 Backend env

```text
OPENAI_API_KEY=
OPENAI_TTS_MODEL=gpt-4o-mini-tts
OPENAI_TTS_RESPONSE_FORMAT=wav
OPENAI_TTS_SPEED=1.0
OPENAI_TTS_TIMEOUT_SECONDS=120

FACTTRACER_AI_PROCESSING_ENABLED=true
FACTTRACER_PODCAST_GENERATION_ENABLED=true
FACTTRACER_PODCAST_GENERATION_INTERVAL_MINUTES=60
FACTTRACER_PODCAST_GENERATION_LIMIT=6
FACTTRACER_PODCAST_TTS_ENABLED=true
FACTTRACER_PODCAST_TTS_RENDER_ON_GENERATE=true
FACTTRACER_PODCAST_MIN_SOURCES_FOR_PUBLISH=1
FACTTRACER_PODCAST_MIN_PUBLISH_QUALITY_SCORE=70
FACTTRACER_PODCAST_SENSITIVE_TOPICS_REQUIRE_OFFICIAL_SOURCE=true
FACTTRACER_PODCAST_RECOMMENDATION_IMPACT_WEIGHT=0.35
FACTTRACER_PODCAST_RECOMMENDATION_VERIFICATION_WEIGHT=0.25
FACTTRACER_PODCAST_RECOMMENDATION_FRESHNESS_WEIGHT=0.20
FACTTRACER_PODCAST_RECOMMENDATION_CONTROVERSY_WEIGHT=0.10
FACTTRACER_PODCAST_RECOMMENDATION_MOMENTUM_WEIGHT=0.10
FACTTRACER_PODCAST_PERSONALIZATION_INTEREST_WEIGHT=0.35
```

### 15.2 Frontend env

```text
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
FACTTRACER_API_BASE_URL=http://localhost:8000
```

## 16. 현재 구현 상태

### 16.1 Backend

상태: 구현 완료.

완료 항목:

- `PodcastEpisode` model
- `0003_podcast_episodes` migration
- podcast generator
- feed sections
- personalized ranking integration
- duplicate prevention
- detail API
- next queue
- OpenAI TTS renderer
- audio storage
- audio serving API
- background job
- scheduler hook
- admin/reviewer generate/render API
- tests
- API spec audit

검증:

```text
71 passed
API spec audit passed: 72 declared routes matched
compileall passed
alembic upgrade head passed
```

### 16.2 Frontend

상태: 설계 완료, 구현 예정.

완료 항목:

- `facttracer-next/docs/PODCAST_FRONTEND_DESIGN.md`
- `facttracer-next/docs/API_SPEC.md` podcast endpoints 반영

남은 항목:

- API types/client
- `/podcasts` route
- section UI
- player provider
- mini player
- expanded player sheet
- audio playback
- transcript/source/queue UI
- browser QA

### 16.3 Demo

상태: 참고용.

위치:

```text
qa/podcast-demo/index.html
```

이 demo는 방향성 참고용이며, 최종 프론트 구현은 FactTracer v2 디자인 시스템에 맞춰 `facttracer-next`에서 다시 구현한다.

## 17. 테스트 계획

### 17.1 Backend

필수:

```bash
cd facttracer-backend
.venv/bin/python -m pytest -q
.venv/bin/python scripts/audit_api_spec.py
.venv/bin/python -m compileall app scripts tests -q
FACTTRACER_DATABASE_URL=sqlite:///./test_podcast_migration.db .venv/bin/alembic upgrade head
```

검증 범위:

- personalized feed ordering
- detail transcript/sources/nextQueue
- duplicate prevention
- job auto publish
- OpenAI TTS segment rendering
- audio file serving
- render_audio job

### 17.2 Podcast Operations Audit

스테이징에서 팟캐스트 운영 증거를 생성할 때는 다음 smoke 스크립트를 먼저 실행한다.

```bash
cd facttracer-backend
.venv/bin/python scripts/run_podcast_operational_smoke.py \
  --api-base-url https://api.example.com \
  --feed recommended \
  --limit 1 \
  --variant short \
  --render-audio \
  --create-admin-failed-job \
  --record-events \
  --check-audio-stream \
  --check-admin-failed-jobs \
  --admin-email "$FACTTRACER_SMOKE_ADMIN_EMAIL" \
  --admin-password "$FACTTRACER_SMOKE_ADMIN_PASSWORD" \
  --enqueue-scheduler-check
```

`--render-audio`는 실제 OpenAI TTS 비용이 발생한다. 비용 없는 브라우저 스트리밍 경로만 먼저 확인할 때는 `--fixture-audio`를 사용한다.
`--create-admin-failed-job`은 없는 회차를 대상으로 실제 `render_podcast_audio` 작업을 실행해 `dead_letter` 실패 이력을 만들고, 관리자 실패 작업 표시 검증에 사용한다.
smoke 결과 JSON의 `publicApi.eventPersistence`는 팟캐스트 이벤트 6종 적재 수와 `UserInterestProfile` 토픽/포맷 가중치 누적 값을 포함한다.

남은 운영 체크리스트 전체는 다음 래퍼로 한 번에 판정한다.

```bash
cd facttracer-backend
.venv/bin/python scripts/verify_podcast_remaining_work.py \
  --api-base-url https://api.example.com \
  --admin-email "$FACTTRACER_SMOKE_ADMIN_EMAIL" \
  --admin-password "$FACTTRACER_SMOKE_ADMIN_PASSWORD" \
  --feed latest \
  --force
```

리포트의 `items` 배열은 `docs/PODCAST_REMAINING_WORK.md`의 남은 체크박스별 pass/fail, 관련 audit check, smoke 증거, `/admin/podcasts` 확인 URL을 포함한다. 명령 출력에서 비밀번호 값은 마스킹된다.
기본 추천 피드가 공식 출처 게이트로 draft 회차를 만들 수 있으므로, 운영 검증에서는 공개 가능한 `latest` 피드 또는 검증된 토픽/이슈를 지정한다.

스테이징/배포 환경에서 팟캐스트 운영 준비 상태는 다음 감사 스크립트로 점검한다.

```bash
cd facttracer-backend
.venv/bin/python scripts/audit_podcast_operations.py \
  --api-base-url https://api.example.com \
  --require-env-vars \
  --require-live-tts \
  --require-audio-stream \
  --require-events \
  --require-failed-job \
  --require-seed-script \
  --require-tts-retry-evidence \
  --json
```

기본 실행은 읽기 전용이다. 스케줄러가 due podcast job을 실제 큐에 등록하는지 확인해야 할 때만 다음 옵션을 추가한다.

```bash
.venv/bin/python scripts/audit_podcast_operations.py --enqueue-scheduler-check --json
```

감사 JSON의 `passed=true`, `failedChecks=[]`이면 필수 조건이 통과한 상태다. `summary`는 pass/warn/fail 개수를 제공한다.

감사 범위:

- OpenAI TTS 완료 회차와 오디오 저장 경로
- `podcast_live_tts_delivery`: OpenAI TTS 완료 회차의 저장 경로, 상세 API `audioUrl`, 실제 스트리밍 응답이 같은 `episodeId`로 연결되는지 확인
- `seed_podcast_episodes.py` 실행 메타데이터
- 공개 API `/v1/podcasts/home`, `/v1/podcasts`, `/v1/podcasts/{episodeId}/audio`
- Chrome/Safari User-Agent 기반 오디오 스트리밍 응답
- `/metrics`의 팟캐스트 운영 지표
- `podcast:auto`, `podcast:daily` 스케줄러 작업 이력
- TTS 세그먼트 attempt 로그 또는 작업 큐 재시도 이력
- 팟캐스트 행동 이벤트와 `UserInterestProfile` 누적
- 관리자 화면에서 확인할 실패 작업 이력

### 17.3 Frontend

필수:

```bash
cd facttracer-next
npm run lint
npm run build
```

브라우저 QA:

- `/podcasts` empty API state
- `/podcasts` with real API
- episode select
- mini player
- expanded player
- audio play/pause
- next queue
- transcript active row
- source links
- mobile 390px
- desktop 1440px

## 18. 구현 로드맵

### Phase 1 — Backend foundation

상태: 완료.

- Episode model
- generator
- API
- scheduler
- OpenAI TTS
- tests

### Phase 2 — Frontend playback MVP

다음 구현 대상.

- API types/client
- `/podcasts`
- home sections
- mini player
- player sheet
- audio playback
- transcript/source/queue

### Phase 3 — Admin operation

- admin podcast list
- issue-level generate action
- TTS retry
- archive
- script/source preview

### Phase 4 — Personalization improvement

- play/skip/completion events
- personalized model refinement
- daily briefing bundle
- push/digest integration

### Phase 5 — Audio/content quality

- longer-form episode
- chapter markers
- source-specific chapter jump
- manual script review for sensitive issues
- multi-issue daily episode

## 19. 수용 기준

전체 팟캐스트 기능 완료 기준:

- 공개 사용자가 `/podcasts`에서 회차를 고를 수 있다.
- 개인화/특집/최신/랭킹/카테고리 섹션이 보인다.
- 회차 선택 시 오디오가 재생된다.
- 하단 미니 플레이어가 동작한다.
- 확장 플레이어에서 대사, 출처, 다음 재생이 보인다.
- 백엔드가 자동으로 episode를 생성하고 발행한다.
- OpenAI TTS로 오디오 파일이 생성된다.
- 오디오 생성 실패/미설정 상태도 UI에서 깨지지 않는다.
- 운영자가 회차 생성과 TTS 재렌더링을 실행할 수 있다.
- 테스트와 빌드가 통과한다.

## 20. 핵심 결정 요약

- 팟캐스트는 기사 내부 기능이 아니라 별도 제품 표면이다.
- 목표는 “국민의 알 권리”다.
- 콘텐츠는 자동 생성/자동 발행을 기본으로 한다.
- 추천은 기존 이슈 랭킹/개인화 알고리즘을 재사용한다.
- 포맷은 1인, 2인, 3인 대화형을 모두 지원한다.
- 패널은 고정하지 않고 주제별 캐릭터형으로 구성한다.
- 오디오는 OpenAI TTS를 사용한다.
- 대사와 출처는 항상 플레이어에 함께 제공한다.
- 프론트는 음악 앱의 사용성을 참고하되 FactTracer v2 디자인 정서에 맞춘다.
