# FactTracer Frontend API Specification

이 문서는 `facttracer-next` 프론트엔드가 기대하는 백엔드 API 계약입니다. 서버 코드는 포함하지 않으며, 서버가 준비되면 `.env.local`의 `NEXT_PUBLIC_API_BASE_URL`만 실제 주소로 설정하면 됩니다.

연관 문서: [프로덕션 설계 문서](./PRODUCTION_DESIGN.md)

## 공통 규칙

- Base URL: `NEXT_PUBLIC_API_BASE_URL`
- API prefix: `/v1`
- Request/response: JSON
- 인증: `Authorization: Bearer <accessToken>`
- 시간 포맷: ISO 8601 권장. 현재 UI 표시용 상대 시간 문자열도 허용합니다.
- 에러 응답:

```json
{
  "message": "요청을 처리하지 못했습니다.",
  "code": "VALIDATION_ERROR",
  "details": {}
}
```

## 인증

### POST `/v1/auth/signup`

회원가입 후 바로 로그인된 세션을 반환합니다.

Request:

```json
{
  "email": "user@example.com",
  "password": "password123",
  "name": "홍길동"
}
```

Response:

```json
{
  "accessToken": "jwt-access-token",
  "refreshToken": "jwt-refresh-token",
  "expiresAt": "2026-06-09T00:00:00.000Z",
  "user": {
    "id": "usr_001",
    "email": "user@example.com",
    "name": "홍길동",
    "role": "user",
    "createdAt": "2026-06-08T00:00:00.000Z",
    "lastLoginAt": "2026-06-08T01:00:00.000Z"
  }
}
```

### POST `/v1/auth/login`

Request:

```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

Response: `POST /v1/auth/signup`과 동일한 `AuthSession`.

### GET `/v1/users/me`

로그인 사용자 정보를 반환합니다.

Headers: `Authorization: Bearer <accessToken>`

Response:

```json
{
  "id": "usr_001",
  "email": "user@example.com",
  "name": "홍길동",
  "role": "user"
}
```

### GET `/v1/users/me/dashboard`

계정별 저장 이슈, 제출 주장, 검증 요청 이력을 반환합니다.

Headers: `Authorization: Bearer <accessToken>`

Response:

```json
{
  "user": {
    "id": "usr_001",
    "email": "user@example.com",
    "name": "홍길동",
    "role": "user"
  },
  "savedIssues": [
    {
      "id": "issue_001",
      "title": "고영향 공공 이슈 A",
      "status": "검증 진행",
      "updatedAt": "3분 전"
    }
  ],
  "submittedClaims": [
    {
      "id": "claim_001",
      "issueTitle": "고영향 공공 이슈 A",
      "text": "일부 현장에서 절차가 지연되었다.",
      "status": "공식자료 연결",
      "submittedAt": "1시간 전"
    }
  ],
  "verificationRequests": [
    {
      "id": "vr_001",
      "articleUrl": "https://example.com/news/001",
      "status": "검증 진행",
      "requestedAt": "12분 전"
    }
  ]
}
```

### PATCH `/v1/users/me`

사용자 프로필을 수정합니다.

Headers: `Authorization: Bearer <accessToken>`

Request:

```json
{
  "name": "홍길동"
}
```

Response: `GET /v1/users/me`와 동일한 `AuthUser`.

### PUT `/v1/users/me/saved-issues/{issueId}`

이슈를 사용자 계정에 저장합니다.

Response:

```json
{
  "id": "issue_001",
  "status": "updated",
  "message": "이슈가 내 계정에 저장되었습니다."
}
```

### DELETE `/v1/users/me/saved-issues/{issueId}`

저장한 이슈를 해제합니다.

Response: `MutationResponse`.

### DELETE `/v1/users/me/submitted-claims/{claimId}`

사용자가 제출한 주장을 철회합니다.

Response: `MutationResponse`.

### DELETE `/v1/users/me/verification-requests/{requestId}`

사용자가 요청한 기사 검증 요청을 취소합니다.

Response: `MutationResponse`.

### GET `/v1/users/me/notifications`

알림 목록, 알림 설정, 팔로우한 이슈를 반환합니다.

Headers: `Authorization: Bearer <accessToken>`

Response:

```json
{
  "notifications": [
    {
      "id": "noti_001",
      "type": "수치 변경",
      "title": "공식 집계 기준이 변경되었습니다.",
      "issueTitle": "고영향 공공 이슈 A",
      "occurredAt": "5분 전",
      "read": false,
      "href": "/issues/issue_001"
    }
  ],
  "settings": {
    "officialSourceChanges": true,
    "numberChanges": true,
    "reviewCompleted": true,
    "timelineUpdates": true,
    "dailyDigest": false,
    "preferredPerspective": "균형"
  },
  "followedIssues": [
    {
      "id": "issue_001",
      "title": "고영향 공공 이슈 A",
      "status": "검증 진행",
      "updatedAt": "3분 전"
    }
  ]
}
```

### PATCH `/v1/users/me/preferences`

알림과 관심 관점 설정을 저장합니다.

Headers: `Authorization: Bearer <accessToken>`

Request:

```json
{
  "officialSourceChanges": true,
  "numberChanges": true,
  "reviewCompleted": true,
  "timelineUpdates": true,
  "dailyDigest": false,
  "preferredPerspective": "공식 자료 우선"
}
```

Response: `MutationResponse`.

### POST `/v1/users/me/device-tokens`

모바일 푸시 발송을 위한 디바이스 토큰을 저장합니다.

Request:

```json
{
  "platform": "expo",
  "token": "ExponentPushToken[example]"
}
```

Response: `MutationResponse`.

## 공개 웹

### GET `/v1/issues/home`

홈 화면에 필요한 이슈 목록, 선택 이슈 상세, 업데이트 로그를 한 번에 반환합니다.

Query:

- `topic`: 선택 토픽. 예: `정치`
- `issueId`: 선택 이슈 ID
- `q`: 검색어

Response:

```json
{
  "topics": ["전체", "정치", "사회", "경제", "국제", "재난", "보건"],
  "issues": [
    {
      "id": "issue_001",
      "title": "고영향 공공 이슈 A",
      "topic": "정치",
      "status": "검증 진행",
      "risk": "고영향",
      "updatedAt": "3분 전",
      "summary": "주요 수치, 원인 해석, 후속 요구의 근거가 서로 다른 주장으로 확산되고 있습니다.",
      "issueScore": 91,
      "articleCount": 126,
      "clusterCount": 18,
      "verifiedCount": 11,
      "needsReviewCount": 7,
      "changedClaims": 3
    }
  ],
  "selectedIssue": {
    "id": "issue_001",
    "title": "고영향 공공 이슈 A",
    "topic": "정치",
    "status": "검증 진행",
    "risk": "고영향",
    "updatedAt": "3분 전",
    "summary": "주요 수치, 원인 해석, 후속 요구의 근거가 서로 다른 주장으로 확산되고 있습니다.",
    "issueScore": 91,
    "articleCount": 126,
    "clusterCount": 18,
    "verifiedCount": 11,
    "needsReviewCount": 7,
    "changedClaims": 3,
    "confirmedFacts": [
      {
        "label": "확인",
        "text": "일부 현장에서 절차 지연 또는 수치 차이가 발생했습니다.",
        "verdict": "공식자료 확인",
        "tone": "positive"
      }
    ],
    "claimClusters": [
      {
        "title": "발생 범위",
        "question": "문제 발생 범위는 어느 기준으로 봐야 하는가?",
        "claims": ["14곳 초기 파악", "전국 50곳 후속 주장"],
        "conflict": "집계 기준과 발표 시점이 다릅니다.",
        "commonGround": "일부 현장 문제 발생 자체는 확인 가능합니다.",
        "verdict": "수치 충돌",
        "tone": "warning"
      }
    ],
    "claims": [
      {
        "text": "전국적으로 동일 문제가 대규모로 발생했다.",
        "type": "수치 주장",
        "verdict": "일부 사실",
        "tone": "warning",
        "confidence": 0.62,
        "evidence": "관련 기관 보고서 일부, 복수 언론 보도",
        "status": "후속 수치 확인 필요"
      }
    ],
    "evidences": [
      {
        "label": "최신 공식 기준",
        "source": "중앙선거관리위원회 설명자료",
        "date": "2024-04-11",
        "summary": "지역별 집계 기준과 후속 설명을 포함합니다.",
        "credibility": 0.94
      }
    ],
    "perspectives": [
      {
        "name": "관리 책임 강조",
        "core": "기관의 현장 관리 실패와 재발 방지 대책을 핵심 문제로 봅니다.",
        "uses": "현장 지연 보도, 기관 사과, 후속 조사 필요성",
        "challengedBy": "고의성 여부는 현재 자료만으로 단정하기 어렵습니다.",
        "commonGround": "절차 지연 발생 자체는 확인 가능한 사안입니다."
      }
    ]
  },
  "updateLogs": [
    {
      "time": "3분 전",
      "type": "공식 입장",
      "title": "관계 기관 추가 설명자료 발표",
      "description": "부족 발생 지역과 배부 기준에 대한 공식 설명이 추가되었습니다."
    }
  ]
}
```

### GET `/v1/issues/{issueId}`

이슈 상세페이지 데이터를 반환합니다. `selectedIssue`와 동일한 `IssueDetail`에 기사 비교, 타임라인, 원문 자료가 포함되어야 합니다.

Response:

```json
{
  "issue": {
    "id": "issue_001",
    "title": "고영향 공공 이슈 A",
    "topic": "정치",
    "status": "검증 진행",
    "risk": "고영향",
    "updatedAt": "3분 전",
    "summary": "주요 수치, 원인 해석, 후속 요구의 근거가 서로 다른 주장으로 확산되고 있습니다.",
    "issueScore": 91,
    "articleCount": 126,
    "clusterCount": 18,
    "verifiedCount": 11,
    "needsReviewCount": 7,
    "changedClaims": 3,
    "confirmedFacts": [],
    "claimClusters": [],
    "claims": [],
    "evidences": [],
    "perspectives": [],
    "articles": [
      {
        "id": "article-001",
        "title": "일부 현장 절차 지연으로 혼선",
        "outlet": "연합뉴스",
        "publishedAt": "06-08 08:21",
        "url": "https://example.com/news/article-001",
        "claimCount": 5,
        "outdatedClaims": 1,
        "officialSourceCount": 2,
        "verdict": "초기 기준",
        "tone": "warning",
        "note": "초기 발생 범위가 후속 공식자료와 다릅니다."
      }
    ],
    "timeline": [
      {
        "id": "timeline-001",
        "occurredAt": "06-08 07:58",
        "type": "현장 제보",
        "title": "일부 현장 절차 지연 제보 확산",
        "description": "현장 영상과 SNS 게시물이 먼저 확산됐습니다."
      }
    ],
    "sourceDocuments": [
      {
        "id": "source-001",
        "title": "현장 집계 기준 설명자료",
        "publisher": "중앙선거관리위원회",
        "publishedAt": "2026-06-08T10:05:00+09:00",
        "url": "https://example.com/source/nec-briefing",
        "sourceType": "official",
        "credibility": 0.94
      }
    ],
    "numberChanges": [
      {
        "id": "num-001",
        "label": "현장 수",
        "previousValue": "14곳",
        "currentValue": "50곳",
        "changedAt": "06-08 10:05",
        "source": "공식 설명자료",
        "note": "초기 보도 기준과 후속 집계 기준이 다릅니다.",
        "tone": "warning"
      }
    ]
  },
  "relatedIssues": []
}
```

### POST `/v1/verification-requests`

기사 URL 검증 요청을 생성합니다. 로그인 사용자는 Bearer 토큰을 포함합니다. 비로그인 요청을 허용할지는 서버 정책으로 결정합니다.

Request:

```json
{
  "articleUrl": "https://example.com/news/001",
  "issueId": "issue_001"
}
```

Response:

```json
{
  "id": "vr_001",
  "status": "queued",
  "matchedIssueId": "issue_001",
  "message": "검증 요청이 접수되었습니다."
}
```

### POST `/v1/issues/{issueId}/claims`

사용자가 구조화된 주장을 제출합니다.

Headers: `Authorization: Bearer <accessToken>` 권장

Request:

```json
{
  "issueId": "issue_001",
  "claimText": "일부 현장에서 절차가 지연되었다.",
  "reason": "후속 기사에서 제시한 지연 기준이 기존 발표와 다릅니다.",
  "evidenceUrl": "https://example.com/source",
  "relatedCluster": "현장 절차 지연",
  "claimType": "수치",
  "refutablePoint": "현장별 처리 시각과 공식 집계 기준이 확인되면 판정이 바뀔 수 있습니다."
}
```

Response:

```json
{
  "id": "claim_001",
  "status": "received",
  "clusterId": "cluster_001"
}
```

### POST `/v1/issues/{issueId}/report`

사용자가 이슈 리포트를 저장합니다. 서버 구현에 따라 PDF/공유 URL을 생성할 수 있습니다.

Headers: `Authorization: Bearer <accessToken>` 권장

Response:

```json
{
  "id": "report-issue_001",
  "issueId": "issue_001",
  "status": "created",
  "downloadUrl": "https://api.facttracer.example.com/reports/report-issue_001.pdf",
  "message": "이슈 리포트가 저장되었습니다."
}
```

## 팟캐스트

### GET `/v1/podcasts/home`

개인화, 데일리, 긴급, 특집, 최신, 랭킹, 카테고리별 팟캐스트 섹션과 현재 재생 후보를 반환합니다. 카테고리 섹션은 정치, 경제, 사회, 국제, 재난, IT/과학 등을 포함합니다.

### GET `/v1/podcasts`

팟캐스트 피드 목록을 반환합니다. `feed`, `topic`, `limit` 쿼리를 지원합니다. `feed`는 `recommended`, `personalized`, `daily`, `urgent`, `featured`, `latest`, `ranking`, `category`를 사용할 수 있습니다.

목록 카드에는 운영 검수를 위한 `ttsStatus`, `publicationGateStatus`, `publicationGateQualityScore`, `publicationGateMissingSignals`, `publicationGateWarnings`를 포함합니다.

`recommended`와 `personalized` 피드는 기존 이슈 랭킹 신호를 재사용하되 팟캐스트 전용 운영 가중치를 적용합니다. 기본 비로그인 추천은 사회적 영향도 0.35, 검증 필요도 0.25, 최신성 0.20, 논란도 0.10, 모멘텀 0.10 기준입니다. 개인화 추천은 공익성 기반 점수에 사용자 관심사 점수를 기본 0.35 비중으로 섞습니다.

### GET `/v1/podcasts/{episodeId}`

플레이어 상세 화면에 필요한 대사, 출처, 진행자, 다음 재생 목록을 반환합니다. 관리자 화면에서는 같은 응답의 `publicationGate`, `notationReview`, `correctionPolicy`, `variant`를 운영 검수에 사용합니다.

대사 세그먼트는 문장 단위 검수 메타데이터를 포함합니다.

- `sourceRefs`: 해당 대사를 뒷받침하는 출처 ID, 출처 유형, 매핑 사유
- `expressionReview`: 단정, 추정, 낙인 표현 패턴 검출 결과

`publicationGate.expressionFindings`는 회차 전체에서 발견된 위험 표현 세그먼트를 요약합니다.

### GET `/v1/podcasts/{episodeId}/audio`

OpenAI TTS로 렌더링된 팟캐스트 오디오 파일을 반환합니다.

### POST `/v1/podcasts/{episodeId}/render-audio`

관리자가 기존 회차의 스크립트를 OpenAI TTS로 다시 렌더링합니다.

### POST `/v1/podcasts/generate`

관리자가 기존 이슈 랭킹 기반으로 팟캐스트 회차를 자동 생성합니다. `issueId`를 넘기면 특정 이슈만 생성하고, `variant=short|standard|deep`으로 짧은 브리핑/표준 회차/심층 정리를 구분합니다. `renderAudio=true`이면 생성 직후 OpenAI TTS 오디오도 렌더링합니다.

## 관리자

관리자 API는 `role`이 `admin` 또는 `reviewer`인 사용자만 호출할 수 있어야 합니다.

### GET `/v1/admin/dashboard`

관리자 화면 전체 데이터를 반환합니다.

Headers: `Authorization: Bearer <accessToken>`

Response:

```json
{
  "metrics": [
    { "label": "대기 이슈", "value": "14" },
    { "label": "민감 검토", "value": "5" },
    { "label": "재검증", "value": "8" }
  ],
  "navItems": [
    { "label": "검토 큐", "value": "14" },
    { "label": "민감 이슈", "value": "5" }
  ],
  "queue": [
    {
      "id": "ISS-260608-001",
      "title": "고영향 공공 이슈 A",
      "topic": "공공",
      "articleCount": 126,
      "firstDetectedAt": "06-08 09:41",
      "status": "검토 대기",
      "priority": "높음",
      "reason": "고영향 이슈, 낙인 표현 신고 증가, 공식자료 갱신"
    }
  ],
  "selectedIssue": {
    "id": "ISS-260608-001",
    "title": "고영향 공공 이슈 A",
    "topic": "공공",
    "articleCount": 126,
    "firstDetectedAt": "06-08 09:41",
    "status": "검토 대기",
    "priority": "높음",
    "reason": "고영향 이슈, 낙인 표현 신고 증가, 공식자료 갱신"
  },
  "claims": [],
  "claimClusters": [],
  "evidences": [],
  "agentRuns": [
    {
      "agent": "News Watcher",
      "status": "completed",
      "target": "새 기사 4건 감지",
      "finishedAt": "10:14",
      "failureReason": ""
    }
  ]
}
```

### POST `/v1/admin/queue/sync`

관리자 검토 큐를 서버 기준으로 다시 동기화합니다.

Response:

```json
{
  "id": "admin-queue",
  "status": "queued",
  "message": "큐 동기화를 시작했습니다."
}
```

### GET `/v1/admin/podcasts`

관리자가 공개/초안/보관 상태를 포함해 팟캐스트 회차 목록을 조회합니다. `status`, `limit` 쿼리를 지원합니다.
관리 화면은 `status=draft` 결과로 출처 부족, 공식 출처 미확인, 표현 검수 경고 때문에 자동발행이 보류된 회차를 별도 표시합니다.

Response:

```json
{
  "episodes": [
    {
      "id": "podcast_001",
      "issueId": "issue_001",
      "issueTitle": "고영향 공공 이슈 A",
      "title": "특집 팟캐스트: 고영향 공공 이슈 A",
      "subtitle": "정치 · 영향도, 논란도, 최신성 종합",
      "category": "정치",
      "format": "panel_3",
      "durationSeconds": 120,
      "thumbnailUrl": null,
      "publishedAt": "2026-06-10T13:06:16+09:00",
      "rankScore": 94.2,
      "rankReason": "사회적 영향도와 확산 신호가 큼",
      "sourceCount": 6,
      "status": "published",
      "variant": "standard"
    }
  ]
}
```

### GET `/v1/admin/podcasts/{episodeId}`

관리자가 팟캐스트 대본, 진행자, 출처, 다음 재생 후보를 검토합니다. 공개되지 않은 회차도 조회할 수 있습니다. 상세 응답은 자동발행 품질 기준(`publicationGate`), 표기 후보(`notationReview`), 정정/후속 회차 정책(`correctionPolicy`)을 포함합니다.

### PATCH `/v1/admin/podcasts/{episodeId}/status`

관리자가 팟캐스트 상태를 변경합니다.

Request:

```json
{
  "status": "archived"
}
```

Response: `MutationResponse`.

### POST `/v1/admin/issues/{issueId}/approve`

검토 이슈를 공개 출고 승인합니다.

Response:

```json
{
  "id": "ISS-260608-001",
  "status": "updated",
  "message": "출고 승인되었습니다."
}
```

### POST `/v1/admin/issues/{issueId}/reverify`

선택 이슈의 재검증 작업을 실행합니다.

Request:

```json
{
  "priority": "high",
  "memo": "공식자료 기준 업데이트 후 판정 재계산"
}
```

### GET `/v1/admin/issues/{issueId}`

관리자 검토 상세 화면 데이터를 반환합니다.

Headers: `Authorization: Bearer <accessToken>`

Response:

```json
{
  "issue": {
    "id": "ISS-260608-001",
    "title": "고영향 공공 이슈 A",
    "topic": "공공",
    "articleCount": 126,
    "firstDetectedAt": "06-08 09:41",
    "status": "검토 대기",
    "priority": "높음",
    "reason": "고영향 이슈, 낙인 표현 신고 증가, 공식자료 갱신"
  },
  "publicIssue": {},
  "queue": [],
  "claims": [],
  "claimClusters": [],
  "evidences": [],
  "articles": [],
  "timeline": [],
  "reports": []
}
```

### GET `/v1/admin/issues/{issueId}/research-runs`

관리자 검토 상세에서 특정 이슈에 연결된 리서치 실행 기록을 반환합니다.

Response:

```json
{
  "items": [
    {
      "id": "research_001",
      "issueId": "issue_001",
      "roundIndex": 1,
      "triggerType": "manual",
      "status": "completed",
      "startedAt": "2026-06-10T09:00:00+09:00",
      "finishedAt": "2026-06-10T09:00:20+09:00",
      "durationMs": 20000,
      "seedQuery": "고영향 공공 이슈 A 공식자료",
      "executedQueries": [],
      "resultUrls": [],
      "selectedArticleIds": [],
      "sourceRoutes": [],
      "missingSignals": [],
      "plan": {},
      "errorMessage": null
    }
  ]
}
```

### GET `/v1/admin/reports`

관리자 신고 처리 목록을 반환합니다.

Response:

```json
{
  "reports": [
    {
      "id": "report-001",
      "issueId": "issue_001",
      "issueTitle": "고영향 공공 이슈 A",
      "targetType": "claim",
      "reason": "근거 없는 고의성 단정",
      "status": "open",
      "priority": "높음",
      "submittedAt": "06-08 11:22",
      "excerpt": "특정 세력이 의도적으로 문제를 만들었다."
    }
  ]
}
```

### POST `/v1/admin/reports/{reportId}/resolve`

신고를 처리하거나 기각합니다.

Request:

```json
{
  "status": "resolved"
}
```

Response: `MutationResponse`.

### GET `/v1/admin/sources`

출처 도메인 관리 목록을 반환합니다.

Response:

```json
{
  "sources": [
    {
      "id": "domain-001",
      "domain": "nec.go.kr",
      "name": "중앙선거관리위원회",
      "sourceType": "official",
      "credibility": 0.94,
      "status": "trusted",
      "isActive": true,
      "collectionUrl": "https://www.nec.go.kr/site/nec/ex/bbs/List.do",
      "collectionIntervalMinutes": 30,
      "lastCollectionStatus": "completed",
      "lastReviewedAt": "06-08 10:05",
      "note": "선거 관련 공식자료 1순위 출처"
    }
  ]
}
```

### POST `/v1/admin/sources`

수집 대상 출처를 등록합니다.

Request:

```json
{
  "domain": "nec.go.kr",
  "name": "중앙선거관리위원회",
  "sourceType": "official",
  "credibility": 0.94,
  "status": "trusted",
  "collectionUrl": "https://www.nec.go.kr/site/nec/ex/bbs/List.do",
  "collectionIntervalMinutes": 30,
  "isActive": true,
  "note": "선거 관련 공식자료 1순위 출처"
}
```

Response: 생성된 `SourceDomain`.

### PATCH `/v1/admin/sources/{domainId}`

출처 도메인과 수집 설정을 변경합니다. 일부 필드만 보내도 됩니다.

Request:

```json
{
  "domain": "nec.go.kr",
  "name": "중앙선거관리위원회",
  "sourceType": "official",
  "credibility": 0.94,
  "status": "watch",
  "collectionUrl": "https://www.nec.go.kr/site/nec/ex/bbs/List.do",
  "collectionIntervalMinutes": 30,
  "isActive": true,
  "note": "선거 관련 공식자료 1순위 출처"
}
```

Response: `MutationResponse`.

### GET `/v1/admin/settings`

관리자 화면에서 수정 가능한 운영 설정을 그룹 단위로 반환합니다. 민감키는 원문 값을 반환하지 않고 설정 여부만 반환합니다.

팟캐스트 운영 설정은 다음 키를 포함합니다.

- `podcast_min_publish_quality_score`: 자동발행 최소 품질 점수, 기본 70
- `podcast_sensitive_topics_require_official_source`: 민감 주제 공식 출처 요구, 기본 true
- `podcast_recommendation_impact_weight`
- `podcast_recommendation_verification_weight`
- `podcast_recommendation_freshness_weight`
- `podcast_recommendation_controversy_weight`
- `podcast_recommendation_momentum_weight`
- `podcast_personalization_interest_weight`

Response:

```json
{
  "groups": [
    {
      "id": "review",
      "label": "판정 기준",
      "description": "이슈 후보, 자동 공개, 주장 묶음 기준을 조정합니다.",
      "items": [
        {
          "key": "issue_candidate_threshold",
          "label": "이슈 후보 기준",
          "description": "새 이슈 후보로 올리는 최소 점수",
          "group": "review",
          "valueType": "integer",
          "value": 55,
          "defaultValue": 55,
          "options": [],
          "min": 0,
          "max": 100,
          "step": null,
          "unit": "점",
          "isSecret": false,
          "isRuntimeMutable": true,
          "configured": true,
          "source": "env",
          "updatedAt": null
        }
      ]
    }
  ],
  "updatedAt": "2026-06-08T00:00:00+00:00"
}
```

### PATCH `/v1/admin/settings`

운영 설정을 저장하거나 관리자 오버라이드를 초기화합니다.

Request:

```json
{
  "settings": [
    {
      "key": "issue_candidate_threshold",
      "value": 60
    },
    {
      "key": "openai_api_key",
      "value": "sk-..."
    },
    {
      "key": "rate_limit_per_minute",
      "reset": true
    }
  ]
}
```

Response: `GET /v1/admin/settings`와 동일한 `AdminSettingsResponse`.

### GET `/v1/admin/agents`

에이전트 실행 상태와 최근 이벤트를 반환합니다.

Response:

```json
{
  "agentRuns": [
    {
      "agent": "News Watcher",
      "status": "completed",
      "target": "새 기사 4건 감지",
      "finishedAt": "10:14",
      "failureReason": ""
    }
  ],
  "recentEvents": []
}
```

### POST `/v1/admin/agents/run`

에이전트를 수동 실행합니다.

Request:

```json
{
  "agent": "News Watcher"
}
```

Response: `MutationResponse`.

Response:

```json
{
  "id": "ISS-260608-001",
  "status": "queued",
  "message": "재검증 작업이 큐에 등록되었습니다."
}
```

## 확장 공개 API

### GET `/v1/issues/{issueId}/updates`

이슈별 업데이트 로그를 반환합니다.

Response:

```json
{
  "updates": []
}
```

### GET `/v1/issues/{issueId}/articles`

이슈에 연결된 기사 비교 데이터를 반환합니다.

Response:

```json
{
  "articles": []
}
```

### GET `/v1/issues/{issueId}/claim-clusters`

이슈의 주장 클러스터 목록을 반환합니다.

Response:

```json
{
  "claimClusters": []
}
```

### GET `/v1/issues/{issueId}/perspectives`

이슈의 관점 지도 데이터를 반환합니다.

Response:

```json
{
  "perspectives": []
}
```

### POST `/v1/issues/{issueId}/subscribe`

관심 이슈를 구독하고 알림 대상으로 등록합니다.

Response: `MutationResponse`.

### DELETE `/v1/issues/{issueId}/subscribe`

관심 이슈 구독을 해제합니다.

Response: `MutationResponse`.

### POST `/v1/issues/{issueId}/content-reports`

이슈 화면의 주장, 기사, 근거 등에 대한 사용자 신고를 등록합니다.

Request:

```json
{
  "targetType": "claim",
  "targetId": "claim_001",
  "reason": "근거가 부족합니다.",
  "excerpt": "문제가 되는 문장"
}
```

Response: `MutationResponse`.

### POST `/v1/issues/{issueId}/report`

이슈 리포트를 생성합니다.

Response:

```json
{
  "id": "report-issue_001",
  "issueId": "issue_001",
  "status": "created",
  "downloadUrl": "/v1/reports/report-issue_001/markdown",
  "message": "이슈 리포트가 저장되었습니다."
}
```

### GET `/v1/reports/{reportId}/markdown`

생성된 이슈 리포트를 Markdown 텍스트로 반환합니다.

Response: `text/markdown`.

### POST `/v1/analytics/events`

사용자 화면의 주요 이벤트를 서버 처리 기록으로 저장합니다.

Request:

```json
{
  "eventName": "issue_opened",
  "properties": {
    "issueId": "issue_001"
  }
}
```

Response: `MutationResponse`.

### POST `/v1/checks`

URL, 텍스트, YouTube, 이미지, PDF, 파일 입력을 검증 요청으로 등록합니다.

Request:

```json
{
  "inputType": "url",
  "content": "https://example.com/news/001",
  "issueId": "issue_001"
}
```

Response:

```json
{
  "id": "check_001",
  "status": "running",
  "inputType": "url",
  "matchedIssueId": "issue_001",
  "standaloneResultId": null,
  "message": "검증 요청이 접수되었습니다."
}
```

### GET `/v1/checks/{checkId}`

수동 검증 요청 상태를 반환합니다.

Response: `POST /v1/checks`와 동일한 `ManualCheckResponse`.

### POST `/v1/files`

이미지, PDF 등 검증 입력 파일 메타데이터를 등록합니다.

Request:

```json
{
  "filename": "source.pdf",
  "contentType": "application/pdf",
  "sizeBytes": 1024,
  "storageUrl": "https://storage.example.com/source.pdf",
  "contentBase64": null
}
```

Response:

```json
{
  "id": "file_001",
  "status": "received",
  "safetyStatus": "accepted",
  "message": "파일 검증 준비가 완료되었습니다."
}
```

## 확장 관리자 API

### GET `/v1/admin/issue-candidates`

자동 감지된 이슈 후보 목록을 반환합니다.

Response: `GET /v1/admin/dashboard`와 동일한 관리자 대시보드 형태.

### POST `/v1/admin/issue-candidates/{candidateId}/approve`

이슈 후보를 공개 이슈로 승인합니다.

Response: `MutationResponse`.

### POST `/v1/admin/issues/{issueId}/merge`

이슈를 다른 이슈로 병합합니다.

Request:

```json
{
  "targetIssueId": "issue_target"
}
```

Response: `MutationResponse`.

### POST `/v1/admin/issues/{issueId}/split`

기사 하나를 기준으로 새 이슈 후보를 분리합니다.

Request:

```json
{
  "articleId": "article_001",
  "title": "분리할 이슈명",
  "topic": "사회"
}
```

Response: `MutationResponse`.

### POST `/v1/admin/issues/{issueId}/hide`

이슈를 공개 목록에서 숨김 처리합니다.

Response: `MutationResponse`.

### POST `/v1/admin/issues/{issueId}/representative-image`

이슈 대표 이미지를 수동 지정합니다.

Response: `MutationResponse`.

### PATCH `/v1/admin/sources/{sourceId}/credibility`

출처 신뢰도와 수집 정책을 수정합니다.

Request:

```json
{
  "status": "trusted",
  "credibility": 0.94,
  "collectionIntervalMinutes": 10
}
```

Response: `MutationResponse`.

### POST `/v1/admin/collectors/run`

등록된 수집원을 즉시 실행합니다.

Request:

```json
{
  "sourceIds": ["domain-001"]
}
```

Response:

```json
{
  "id": "collectors",
  "status": "completed",
  "message": "수집 작업을 실행했습니다.",
  "result": {}
}
```

### GET `/v1/admin/collectors/runs`

수집 작업 실행 이력을 반환합니다.

Response:

```json
{
  "runs": []
}
```

### GET `/v1/admin/search-keywords`

검색 기반 자동 수집 키워드 목록과 마지막 수집 상태를 반환합니다.

Response:

```json
{
  "keywords": []
}
```

### GET `/v1/admin/discovery-topics`

상위 감시 주제와 discovery 실행 상태를 반환합니다.

Response:

```json
{
  "topics": []
}
```

### POST `/v1/admin/discovery-topics`

상위 감시 주제를 등록하고 필요하면 즉시 사건 discovery를 실행합니다.

Request:

```json
{
  "name": "선거 감시",
  "topic": "정치",
  "baseQueries": ["선관위", "투표소"],
  "priority": "high",
  "intervalMinutes": 60,
  "maxResultsPerQuery": 12,
  "minClusterSize": 2,
  "runImmediately": true
}
```

Response: `GET /v1/admin/discovery-topics`와 동일한 `DiscoveryTopicsResponse`.

### POST `/v1/admin/discovery-topics/{topicId}/run`

특정 감시 주제의 broad 검색, 기사 클러스터링, 사건 정의, 키워드 확장을 즉시 실행합니다.

Response: `CollectorRunResponse`.

### GET `/v1/admin/discovered-incidents`

검색 discovery로 정의된 사건 후보와 연결된 이슈/키워드/기사 신호를 반환합니다.

Response:

```json
{
  "incidents": []
}
```

### POST `/v1/admin/search-keywords/seed`

사건명에서 검색 키워드를 생성하고 필요하면 즉시 검색 수집을 실행합니다.

Request:

```json
{
  "query": "선관위 투표용지 부족 사태",
  "topic": "정치",
  "priority": "high",
  "intervalMinutes": 30,
  "generateVariants": true,
  "runImmediately": true
}
```

Response: `GET /v1/admin/search-keywords`와 동일한 `SearchKeywordsResponse`.

### POST `/v1/admin/search-keywords/{keywordId}/run`

특정 검색 키워드의 뉴스 검색 수집을 즉시 실행합니다.

Response: `CollectorRunResponse`.

### POST `/v1/admin/issues/source-backfill/run`

출처 부족 이슈 보강과 활성 이슈 후속 추적 검색을 즉시 실행합니다.

Response: `CollectorRunResponse`.

### GET `/v1/admin/scheduler`

내장 스케줄러 heartbeat, lock, 최근 tick 결과를 반환합니다.

Response:

```json
{
  "id": "default",
  "ownerId": "embedded:1234",
  "status": "idle",
  "lockedUntil": null,
  "lastHeartbeatAt": null,
  "lastTickStartedAt": null,
  "lastTickFinishedAt": null,
  "tickCount": 0,
  "lastTick": {},
  "errorMessage": ""
}
```

### POST `/v1/admin/scheduler/tick`

검색 키워드와 등록 수집원의 due 작업을 한 번 스케줄링하고 실행합니다.

Response: `GET /v1/admin/scheduler`와 동일한 `SchedulerStatusResponse`.

### GET `/v1/admin/jobs`

비동기 작업과 재시도 상태를 반환합니다.

팟캐스트 생성/렌더링 실패 작업은 `lastError`와 함께 운영자용 요약 문장 `userMessage`를 포함합니다.

Response:

```json
{
  "jobs": [
    {
      "id": "job_001",
      "jobType": "render_podcast_audio",
      "targetId": "podcast_001",
      "status": "failed",
      "attempts": 1,
      "maxAttempts": 3,
      "lastError": "invalid_api_key",
      "userMessage": "OpenAI TTS 연결 키 또는 모델 설정을 확인해야 합니다.",
      "createdAt": "2026-06-11T00:00:00+00:00",
      "updatedAt": "2026-06-11T00:01:00+00:00"
    }
  ]
}
```

### POST `/v1/admin/jobs/{jobId}/retry`

실패한 작업을 재시도 큐에 넣습니다.

Response: `MutationResponse`.

### GET `/metrics`

운영 모니터링용 Prometheus 텍스트 포맷 지표를 반환합니다. 팟캐스트 관련 지표는 다음을 포함합니다.

- `facttracer_podcast_draft_episodes`
- `facttracer_podcast_jobs_failed`
- `facttracer_podcast_tts_pending`

### POST `/v1/admin/claims/{claimId}/reverify`

특정 주장을 다시 검증합니다.

Response: `MutationResponse`.

## 프론트 연결 위치

- API URL 설정: `src/lib/api/config.ts`
- 공통 HTTP 클라이언트: `src/lib/api/http.ts`
- 공개/관리자 서비스: `src/lib/api/facttracer.ts`
- 인증/유저 서비스: `src/lib/api/auth.ts`
- 타입 계약: `src/lib/api/types.ts`
- API 미설정 처리: 조회 화면은 빈 상태를 표시하고, 생성/수정/삭제 액션은 설정 오류를 반환합니다.

`NEXT_PUBLIC_API_BASE_URL`이 비어 있으면 프론트는 로컬 내장 데이터를 표시하지 않습니다. 서버 주소를 설정하면 위 서비스 함수들이 실제 API로 요청합니다.
