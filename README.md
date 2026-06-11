# FactTracer

팩트 기반 뉴스 검증과 증거 추적을 제공하는 웹 서비스입니다.
`facttracer-backend`(FastAPI)와 `facttracer-next`(Next.js)로 구성되어 있으며,
기사 수집/요약, 주장 분해, 검증 흐름, 사용자 피드백, 팟캐스트 생성까지 한 번에 다룹니다.

## 목차

- [구성 요소](#구성-요소)
- [빠른 시작](#빠른-시작)
- [로컬 개발 실행](#로컬-개발-실행)
- [환경 변수](#환경-변수)
- [디렉터리 구조](#디렉터리-구조)
- [검증 및 테스트](#검증-및-테스트)
- [주요 API와 화면](#주요-api와-화면)
- [문서](#문서)

## 구성 요소

- `facttracer-backend`: FastAPI 기반 API 서버, DB, AI 파이프라인, 작업 큐/스케줄러, 팟캐스트 생성
- `facttracer-next`: 공개 페이지 + 관리자 화면(뉴스/주장/검수/팟캐스트)
- `facttracer-prototype`: 초기 시안/정적 산출물 보관용(참고용)
- `docs`: PRD/설계/감사 문서
- `qa`: QA 결과 스크린샷, 검증/운영 점검 기록

## 빠른 시작

### 1) Docker로 실행 (권장)

루트 경로에서 실행합니다.

```bash
docker compose up --build
```

실행 후 접속:

- 웹: http://localhost:3000
- API 헬스체크: http://localhost:8000/health

`docker-compose.yml` 기본 구성은 아래 동작입니다.

- API: `facttracer-backend` 컨테이너(`:8000`)
- 웹: `facttracer-next` 컨테이너(`:3000`)
- SQLite DB는 컨테이너 볼륨(`api_data`)에 저장
- 워커/스케줄러는 기본적으로 백엔드 서버 내부 inline 모드로 동작

macOS에서는 `start-facttracer.command`를 더블클릭해 백그라운드 실행 후 브라우저가 자동으로 열립니다.

### 2) 운영형(PostgreSQL + Redis + RQ) 구성

백엔드 단독 운영 구성이 필요하면 `facttracer-backend/docker-compose.yml`을 사용합니다.

```bash
cd facttracer-backend
docker compose up --build
```

이 구성은 다음을 포함합니다.

- PostgreSQL
- Redis
- RQ 워커
- 별도 스케줄러 프로세스

## 로컬 개발 실행

로컬에서 백엔드/프론트를 각각 실행할 때는 아래 순서를 추천합니다.

### 1. 백엔드 (Python)

```bash
cd facttracer-backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env
# OPENAI/DEEPSEEK 키는 필요 시 입력
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

백그라운드 작업이 분리되어 필요할 경우:

```bash
python scripts/run_worker.py      # 백엔드 내장 워커
python scripts/run_scheduler.py   # 스케줄러 수동 기동
```

### 2. 프론트엔드 (Next.js)

```bash
cd facttracer-next
npm install
cp .env.example .env.local

npm run dev -- --port 3002
```

브라우저:

- 웹: http://localhost:3002

참고:

- 프론트는 `NEXT_PUBLIC_API_BASE_URL`로 API 주소를 사용합니다.
- API가 없으면 더미가 아닌 빈 상태 기반 UI를 보여주고, API 호출 실패 시 사용자 안내를 제공합니다.

## 환경 변수

### 백엔드

기본값 템플릿은 `facttracer-backend/.env.example`에 있습니다.
루트 `docker compose`는 `facttracer-backend/.env`를 직접 사용합니다.

핵심 값은 아래와 같습니다.

```bash
FACTTRACER_DATABASE_URL=sqlite:///./facttracer.db
FACTTRACER_JWT_SECRET=replace-this-secret
FACTTRACER_CORS_ORIGINS=http://localhost:3000,http://localhost:3002
FACTTRACER_REDIS_URL=redis://localhost:6379/0
FACTTRACER_WORKER_BACKEND=inline
FACTTRACER_EMBEDDED_SCHEDULER_ENABLED=true
FACTTRACER_AI_PROCESSING_ENABLED=true
OPENAI_API_KEY=
DEEPSEEK_API_KEY=
```

AI 기능을 쓰지 않을 경우 `FACTTRACER_AI_PROCESSING_ENABLED=false`로 두고 실행하면
규칙 기반/운영상태 전환으로 동작합니다.

### 프론트엔드

`facttracer-next/.env.local` 기준입니다.

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_API_TIMEOUT_MS=15000
FACTTRACER_API_BASE_URL=http://localhost:8000
```

## 디렉터리 구조

- `facttracer-backend/`
  - `app/`: API 라우트, 서비스, 모델, 스케줄러/워커
  - `scripts/`: 수동 수집/QA/운영 점검 유틸
  - `storage/`: 팟캐스트 오디오 및 중간 파일
  - `.env`, `docker-compose.yml`, `Dockerfile`
- `facttracer-next/`
  - `src/app`: 라우트 페이지(공개/관리자 영역)
  - `src/components`: 화면 컴포넌트(검수, 주장, 팟캐스트, 알림)
  - `public/`: 정적 리소스, PWA 파일
  - `docs/`: 프론트엔드 설계/API 스펙
- `docs/`: PRD/설계/점검 정책
- `qa/`: QA 리포트, 스크린샷, 사운드 샘플

## 검증 및 테스트

### 백엔드

```bash
cd facttracer-backend
pytest
python scripts/audit_api_spec.py
```

### 프론트엔드

```bash
cd facttracer-next
npm run lint
npm run build
FACTTRACER_AUDIT_BASE_URL=http://localhost:3002 npm run acceptance:audit
```

### 점검 스크립트 예시

```bash
python facttracer-backend/scripts/run_podcast_operational_smoke.py \
  --api-base-url http://localhost:8000 \
  --feed latest --limit 1 --fixture-audio \
  --create-admin-failed-job --record-events

python facttracer-backend/scripts/verify_podcast_remaining_work.py \
  --api-base-url http://localhost:8000 \
  --admin-email "$FACTTRACER_SMOKE_ADMIN_EMAIL" \
  --admin-password "$FACTTRACER_SMOKE_ADMIN_PASSWORD" \
  --feed latest --force
```

## 주요 API와 화면

백엔드에서 제공하는 핵심 API는 `/v1` 경로 기반으로 공개/검수/팟캐스트/작업 관리 엔드포인트를 포함합니다.
상세 라우트는 `facttracer-backend/README.md`를 기준으로 확인하세요.

프론트 노출 라우트(예시):

- 공개: `/`, `/issues/[issueId]`, `/saved`, `/verify`, `/notifications`, `/reports/[issueId]`
- 계정: `/login`, `/signup`, `/account`
- 운영: `/admin`, `/admin/issues/[issueId]`, `/admin/reports`, `/admin/sources`, `/admin/agents`

## 문서

- 백엔드 전체 가이드: `facttracer-backend/README.md`
- 프론트엔드 설계/QA: `facttracer-next/README.md`
- 팟캐스트 시스템 설계: `docs/PODCAST_SYSTEM_DESIGN.md`
- PRD(제품 요구사항): `PRD.md`
- 운영/감사 기록: `docs/PODCAST_LOCAL_OPERATIONAL_VERIFICATION_2026-06-11.md`
