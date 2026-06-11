# FactTracer Backend PRD 기능 충족 현황

작성 기준: `PRD.md`, `facttracer-backend` 현재 코드  
최종 갱신일: 2026-06-09

이 문서는 최초에는 백엔드 미완료 기능을 추적하기 위해 작성되었지만, 현재는 해당 항목을 어떤 코드로 충족했는지 확인하는 완료 매트릭스로 사용한다.

## 1. 완료 요약

| 범위 | 현재 상태 | 주요 코드 증거 |
| --- | --- | --- |
| 정규화 데이터 모델 | 완료 | `app/models.py` |
| Alembic/PostgreSQL 준비 | 완료 | `alembic.ini`, `app/db/migrations/*`, `pyproject.toml` |
| Redis/RQ 작업큐 준비 | 완료 | `app/services/jobs.py`, `scripts/run_rq_worker.py` |
| 스케줄러/재시도/dead-letter | 완료 | `SchedulerHeartbeat`, `app/services/scheduler/runtime.py`, `app/services/jobs.py` |
| 검색/RSS/JSON/공식/SNS/YouTube 수집 | 완료 | Google News search, DiscoveryTopic, `app/collectors/*`, `app/workers/issue_jobs.py` |
| 기사 파싱/중복 제거 | 완료 | `app/services/articles/*` |
| 이슈 점수/후보/매칭/공개 | 완료 | `app/services/issues/*` |
| 주장 추출/분류/엔티티/클러스터링 | 완료 | DeepSeek claim extraction + `app/services/claims/*`, `app/services/vector/store.py` |
| 근거 검색/랭킹/판정/이력 | 완료 | DeepSeek evidence/verifier + `app/services/evidence/*`, `app/services/verification/*` |
| 관점 지도/라벨 안전장치 | 완료 | DeepSeek perspective grouping + `app/services/perspectives/mapper.py`, `app/services/safety/*` |
| 구조화된 사용자 주장 처리 | 완료 | `app/api/routes/issues.py`, `app/services/claims/workflow.py` |
| 알림/푸시 토큰/Expo 어댑터 | 완료 | `app/services/notifications/*`, `app/api/routes/users.py` |
| URL/텍스트/파일/PDF/이미지/YouTube 직접 검증 | 완료 | `app/services/manual_checks/*`, `app/services/files/*` |
| 관리자 병합/분리/숨김/재검증/출처 정책 | 완료 | `app/api/routes/admin.py`, `app/services/admin/*` |
| 보안/안정성/관측 | 완료 | `app/core/rate_limit.py`, `app/api/routes/health.py`, `app/services/audit/logger.py` |
| Docker/Compose/CI | 완료 | `Dockerfile`, `docker-compose.yml`, `.github/workflows/*` |

검증 결과:

```bash
pytest
# 12 passed

python scripts/audit_api_spec.py
# API spec audit passed: 60 declared routes matched
```

## 2. PRD 기능 요구사항 충족 매트릭스

### 2.1 자동 이슈 기능

| 요구사항 | 상태 | 구현 |
| --- | --- | --- |
| FR-ISSUE-001 뉴스 데이터 주기 수집 | 완료 | `schedule_due_discovery_jobs`, `schedule_due_search_jobs`, `schedule_due_collector_jobs` |
| FR-ISSUE-002 이슈 점수 계산 | 완료 | `app/services/issues/scoring.py`, discovery signal score |
| FR-ISSUE-003 이슈 후보 생성 | 완료 | `DiscoveredIncident`, `ensure_issue_candidate`, discovery issue promotion |
| FR-ISSUE-004 후보 승인/병합/삭제 | 완료 | `approve_issue_candidate`, `merge_issue_route`, `hide_issue_route` |
| FR-ISSUE-005 자동 공개/민감 이슈 검토 | 완료 | `issue_auto_publish_threshold`, `AdminQueueItem.status`, `is_public` |

### 2.2 기사 수집 기능

| 요구사항 | 상태 | 구현 |
| --- | --- | --- |
| FR-ARTICLE-001 이슈 관련 기사 자동 수집 | 완료 | Google News search, RSS, JSON news, official, social, YouTube collectors |
| FR-ARTICLE-002 중복 기사 제거 | 완료 | URL 정규화, `dedup_hash`, article upsert |
| FR-ARTICLE-003 본문 추출 실패 대체 | 완료 | `title_only`, `fallback_text`, manual input fallback |
| FR-ARTICLE-004 기사 링크 직접 제보 | 완료 | `/v1/verification-requests`, `/v1/checks` |

### 2.3 주장 추출 기능

| 요구사항 | 상태 | 구현 |
| --- | --- | --- |
| FR-CLAIM-001 기사에서 검증 가능한 주장 추출 | 완료 | `DeepSeekAnalysisService.extract_claims_from_article`, fallback `extract_claim_candidates` |
| FR-CLAIM-002 주장 유형 분류 | 완료 | DeepSeek `claim_type`, fallback `classify_claim` |
| FR-CLAIM-003 같은 쟁점 클러스터링 | 완료 | `assign_cluster`, OpenAI embedding/vector fallback |
| FR-CLAIM-004 새 클러스터 후보 등록 | 완료 | `ClaimCluster.status="candidate"` |

### 2.4 검증 기능

| 요구사항 | 상태 | 구현 |
| --- | --- | --- |
| FR-VERIFY-001 주장별 공식자료/근거 검색 | 완료 | DeepSeek local evidence matching + `retrieve_evidence_for_claim` |
| FR-VERIFY-002 날짜/수치/기관/장소/대상 비교 | 완료 | DeepSeek entities + `extract_entities`, `compare_entities` |
| FR-VERIFY-003 판정 라벨 생성 | 완료 | `DeepSeekAnalysisService.verify_claim_against_evidence`, fallback `verdict_from_evidence` |
| FR-VERIFY-004 근거 부족/검증 불가 허용 | 완료 | `근거 부족`, `법적 판단 필요`, `맥락 누락` 라벨 |
| FR-VERIFY-005 공식자료 등장 시 재계산 | 완료 | official/public source article 처리 시 기존 claim 재검증 |

### 2.5 쟁점 지도 기능

| 요구사항 | 상태 | 구현 |
| --- | --- | --- |
| FR-MAP-001 이슈별 주요 쟁점 자동 생성 | 완료 | claim cluster 기반 `refresh_issue_cache` |
| FR-MAP-002 관점별 주장 요약 | 완료 | DeepSeek perspective grouping + `rebuild_perspectives` |
| FR-MAP-003 관점 간 충돌/공통분모 표시 | 완료 | `conflicts_json`, `common_ground_json` |
| FR-MAP-004 진영 라벨 대신 주장 중심 관점명 | 완료 | `sanitize_public_label`, `PERSPECTIVE_NAMES` |

### 2.6 사용자 참여 기능

| 요구사항 | 상태 | 구현 |
| --- | --- | --- |
| FR-USER-CLAIM-001 구조화된 주장 제출 | 완료 | `POST /v1/issues/{issueId}/claims` |
| FR-USER-CLAIM-002 근거 링크 제출 | 완료 | `evidence_url`, evidence 연결 workflow |
| FR-USER-CLAIM-003 자동 분류/중복 확인 | 완료 | `ingest_submitted_claim`, cluster similarity |
| FR-USER-CLAIM-004 낙인/비방 정제/비공개 처리 | 완료 | `moderate_claim_text`, `sanitize_claim_text` |
| FR-USER-CLAIM-005 정치 성향 공개 라벨 금지 | 완료 | 공개 라벨 필터와 관점명 생성 정책 |

### 2.7 알림 기능

| 요구사항 | 상태 | 구현 |
| --- | --- | --- |
| FR-NOTI-001 관심 이슈 구독 | 완료 | `POST/DELETE /v1/issues/{issueId}/subscribe` |
| FR-NOTI-002 공식자료/수치/판정 변경 알림 | 완료 | `UpdateLog`, `create_issue_notification` |
| FR-NOTI-003 앱 푸시 알림 | 완료 | `DeviceToken`, `deliver_notification`, Expo adapter |

### 2.8 직접 검증 기능

| 요구사항 | 상태 | 구현 |
| --- | --- | --- |
| FR-MANUAL-001 뉴스 URL 직접 검증 | 완료 | `/v1/checks` inputType `url` |
| FR-MANUAL-002 텍스트 직접 입력 | 완료 | `/v1/checks` inputType `text` |
| FR-MANUAL-003 이미지/PDF/YouTube 링크 | 완료 | `/v1/files`, file parser, OCR optional path, YouTube transcript adapter |
| FR-MANUAL-004 기존 이슈 매칭/단독 결과 저장 | 완료 | `matched_issue_id`, `standalone_result_id`, article pipeline 연결 |

### 2.9 관리자 기능

| 요구사항 | 상태 | 구현 |
| --- | --- | --- |
| FR-ADMIN-001 이슈 후보 목록 | 완료 | `/v1/admin/issue-candidates` |
| FR-ADMIN-002 병합/분리/숨김 | 완료 | `/merge`, `/split`, `/hide` |
| FR-ADMIN-003 신고 주장/리포트 검토 | 완료 | report resolve + moderation audit |
| FR-ADMIN-004 출처 도메인 신뢰도 수정 | 완료 | `/v1/admin/sources/{sourceId}/credibility` |
| FR-ADMIN-005 에이전트 로그 확인 | 완료 | `AgentRun`, `/v1/admin/agents` |
| FR-ADMIN-006 특정 이슈/주장 재검증 | 완료 | issue reverify, claim reverify |

## 3. 비기능 요구사항 충족

| 영역 | 상태 | 구현 |
| --- | --- | --- |
| 성능 | 완료 | source별 수집 주기, scheduler, worker 분리 |
| 안정성 | 완료 | `SchedulerHeartbeat`, DB lock, `JobAttempt`, retry, `dead_letter`, fallback parsing |
| 투명성 | 완료 | evidence links, verdict history, update logs, agent input/output |
| 안전성 | 완료 | 낙인 표현 정제, 진영 라벨 차단, 법적 판단 분리 |
| 보안 | 완료 | JWT, role check, MIME/크기 검사, URL scheme 검사, rate limit |
| 관측 | 완료 | `/metrics`, `AgentRun`, `CollectorRun`, `JobAttempt` |
| 배포 | 완료 | Dockerfile, Docker Compose, GitHub Actions CI |

## 4. 운영 시 필요한 외부 설정

코드는 PRD 백엔드 기능을 구현했지만, 실제 운영 품질은 아래 외부 설정에 따라 달라진다.

- 기본 검색 discovery는 Google News RSS 검색으로 동작한다. 별도 뉴스 검색 API는 `SourceDomain.collection_url` 또는 JSON collector endpoint로 추가 연결할 수 있다.
- `DiscoveryTopic`은 broad query 검색 결과를 기사 유사도 기반으로 묶고 `DiscoveredIncident`, `Issue`, `SearchKeyword`를 생성한다.
- `FACTTRACER_WORKER_BACKEND=rq` 운영 시 Redis가 필요하다.
- PostgreSQL 운영 시 `FACTTRACER_DATABASE_URL=postgresql+psycopg://...`로 전환하고 `alembic upgrade head`를 실행한다.
- Expo push 발송은 `FACTTRACER_EXPO_PUSH_ENABLED=true`와 유효한 Expo push token이 필요하다.
- OCR은 Docker 이미지처럼 `tesseract-ocr`와 `tesseract-ocr-kor`가 설치된 환경에서 실제 이미지 텍스트 추출이 동작한다.
- `FACTTRACER_AI_PROCESSING_ENABLED=true`와 API key가 있으면 OpenAI embedding, DeepSeek 기사 분석, 주장 추출, 근거 후보 매칭, 판정, 관점 생성이 활성화된다.
- API key가 없거나 자동 처리가 꺼져 있으면 규칙 기반 fallback과 운영 검토 상태로 전환된다.
- `FACTTRACER_EMBEDDED_SCHEDULER_ENABLED=true`와 `FACTTRACER_EMBEDDED_WORKER_ENABLED=true`이면 API 서버 lifespan에서 내장 스케줄러와 내장 워커가 함께 실행된다. 기본 inline 모드에서는 서버만 켜도 주기 수집, discovery, 검색 수집, 분석 작업이 큐를 거쳐 순차 처리된다.
- 검색/수집 작업은 기사 저장 후 `parse_article` 작업을 큐에 넣고 종료한다. 기사 분석, 주장 추출, 근거 검색, 판정은 parse 계열 작업이 우선순위 큐에서 처리한다.
- `FACTTRACER_WORKER_BACKEND=rq` 운영에서는 내장 워커가 큐를 직접 실행하지 않으며, `scripts/run_rq_worker.py` 같은 별도 RQ 워커가 작업을 처리한다.

## 5. 완료 판정

`BACKEND_INCOMPLETE_FEATURES.md`에 적었던 백엔드 구현 항목은 현재 코드상 모두 대응 모듈, API, 데이터 모델, 테스트 또는 운영 설정으로 연결되어 있다. 외부 API 키와 실제 수집원 URL은 배포 환경 설정값이며, 서버 코드는 해당 값을 연결하면 수집/분석/검증/알림 파이프라인이 실행되는 구조다.
