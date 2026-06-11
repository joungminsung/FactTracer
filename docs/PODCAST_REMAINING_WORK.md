# 팟캐스트 미완료 항목

기준일: 2026-06-11

이 문서는 팟캐스트 기능에서 아직 닫히지 않은 작업만 정리한다. 로컬 코드 검증, 백엔드 테스트, 프론트 빌드, API 문서 감사, 로컬 샘플 데이터 기반 `/podcasts` 브라우저 상호작용 QA, 데스크톱/모바일 플레이어 레이아웃 QA, fixture 오디오 기반 브라우저 재생 QA, 대사별 출처 매핑/위험 표현 패턴 검출, 출처 부족 draft 회차 관리자 탐색/보완 진입 흐름, 팟캐스트 추천 운영 가중치 설정, 민감 주제 공식 출처 기본 요구, 자동발행 최소 품질 점수 설정, 팟캐스트 운영 메트릭, 로그인 사용자 행동 이후 개인화 추천 순서 변경 통합 테스트, 콘텐츠 샘플 생성/검수 통합 테스트, 관리자 단일 이슈 생성/TTS 후속 렌더링/상태 변경 공개 피드 반영/실패 사유 요약 API 테스트, 로컬 Docker 기반 seed/smoke/audit 검증은 제외했다.

## 1. 운영 환경 검증

목표: 실제 스테이징/배포 환경에서 자동 생성과 OpenAI 음성 렌더링이 끝까지 되는지 확인한다.

현재 로컬 Docker 검증 메모: 2026-06-11에 `docker compose` API 컨테이너에서 seed, fixture 오디오, 공개 오디오 스트리밍, Chrome/Safari User-Agent 스트리밍, 이벤트 6종 적재, `UserInterestProfile` 누적, 실패 `render_podcast_audio` JobAttempt, 필수 팟캐스트 환경변수 적용, 스케줄러 작업 흔적을 확인했다. 이후 유효한 `OPENAI_API_KEY`를 주입하고 API 컨테이너를 재생성한 뒤 `verify_podcast_remaining_work.py --feed latest --force`를 실행해 OpenAI TTS 완료 회차, 공개 상세 API `audioUrl`, 실제 오디오 스트리밍, 이벤트/개인화 누적, 관리자 실패 작업 표시 데이터를 모두 통과했다. 최종 audit은 `status=passed`, `passed=true`, `failedChecks=[]`, `warnings=0`이었다. 로컬 증거는 `docs/PODCAST_LOCAL_OPERATIONAL_VERIFICATION_2026-06-11.md`에 남겼다. `recommended` 피드는 공식 출처 게이트에 걸린 draft 회차를 생성할 수 있으므로, 운영 검증에서는 공개 가능한 피드/토픽/이슈를 지정해야 한다.

별도 스테이징/배포 URL은 현재 워크스페이스 설정에서 확인되지 않았다. 아래 체크박스는 실제 외부 스테이징/배포 환경이 따로 있을 경우 해당 환경에서 같은 명령을 재실행해 닫는다.

스테이징 검증 명령:

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

`--render-audio`는 실제 OpenAI TTS 비용이 발생한다. 브라우저 스트리밍과 이벤트 적재만 먼저 검증할 때는 `--render-audio` 대신 `--fixture-audio`를 사용한다.
`--create-admin-failed-job`은 없는 회차를 대상으로 `render_podcast_audio` 작업을 실제 실행해 `dead_letter` 실패 이력을 만들고, `/admin/podcasts` 실패 작업 섹션 검증에 사용할 수 있게 한다.
감사 스크립트의 `--require-audio-stream`은 일반 오디오 응답과 Chrome/Safari User-Agent 기반 스트리밍 응답을 함께 확인한다.
`--require-live-tts`와 `--api-base-url`을 함께 사용하면 `podcast_live_tts_delivery` 체크가 OpenAI TTS 완료 회차의 `audioStoragePath`, 상세 API `audioUrl`, 실제 오디오 스트리밍 응답을 같은 `episodeId` 기준으로 검증한다.
감사 JSON의 `passed=true`, `failedChecks=[]`이면 필수 조건이 통과한 상태이며, `summary`에서 pass/warn/fail 개수를 확인한다.
smoke 결과의 `publicApi.eventPersistence`는 이벤트 타입별 적재 수와 `UserInterestProfile`의 토픽/포맷 가중치 누적을 함께 출력한다.

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

남은 체크박스 전체를 한 번에 판정하는 최종 리포트:

```bash
cd facttracer-backend
.venv/bin/python scripts/verify_podcast_remaining_work.py \
  --api-base-url https://api.example.com \
  --admin-email "$FACTTRACER_SMOKE_ADMIN_EMAIL" \
  --admin-password "$FACTTRACER_SMOKE_ADMIN_PASSWORD" \
  --feed latest \
  --force
```

이 명령은 `run_podcast_operational_smoke.py`와 `audit_podcast_operations.py`를 함께 실행하고 `items` 배열에 아래 체크박스별 pass/fail, 증거 JSON, `/admin/podcasts` 확인 URL을 출력한다. 비밀번호 값은 출력에서 `<redacted>`로 마스킹된다.

- [ ] 유효한 `OPENAI_API_KEY`가 주입된 스테이징/배포 환경에서 OpenAI TTS 완료 회차를 1개 이상 생성하고 `podcast_live_tts_audio`가 `pass`인지 확인
- [ ] 스테이징/배포 환경에서 위 smoke 명령과 audit 명령을 실행해 `--require-live-tts`를 포함한 전체 요구 조건이 `status=passed`, `passed=true`, `failedChecks=[]`인지 확인
- [ ] OpenAI TTS로 생성된 실제 오디오 파일의 저장 경로와 배포 접근 URL이 같은 회차 기준으로 확인되는지 `podcast_live_tts_delivery=pass`로 검증

## 2. 추천 알고리즘 운영 검증

목표: 실제 사용자 행동 데이터로 추천 순서가 유효하게 움직이는지 확인한다.

- [ ] 스테이징/배포 환경에서 smoke가 기록한 `podcast_home_impression`, `podcast_play_start`, `podcast_progress`, `podcast_complete`, `podcast_skip`, `podcast_source_click` 로그와 `UserInterestProfile` 토픽/포맷 가중치 누적을 운영 DB 기준으로 확인

## 3. 관리자 운영 검증

목표: 운영자가 자동 파이프라인을 신뢰하고 복구할 수 있는지 실제 데이터로 확인한다.

- [ ] 스테이징/배포 `/admin/podcasts`에서 `--create-admin-failed-job`으로 생성한 실패 `render_podcast_audio` 작업 이력과 운영자용 `userMessage`가 표시되는지 브라우저로 확인
