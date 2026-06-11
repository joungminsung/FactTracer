# FactTracer 문서 허브

최종적으로 확인해야 할 문서는 아래 분류로 정리했습니다.

## 1) 제품/설계 핵심

- [제품 요구사항: PRD](../PRD.md)
- [시스템 설계(팟캐스트 중심)](./PODCAST_SYSTEM_DESIGN.md)
- [DB 품질 감사](./DB_INFORMATION_QUALITY_AUDIT_2026-06-11.md)
- [추천 정책(팟캐스트)](./PODCAST_RECOMMENDATION_POLICY.md)
- [운영 검증 기록(로컬)](./PODCAST_LOCAL_OPERATIONAL_VERIFICATION_2026-06-11.md)
- [잔여 작업 정리](./PODCAST_REMAINING_WORK.md)

## 2) 백엔드 문서

- [백엔드 README](../facttracer-backend/README.md)
- [백엔드 미완료 기능 목록](../facttracer-backend/docs/BACKEND_INCOMPLETE_FEATURES.md)
- `facttracer-backend/.env.example` 환경 변수 템플릿
- `facttracer-backend/docker-compose.yml` 운영형(PostgreSQL + Redis + RQ) 구성
- `facttracer-backend/scripts/*`: 수집/검증/스모크/감사용 실행 스크립트

## 3) 프론트엔드 문서

- [Next.js README](../facttracer-next/README.md)
- [프론트엔드 설계](../facttracer-next/docs/PRODUCTION_DESIGN.md)
- [API 계약서](../facttracer-next/docs/API_SPEC.md)
- [팟캐스트 화면 설계](../facttracer-next/docs/PODCAST_FRONTEND_DESIGN.md)

## 4) 운영 계획/디자인 스펙

- `docs/superpowers/plans/*`
- `docs/superpowers/specs/*`
- `facttracer-next/docs/superpowers/plans/*`
- `facttracer-next/docs/superpowers/specs/*`

## 5) QA/검증 자료

- `qa/web-qa-2026-06-10/*`
- `qa/ui-audit-2026-06-09/*`
- `qa/podcast-demo/*`
- `qa/podcast-audio/*`

## 6) 정리 원칙

- 코드/문서/증빙 파일을 기능별 디렉터리로 분리

- 추적이 필요한 산출물은 원본 경로를 유지하고, 루트 README에서 문서 허브로 한 번에 접근 가능하도록 관리
