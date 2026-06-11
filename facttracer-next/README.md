# FactTracer Next

FactTracer 프론트엔드는 사건, 주장, 쟁점, 근거를 구조화해 보여주는 공개 웹과 운영 검수 화면을 제공합니다. 서버 코드는 포함하지 않으며, 서버가 준비되면 환경 설정의 기본 주소만 연결해 실제 응답으로 동작하도록 구성되어 있습니다.

## 주요 문서

- [프로덕션 설계](./docs/PRODUCTION_DESIGN.md)
- [프론트엔드 API 명세](./docs/API_SPEC.md)

## 실행

```bash
npm run dev -- --port 3002
```

## 검증

```bash
npm run lint
npm run build
FACTTRACER_AUDIT_BASE_URL=http://localhost:3002 npm run acceptance:audit
```

## 서버 연결

`.env.local`에 다음 값을 설정합니다.

```bash
NEXT_PUBLIC_API_BASE_URL=https://api.example.com
```

서버 주소가 없을 때도 화면 골격과 빈 상태는 유지됩니다. 생성, 수정, 삭제 행동은 사용자 관점의 실패 메시지를 표시합니다.

## 포함된 화면

- 공개 홈 `/`
- 이슈 상세 `/issues/[issueId]`
- 저장 이슈 `/saved`
- 검증하기 `/verify`
- 알림 `/notifications`
- 리포트 `/reports/[issueId]`
- 로그인 `/login`
- 회원가입 `/signup`
- 내 계정 `/account`
- 운영 콘솔 `/admin`
- 검토 상세 `/admin/issues/[issueId]`
- 신고 처리 `/admin/reports`
- 출처 관리 `/admin/sources`
- 자동 처리 기록 `/admin/agents`
