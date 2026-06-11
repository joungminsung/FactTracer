# FactTracer Backend

Python/FastAPI 기반 FactTracer 백엔드입니다. `facttracer-next`의 `/v1` API 계약을 구현하며, 서버 주소를 프론트 `.env.local`에 연결하면 더미 데이터 없이 실제 응답으로 동작합니다.

## 기술 구성

- FastAPI
- SQLAlchemy + SQLite/PostgreSQL
- Alembic
- Redis/RQ 준비 설정
- JWT 인증
- OpenAI Embeddings
- DeepSeek OpenAI-compatible Chat Completions
- Google News 검색/RSS/JSON/공식 출처 수집 파이프라인
- 감시 주제 기반 사건 discovery/정의/키워드 확장
- 내장 스케줄러 heartbeat/lock

## 실행

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

프론트 연결:

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
FACTTRACER_API_BASE_URL=http://localhost:8000
```

## 환경 변수

```bash
FACTTRACER_DATABASE_URL=sqlite:///./facttracer.db
FACTTRACER_JWT_SECRET=replace-this-secret
FACTTRACER_CORS_ORIGINS=http://localhost:3002,http://127.0.0.1:3002,http://localhost:3003,http://127.0.0.1:3003
FACTTRACER_REDIS_URL=redis://localhost:6379/0
FACTTRACER_WORKER_BACKEND=inline
FACTTRACER_EMBEDDED_SCHEDULER_ENABLED=true
FACTTRACER_SCHEDULER_POLL_SECONDS=30
FACTTRACER_RATE_LIMIT_PER_MINUTE=600
FACTTRACER_COLLECTOR_TIMEOUT_SECONDS=12
FACTTRACER_OBJECT_STORAGE_PATH=./storage
FACTTRACER_EXPO_PUSH_ENABLED=false

OPENAI_API_KEY=
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_EMBEDDING_DIMENSIONS=
OPENAI_TTS_MODEL=gpt-4o-mini-tts
OPENAI_TTS_RESPONSE_FORMAT=wav
OPENAI_TTS_SPEED=1.0
OPENAI_TTS_TIMEOUT_SECONDS=120
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
FACTTRACER_PODCAST_TTS_PRONUNCIATION_LEXICON=

DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_FLASH_MODEL=deepseek-v4-flash
DEEPSEEK_PRO_MODEL=deepseek-v4-pro
FACTTRACER_AI_PROCESSING_ENABLED=true
```

`FACTTRACER_AI_PROCESSING_ENABLED=true`와 API 키가 설정되면 자동 수집/검색 수집/직접 검증/사용자 제출 주장 처리에서 AI 파이프라인이 실행됩니다. `OPENAI_API_KEY`는 주장 임베딩, 유사 클러스터 탐색, OpenAI TTS 팟캐스트 오디오 렌더링에 사용하고, `DEEPSEEK_API_KEY`는 검색 키워드 생성, 기사 분석, 주장 추출, 사용자 주장 구조화, 근거 후보 매칭, 주장 판정, 관점 생성, 재검증 계획 생성에 사용합니다. 키가 없거나 자동 처리가 꺼져 있으면 요청은 접수되고 규칙 기반 fallback과 운영 화면의 처리 기록으로 전환됩니다.

Discovery는 `DiscoveryTopic`의 broad query를 주기적으로 검색하고, 결과 기사를 유사도 기반으로 묶어 `DiscoveredIncident`를 만든 뒤 `Issue`와 정밀 `SearchKeyword`로 승격합니다. 즉, 사람이 사건명을 정확히 등록하지 않아도 상위 감시 주제에서 사건 후보를 정의할 수 있습니다.

## 작업 실행

로컬 기본값은 API 서버 안에서 내장 스케줄러와 내장 워커가 함께 실행되는 inline 모드입니다. `DiscoveryTopic`, `SearchKeyword`, `SourceDomain`의 주기가 도래하면 스케줄러가 큐를 만들고 워커가 큐를 1개씩 실행합니다.
검색/수집 작업은 기사 레코드 저장까지만 담당하고, 주장 추출·근거 검색·판정은 `parse_article` 작업으로 분리되어 우선 처리됩니다. SQLite 로컬 DB는 WAL 모드와 busy timeout을 적용해 화면 조회 중 백그라운드 쓰기 작업과 충돌을 줄입니다.

```bash
uvicorn app.main:app --reload --port 8001
```

수동/분리 실행이 필요할 때:

```bash
python scripts/run_worker.py
python scripts/run_scheduler.py
```

초기 팟캐스트 회차를 개발/스테이징에 채울 때:

```bash
python scripts/seed_podcast_episodes.py --limit 6
python scripts/seed_podcast_episodes.py --feed category --topic IT --variant deep --render-audio
python scripts/seed_podcast_episodes.py --limit 4 --fixture-audio
```

`--render-audio`는 실제 OpenAI TTS를 호출합니다. 브라우저 재생 QA만 필요하면 비용이 없는 `--fixture-audio`로 로컬 silent WAV를 붙일 수 있습니다.
시드 스크립트로 만든 회차는 `generation_json.seedScript`, `seedFeed`, `seededAt` 메타데이터를 남기므로 운영 감사에서 스테이징 시드 실행 여부를 확인할 수 있습니다.

스테이징에서 생성, TTS, 이벤트 적재, 공개 오디오 스트리밍 증거를 한 번에 만들 때:

```bash
python scripts/run_podcast_operational_smoke.py \
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

`--render-audio`는 실제 OpenAI TTS 비용이 발생합니다. 비용 없는 스트리밍 경로 검증은 `--fixture-audio`로 대체할 수 있습니다.
`--create-admin-failed-job`은 없는 회차를 대상으로 실제 `render_podcast_audio` 작업을 실행해 `dead_letter` 실패 이력을 만들고, `/admin/podcasts` 실패 작업 표시 검증에 사용할 수 있습니다.
결과 JSON의 `publicApi.eventPersistence`에서 팟캐스트 이벤트 6종 적재 수와 `UserInterestProfile` 토픽/포맷 가중치 누적을 확인할 수 있습니다.

남은 운영 체크리스트 최종 리포트:

```bash
python scripts/verify_podcast_remaining_work.py \
  --api-base-url https://api.example.com \
  --admin-email "$FACTTRACER_SMOKE_ADMIN_EMAIL" \
  --admin-password "$FACTTRACER_SMOKE_ADMIN_PASSWORD" \
  --feed latest \
  --force
```

이 스크립트는 smoke와 audit을 함께 실행하고 `docs/PODCAST_REMAINING_WORK.md`의 남은 항목별 pass/fail과 증거 JSON을 출력합니다. 비밀번호 값은 출력에서 마스킹됩니다.
기본 추천 피드가 공식 출처 게이트로 draft 회차를 만들 수 있으므로, 운영 검증에서는 공개 가능한 `latest` 피드 또는 검증된 토픽/이슈를 지정합니다.

스테이징 운영 감사:

```bash
python scripts/audit_podcast_operations.py \
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

감사 JSON의 `passed=true`, `failedChecks=[]`이면 필수 조건이 통과한 상태입니다.
`podcast_live_tts_delivery=pass`이면 OpenAI TTS 완료 회차의 저장 경로, 상세 API `audioUrl`, 실제 오디오 스트리밍 응답이 같은 `episodeId` 기준으로 연결된 상태입니다.

검색 사건 수집 테스트:

```bash
python scripts/run_search_collection.py "선관위 투표용지 부족 사태" --topic 정치 --limit 1 --max-items 3
```

Redis/RQ 실행:

```bash
FACTTRACER_WORKER_BACKEND=rq python scripts/run_rq_worker.py
```

RQ 모드에서는 내장 워커가 큐를 직접 실행하지 않고 RQ 워커가 처리합니다.

Docker Compose:

```bash
cd ..
docker compose up --build
```

## 구현된 주요 API

- `POST /v1/auth/signup`
- `POST /v1/auth/login`
- `GET /v1/users/me`
- `GET /v1/users/me/dashboard`
- `GET /v1/users/me/notifications`
- `POST /v1/users/me/device-tokens`
- `PATCH /v1/users/me/preferences`
- `GET /v1/issues/home`
- `GET /v1/issues/{issueId}`
- `POST /v1/verification-requests`
- `POST /v1/checks`
- `GET /v1/checks/{checkId}`
- `POST /v1/files`
- `POST /v1/issues/{issueId}/claims`
- `GET /v1/issues/{issueId}/updates`
- `GET /v1/issues/{issueId}/articles`
- `GET /v1/issues/{issueId}/claim-clusters`
- `GET /v1/issues/{issueId}/perspectives`
- `POST /v1/issues/{issueId}/subscribe`
- `POST /v1/issues/{issueId}/report`
- `GET /v1/podcasts/home`
- `GET /v1/podcasts`
- `GET /v1/podcasts/{episodeId}`
- `GET /v1/podcasts/{episodeId}/audio`
- `POST /v1/podcasts/{episodeId}/render-audio`
- `POST /v1/podcasts/generate`
- `GET /v1/admin/podcasts`
- `GET /v1/admin/podcasts/{episodeId}`
- `PATCH /v1/admin/podcasts/{episodeId}/status`
- `GET /v1/admin/dashboard`
- `GET /v1/admin/issues/{issueId}`
- `POST /v1/admin/issues/{issueId}/representative-image`
- `GET /v1/admin/issue-candidates`
- `POST /v1/admin/collectors/run`
- `GET /v1/admin/collectors/runs`
- `GET /v1/admin/jobs`
- `GET /v1/admin/reports`
- `GET /v1/admin/sources`
- `POST /v1/admin/sources`
- `GET /v1/admin/discovery-topics`
- `POST /v1/admin/discovery-topics`
- `POST /v1/admin/discovery-topics/{topicId}/run`
- `GET /v1/admin/discovered-incidents`
- `GET /v1/admin/search-keywords`
- `POST /v1/admin/search-keywords/seed`
- `POST /v1/admin/search-keywords/{keywordId}/run`
- `GET /v1/admin/scheduler`
- `POST /v1/admin/scheduler/tick`
- `GET /v1/admin/settings`
- `PATCH /v1/admin/settings`
- `GET /v1/admin/agents`

## 테스트

```bash
pytest
# 71 passed

python scripts/audit_api_spec.py
# API spec audit passed: 72 declared routes matched
```

## 문서

- [PRD 기준 백엔드 미완료 기능 정리](docs/BACKEND_INCOMPLETE_FEATURES.md)
