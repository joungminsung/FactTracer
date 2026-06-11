# FactTracer Podcast Frontend Design

작성일: 2026-06-10  
대상 앱: `facttracer-next`  
연동 백엔드: `facttracer-backend` podcast API

## 1. 목적

FactTracer 팟캐스트는 뉴스 기사 안에 딸린 보조 기능이 아니라, 별도 탐색/재생 경험을 가진 오디오 정보 서비스다. 목적은 기존 서비스와 동일하게 **국민의 알 권리**이며, 사용자는 관심 이슈를 음악 서비스처럼 고르되 내용은 검증 플랫폼답게 대사, 출처, 다음 재생, 확인 상태를 함께 본다.

프론트 1차 목표:

- `/podcasts`에 팟캐스트 탐색 페이지를 만든다.
- 팟캐스트 선택 시 하단 미니 플레이어가 나타난다.
- 미니 플레이어를 펼치면 화면 전체에 가까운 플레이어 시트가 올라온다.
- 플레이어 시트는 대사, 출처, 다음 재생 목록, 재생 설정을 포함한다.
- 실제 오디오는 `GET /v1/podcasts/{episodeId}/audio`를 재생한다.
- 디자인은 YouTube Music을 복제하지 않고, FactTracer v2의 라이트/뉴스 제품 정서에 맞춘다.

## 2. 제품 원칙

### Design Thesis

이 인터페이스는 **뉴스 편집 데스크 위에 놓인 오디오 플레이어**처럼 느껴져야 한다. FactTracer는 사건을 검증 가능한 단위로 분해하는 서비스이므로, 팟캐스트 UI는 음악 앱의 탐색성을 빌리되 신뢰, 출처, 대사 가독성, 다음 확인 흐름을 더 강하게 보여줘야 한다.

### 피해야 할 방향

- 다크 그라데이션 음악 앱 클론
- 과한 앨범아트 중심 UI
- 카드가 중첩된 SaaS 대시보드
- 팟캐스트를 기사 상세 내부 탭으로 넣는 구조
- 출처/대사 없이 재생 버튼만 있는 오디오 목록

### FactTracer v2 규칙 적용

- 기본 배경은 `bg-white`.
- 색은 `gray`, 선택/링크는 `blue-600`.
- 상태는 pill badge가 아니라 dot + 텍스트.
- 섹션 구분은 border보다 여백 우선.
- 큰 장식보다 타이포 위계, 목록 밀도, 출처 가시성을 우선한다.

## 3. 정보 구조

### 신규 공개 라우트

```txt
/podcasts
```

역할:

- 사용자가 팟캐스트를 고르는 첫 화면.
- 백엔드 `GET /v1/podcasts/home` 응답의 sections를 렌더링.
- URL query로 특정 회차를 열 수 있게 한다.

예상 query:

```txt
/podcasts?episode=podcast_abc
/podcasts?feed=latest
/podcasts?topic=정치
```

초기 구현은 `/podcasts` 단일 페이지와 클라이언트 플레이어 상태로 충분하다. 상세를 별도 page route로 만들지 않는다. 필요하면 추후 공유 링크용 `/podcasts/[episodeId]`를 추가한다.

### 헤더 내비게이션

`SiteHeader`의 주요 nav에 `팟캐스트`를 추가한다.

권장 위치:

```txt
정치 · 사회 · 경제 · 국제 · 재난/환경 · 과학/기술 · 라이프 · 팟캐스트 · 제보/검증
```

이유:

- 팟캐스트는 기사/이슈와 같은 공개 소비면이다.
- 운영 콘솔이나 계정 기능이 아니다.

## 4. API 계약

백엔드가 이미 제공하는 API:

```txt
GET  /v1/podcasts/home
GET  /v1/podcasts?feed=&topic=&limit=
GET  /v1/podcasts/{episodeId}
GET  /v1/podcasts/{episodeId}/audio
POST /v1/podcasts/{episodeId}/render-audio
POST /v1/podcasts/generate
```

프론트에서 필요한 타입:

```ts
type PodcastEpisodeCard = {
  id: string;
  issueId?: string | null;
  issueTitle?: string | null;
  title: string;
  subtitle: string;
  category: string;
  format: "solo" | "panel_2" | "panel_3" | string;
  durationSeconds: number;
  thumbnailUrl?: string | null;
  publishedAt: string;
  rankScore?: number | null;
  rankReason?: string | null;
  sourceCount: number;
  status: string;
};

type PodcastEpisodeDetail = PodcastEpisodeCard & {
  summary: string;
  hosts: PodcastHost[];
  script: PodcastScriptSegment[];
  sources: PodcastSource[];
  audioUrl?: string | null;
  ttsStatus: string;
  autoPublished: boolean;
  playback: Record<string, unknown>;
};

type PodcastHomeResponse = {
  sections: PodcastSection[];
  nowPlaying: PodcastEpisodeCard | null;
};
```

`audioUrl`은 상대 경로(`/v1/podcasts/{episodeId}/audio`)일 수 있으므로 프론트에서는 `buildApiUrl` 또는 audio 전용 helper로 API base URL을 붙여야 한다.

## 5. 데이터 흐름

### 페이지 로드

1. 서버 컴포넌트 `/podcasts/page.tsx`에서 `getPodcastHome(token)` 호출.
2. API 미설정 또는 실패 시 empty home 구조 반환.
3. `PodcastHomeClient`에 home data 전달.
4. 사용자가 episode card를 누르면 detail fetch.

### 회차 선택

1. `PodcastEpisodeCard` 클릭.
2. `GET /v1/podcasts/{episodeId}` 호출.
3. `PodcastPlayerProvider`가 selected detail 저장.
4. 하단 `PodcastMiniPlayer` 표시.
5. `<audio>`의 `src`는 `episode.audioUrl`을 API base URL로 변환한 값.

### 플레이어 확장

1. 미니 플레이어의 확장 버튼 클릭.
2. `PodcastPlayerSheet`가 `fixed inset-x-0 bottom-0 top-0`에 가까운 sheet로 표시.
3. sheet 내부에서 transcript/source/queue 탭 또는 2-column 레이아웃 표시.
4. 닫으면 mini player만 유지.

### 다음 재생

1. detail 응답의 `nextQueue`를 우선 사용.
2. 사용자가 다음 버튼을 누르면 queue[0] detail fetch 후 재생.
3. queue가 비어 있으면 현재 feed의 다음 항목을 `GET /v1/podcasts?feed=recommended&limit=12`로 보강.

## 6. 화면 설계

### `/podcasts` 페이지

상단 구조:

- `SiteHeader`
- 페이지 타이틀: `팟캐스트`
- 설명: “검증된 이슈를 대사와 출처가 있는 오디오로 정리합니다.”
- 우측 또는 하단 작은 필터: 전체, 특집, 맞춤, 최신, 랭킹, 정치, 경제, 국제, 재난

본문:

- 첫 섹션: 개인화 추천
  - 로그인 사용자: `{name}님만을 위한 오늘의 팟캐스트`
  - 비로그인: `오늘의 추천 팟캐스트`
- 다음 섹션: 특집 팟캐스트
- 다음 섹션: 최신 회차
- 다음 섹션: 많이 확인하는 이슈
- 카테고리 섹션: 정치, 경제 등

섹션 디자인:

- 카드 그리드보다 “뉴스 목록 + 가로 레일” 혼합.
- 대표 카드 1개는 넓게, 나머지는 compact row.
- `thumbnailUrl`이 있으면 사용하고, 없으면 주제별 neutral placeholder를 사용한다.
- 카드에는 반드시 `sourceCount`, `format`, `durationSeconds`, `rankReason` 중 2개 이상을 보여준다.

### 하단 미니 플레이어

위치:

```txt
fixed inset-x-0 bottom-0 z-40 border-t border-gray-200 bg-white
```

구성:

- 좌측: 재생/일시정지 icon button
- 중앙: 제목, 카테고리, 진행 시간
- 우측: 다음, 속도, 확장 버튼
- 진행률 bar는 상단 2px 또는 내부 slider

디자인:

- YouTube Music처럼 아래에서 올라오는 구조만 참고.
- 다크 바 금지.
- shadow는 최소화하고 border로 구분.
- 모바일에서는 제목 1줄 clamp, 제어 버튼 3개만 노출.

### 플레이어 시트

열림 상태:

```txt
fixed inset-x-0 bottom-0 z-50 h-[calc(100dvh-0px)] bg-white
```

데스크톱 레이아웃:

- 좌측 55%: 회차 제목, 요약, 진행자, 큰 재생 제어, 대사
- 우측 45%: 다음 재생, 출처, 관련 이슈 링크

모바일 레이아웃:

- 상단: 닫기/축소, 제목
- 중단: 재생 제어
- 하단: tabs
  - 대사
  - 다음 재생
  - 출처

대사 UI:

- `script`를 speaker별로 행 렌더링.
- 현재 재생 위치가 `startsAt`을 넘으면 active row 표시.
- active row는 `bg-gray-50` + 좌측 `border-l-2 border-blue-600`.
- speaker name과 role은 small meta.
- 대사는 `text-[15px] leading-7`.

출처 UI:

- 원문 링크, publisher, sourceType, credibility 표시.
- “출처 없음” 상태는 미확인으로 표시.
- 출처는 별도 카드가 아니라 row/list 형식.

다음 재생 UI:

- episode title
- format
- duration
- source count
- 현재 회차와 같은 항목은 제외.

## 7. 컴포넌트 설계

권장 파일 구조:

```txt
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
src/lib/api/podcasts.ts
```

### Server component

`src/app/podcasts/page.tsx`

- `getServerAccessToken()` 호출.
- `getPodcastHome({ token })` 호출.
- 실패 시 empty state 전달.
- 직접 audio control 상태를 갖지 않는다.

### Client provider

`PodcastPlayerProvider`

상태:

```ts
selectedEpisode: PodcastEpisodeDetail | null
queue: PodcastEpisodeCard[]
isExpanded: boolean
isPlaying: boolean
currentTime: number
duration: number
playbackRate: number
error: string | null
```

책임:

- detail fetch
- audio element 제어
- 재생/일시정지/seek/next/speed
- mini player와 sheet에 context 제공

### API layer

`src/lib/api/podcasts.ts`

함수:

```ts
getPodcastHome({ token })
getPodcastFeed({ feed, topic, limit, token })
getPodcastDetail(episodeId, token?)
buildPodcastAudioUrl(audioUrl)
```

API 미설정 fallback:

```ts
const emptyPodcastHome = {
  nowPlaying: null,
  sections: [],
};
```

## 8. 상태와 에러 처리

### API 미설정

`NEXT_PUBLIC_API_BASE_URL`이 없으면 `/podcasts`는 빈 상태를 보여준다.

문구:

```txt
팟캐스트를 준비 중입니다.
검증된 이슈가 생성되면 자동으로 오디오 회차가 표시됩니다.
```

### 오디오 없음

`audioUrl`이 없거나 `ttsStatus !== completed`이면:

- 재생 버튼 비활성
- 대사는 표시
- 문구: `오디오 생성 대기 중`
- 운영자용 렌더링 버튼은 공개 화면에 두지 않는다.

### 재생 실패

- audio `error` 이벤트에서 사용자 메시지 표시.
- message: `오디오를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.`
- 대사와 출처는 계속 표시.

### 상세 fetch 실패

- mini player를 열지 않는다.
- 카드 근처 또는 페이지 상단에 짧은 오류 메시지.
- 기존 페이지 전체를 깨뜨리지 않는다.

## 9. 접근성

- 모든 icon button에 `aria-label`.
- 미니 플레이어와 sheet는 keyboard focus 가능.
- sheet 열림 시 닫기 버튼으로 focus 이동.
- `Escape`로 sheet 축소.
- transcript active row에 `aria-current="true"`.
- audio control은 커스텀 UI와 `<audio>` 상태가 어긋나지 않게 동기화.

## 10. 반응형 기준

### Desktop

- 본문 max width는 기존 홈과 같은 `max-w-[1520px]`.
- 섹션은 1개의 large lead + 3~5개 compact item.
- player sheet는 2-column.

### Tablet

- 섹션은 2-column.
- sheet는 상단 제어 + transcript/queue stack.

### Mobile

- 섹션은 vertical list.
- mini player 높이는 72~84px.
- sheet는 full height.
- 하단 safe area 고려: `pb-[env(safe-area-inset-bottom)]`.

## 11. 구현 순서

1. API 타입 추가
   - `PodcastEpisodeCard`
   - `PodcastEpisodeDetail`
   - `PodcastHomeResponse`
   - `PodcastDetailResponse`
2. API 함수 추가
   - `getPodcastHome`
   - `getPodcastFeed`
   - `getPodcastDetail`
   - `buildPodcastAudioUrl`
3. `/podcasts` page 추가
4. 탐색 UI 구현
   - section
   - episode card
   - empty state
5. player provider 추가
6. mini player 추가
7. player sheet 추가
   - transcript
   - queue
   - sources
8. header nav에 `팟캐스트` 추가
9. 테스트/검증

## 12. 테스트 계획

### Unit/API

가능하면 API helper 단위 테스트:

- API 미설정 시 empty home 반환
- audioUrl이 상대 경로일 때 API base URL로 변환
- feed/topic/limit query 생성

현재 프로젝트에 테스트 러너가 없다면 최소 `npm run lint`, `npm run build`를 gate로 둔다.

### UI 수동 검증

필수 확인:

- `/podcasts`가 빈 API 상태에서도 깨지지 않는다.
- 회차 클릭 시 mini player가 뜬다.
- mini player 확장 시 sheet가 화면을 채운다.
- 오디오 재생/일시정지/seek가 동작한다.
- `nextQueue` 항목 클릭 시 회차가 바뀐다.
- transcript active row가 현재 시간에 따라 바뀐다.
- 모바일 390px 폭에서 텍스트가 버튼 밖으로 넘치지 않는다.
- 기존 `/`, `/issues/[issueId]`, `/admin` 화면에 영향이 없다.

### Browser QA

Playwright 또는 브라우저 확인 대상:

```txt
desktop: 1440x900
tablet: 768x1024
mobile: 390x844
```

확인 항목:

- body horizontal overflow 없음
- fixed mini player가 콘텐츠를 가리지 않도록 bottom padding 적용
- sheet 열림/닫힘 시 layout shift 과도하지 않음
- audio controls와 transcript가 동시에 보임

## 13. 수용 기준

프론트 1차 완료 조건:

- `/podcasts` 페이지가 존재한다.
- 백엔드 `GET /v1/podcasts/home` 데이터를 렌더링한다.
- 회차 선택 시 `GET /v1/podcasts/{episodeId}`를 호출한다.
- 실제 `<audio>`가 `GET /v1/podcasts/{episodeId}/audio`를 재생한다.
- 하단 미니 플레이어와 확장 플레이어 시트가 동작한다.
- 대사, 다음 재생, 출처가 player sheet에 표시된다.
- API 미설정/오디오 미생성/재생 실패 상태가 깨지지 않는다.
- `npm run lint`와 `npm run build`가 통과한다.

## 14. 후속 단계

1차 이후 고려:

- `/podcasts/[episodeId]` 공유 링크 페이지
- 재생 이력 기반 개인화 이벤트 전송
- 이어 듣기 저장
- 앱 푸시/데일리 digest와 팟캐스트 연결
- 운영 콘솔에서 특정 이슈의 팟캐스트 수동 생성/재렌더링 UI
- 실제 오디오 waveform 또는 chapter marker 표시
