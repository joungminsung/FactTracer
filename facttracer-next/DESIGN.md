# FactTracer Design System v2

이 문서는 FactTracer UI 구현의 기준이다. 새 화면, 컴포넌트, 스타일 변경은 먼저 이 문서를 확인하고 진행한다.

v2는 기존 "사건 기록대/원장" 컨셉을 폐기하고, 주요 뉴스 미디어와 빅테크 제품 수준의 절제된 UI로 방향을 전환한 버전이다. 충돌 시 이 문서가 기존 코드보다 우선한다.

## 0. Why v2 — 기존 디자인의 문제 진단

v1이 "AI가 만든 화면"처럼 보였던 구체적 원인. 아래 패턴이 다시 나타나면 회귀로 간주한다.

| v1 패턴 | 왜 문제인가 | v2 대체 |
| --- | --- | --- |
| `font-black` 남발 | 모든 게 비명을 지르면 위계가 사라진다. AI 생성 UI의 대표 신호 | `font-semibold` 기본, `font-bold`는 헤드라인만 |
| 모든 섹션을 hairline border로 구분 | "신문 흉내" 템플릿 룩. 화면이 격자 감옥이 된다 | 여백으로 구분, border는 표와 입력에만 |
| 배경 tint 4종 (`#f5f7f2`, `#fbfcf8`, `#f8faf6`, `#eef4ff`) | 미세하게 다른 색조가 화면을 탁하게 만든다 | white 단일 배경 + gray-50 하나 |
| badge 3개 연속 (topic + risk + status) | 알록달록한 pill 나열은 대시보드 템플릿의 전형 | 상태 1개만 dot + 텍스트로, 나머지는 평문 메타 |
| dark rail + cyan 액센트 | 근거 없는 다크 패널은 "해커 대시보드" 클리셰 | 다크 surface 전면 제거, 전부 라이트 |
| square corner 도그마 | "서류 느낌" 컨셉 장식. 실사용 제품은 이렇게 안 만든다 | 8px(`rounded-lg`) 표준 |
| emerald/rose/amber tint 박스 남발 | 색 박스가 많을수록 어떤 것도 중요해 보이지 않는다 | 시맨틱 컬러는 점·텍스트·얇은 액센트로만 |

한 줄 요약: **v1은 "정보가 많아 보이는 것"을 디자인했고, v2는 "정보가 잘 읽히는 것"을 디자인한다.**

## 1. Design Thesis

FactTracer는 사건, 주장, 쟁점, 근거를 분해해 추적하는 검증 플랫폼이다.

v2의 인터페이스 기준은 신뢰받는 뉴스 제품(NYT, Reuters의 제품 화면)과 빅테크 제품(Google, Stripe, Linear)이 공유하는 원칙이다:

1. **타이포그래피가 디자인이다.** 위계는 크기·굵기·색의 대비로 만들고, 박스·배지·테두리로 만들지 않는다.
2. **여백이 구조다.** 섹션은 선이 아니라 거리로 구분한다.
3. **색은 침묵이 기본이다.** 화면의 95%는 무채색이고, 색은 상태와 행동에만 쓴다.
4. **신뢰는 절제에서 온다.** 장식이 적을수록 데이터가 진지해 보인다.

판단 기준: 이 화면을 캡처해서 Reuters 제품팀 리뷰에 올렸을 때 이질감이 없어야 한다.

## 2. Foundations

### Font

- 기본 폰트: **Pretendard** (한글 최적화, 국내 테크 제품 표준). `font-family: Pretendard, -apple-system, ...` 폴백.
- 숫자가 정렬되는 위치(metric, 테이블)는 `font-variant-numeric: tabular-nums`.
- 한 제품에 폰트는 1개. 디스플레이용 별도 폰트를 추가하지 않는다.

### Color

배경은 white 하나다. 화면 분위기는 텍스트 회색 단계로만 만든다.

| Role | Token | Usage |
| --- | --- | --- |
| Background | `bg-white` | 모든 화면 기본 |
| Surface (보조) | `bg-gray-50` | hover, 테이블 헤더, 코드/인용 배경. 유일하게 허용되는 보조 배경 |
| Heading / primary | `text-gray-900` | 제목, 핵심 수치 |
| Body | `text-gray-700` | 본문 |
| Secondary | `text-gray-500` | 메타, 시간, 단위 |
| Disabled / faint | `text-gray-400` | 비활성, placeholder |
| Border | `border-gray-200` | 표, 입력, 구분이 꼭 필요한 곳 |
| Accent (단일) | `blue-600` | 링크, primary 버튼, 선택 상태, focus. 브랜드 액센트는 이것 하나 |
| Verified / 사실 | `emerald-600` | 텍스트와 dot에만 |
| Conflict / 반박 | `red-600` | 텍스트와 dot에만 |
| Watch / 주의 | `amber-600` | 텍스트와 dot에만 |
| Pending / 중립 | `gray-400` | 텍스트와 dot에만 |

Rules:

- **시맨틱 컬러(emerald/red/amber)는 배경으로 쓰지 않는다.** `bg-emerald-50` 같은 tint 박스 금지. 상태는 `●` dot(2~2.5px radius 원) + 텍스트로 표현한다.
- 예외 1개: 페이지 상단의 중요 알림 1곳에만 `bg-amber-50` 류의 알림 배너 허용.
- slate 계열은 v2에서 gray로 통일한다.
- 새 색이 필요하면 이 표에 추가한 뒤 사용한다. arbitrary hex 금지.

### Typography Scale

| Role | Class |
| --- | --- |
| Issue title (상세 H1) | `text-3xl sm:text-4xl font-bold tracking-tight text-gray-900` |
| Page title | `text-2xl font-bold tracking-tight` |
| Section title | `text-lg font-semibold` |
| Eyebrow (섹션 위 소제목) | `text-xs font-medium uppercase tracking-wide text-gray-500` |
| Body | `text-[15px] leading-7 text-gray-700` |
| Small / meta | `text-sm text-gray-500` |
| Caption | `text-xs text-gray-500` |
| Metric number | `text-2xl font-semibold tabular-nums` |

Rules:

- `font-black` 사용 금지. 굵기는 `medium / semibold / bold` 3단계.
- `tracking-tight`는 `text-2xl` 이상에만, `tracking-wide`는 eyebrow에만.
- 본문 컬럼은 `max-w-[680px]`을 넘기지 않는다. 긴 한국어 본문의 가독 한계다.
- 긴 한국어 제목은 `break-keep` 전제. viewport 단위로 글자 크기를 스케일하지 않는다.

### Spacing & Shape

- 간격은 4px 그리드. 섹션 사이 `py-10` ~ `py-14`, 패널 내부 `p-5` ~ `p-6`, 리스트 행 `py-4`.
- Radius 표준: `rounded-lg`(8px). 입력·버튼은 `rounded-md`(6px) 허용. `rounded-xl` 이상, `rounded-full`은 dot/avatar에만.
- Shadow: 기본 없음. 떠 있는 요소(dropdown, modal)에만 `shadow-lg`. 카드에 shadow를 주지 않는다.
- **섹션 구분은 여백이 기본이다.** `border-t`로 섹션을 나누는 패턴은 페이지당 최대 1곳(footer 위)만 허용.

## 3. Status Vocabulary (Single Source of Truth)

상태 용어는 이 표가 유일한 기준이다. 화면별 동의어를 만들지 않는다.

### Issue status

| 상태 | 의미 | Dot 색 |
| --- | --- | --- |
| 수집 중 | 사건 감지됨, 기사 수집 진행 | gray-400 |
| 검토 중 | 쟁점 분해·검증 진행 | amber-600 |
| 확인됨 | 핵심 팩트 검증 완료 | emerald-600 |
| 충돌 | 주요 주장 간 미해소 충돌 | red-600 |
| 최신화 필요 | 새 기사/변경으로 재검토 필요 | amber-600 |
| 보류 | 근거 부족으로 판정 유보 | gray-400 |

### Claim verdict

| 판정 | Dot 색 |
| --- | --- |
| 사실 | emerald-600 |
| 반박됨 | red-600 |
| 부분 사실 | amber-600 |
| 미확인 | gray-400 |

표현 형식 (badge pill 아님):

```tsx
<span className="inline-flex items-center gap-1.5 text-sm text-gray-700">
  <span className="h-1.5 w-1.5 rounded-full bg-emerald-600" />
  확인됨
</span>
```

Rules:

- 판정은 항상 "판정 + 확인 시점"을 함께 표기한다.
- "완료", "처리됨" 같은 모호한 상태어 금지. 무엇이 완료인지 명시한다.
- 새 상태는 이 표에 먼저 추가한다.

## 4. Time & Number Formatting

시점은 세 종류를 구분한다: **발생**(사건 시점), **보도**(기사 발행), **확인**(검증 시점).

- 어떤 시점인지 label 없이 날짜만 단독 표기하지 않는다. `확인 2026.06.08` 형태.
- 포맷: `YYYY.MM.DD`, 시각 필요 시 `YYYY.MM.DD HH:mm` (24시간, KST).
- 상대 시간("3시간 전")은 목록의 업데이트 표시에만 허용. 판정·타임라인은 절대 시각.
- 숫자는 천 단위 구분자 + `tabular-nums`. 0은 숨기지 않는다. 수집 전이면 `—` + 상태 텍스트.

## 5. Layout System

### Global

- 콘텐츠 최대 폭 `max-w-screen-xl mx-auto px-4 sm:px-6 lg:px-8`.
- 상단 헤더: `h-14`, white 배경, `border-b border-gray-200`, sticky + `backdrop-blur` 허용. 다크 헤더 금지.
- 내비게이션은 텍스트 링크. 활성 항목은 `text-gray-900 font-medium`, 비활성은 `text-gray-500`.

### Public Home — 이슈 모니터

- 데스크톱: 좌측 이슈 목록(`xl:grid-cols-[400px_minmax(0,1fr)]`), 우측 선택 이슈 요약. 두 pane 사이는 `gap-10` 여백으로 구분, 세로 구분선 없음.
- 목록 row 구성: 상태 dot + 제목(`font-medium text-gray-900`) + 메타 한 줄(`text-sm text-gray-500`: 토픽 · 업데이트 시각 · 기사 N). **badge pill을 나열하지 않는다.** 토픽·위험도는 평문 메타다.
- 선택 row: `bg-gray-50` + 좌측 `border-l-2 border-blue-600`. 진한 파란 배경 금지.
- row 사이는 `divide-y divide-gray-100` 허용 (리스트는 border 허용 대상).

### Issue Detail — 사건 페이지

뉴스 기사 페이지의 정보 구조를 따르되, 본문은 검증 데이터다.

위에서 아래로:

1. **Header**: eyebrow(분야 · 상태 dot+텍스트 · 확인 시점) → 이슈 제목(H1) → 요약 1~2문장(`text-lg text-gray-600 leading-8`) → metric 한 줄.
2. **Key facts**: 확인된 사실 리스트. 박스 없이 dot + 텍스트 행.
3. **본문 섹션들**: 쟁점 지도, 주장 검증, 기사 비교, 타임라인, 원문 자료. 각 섹션은 eyebrow + section title + 콘텐츠, 섹션 간 `py-12` 여백.
4. **우측 rail** (xl 이상): 목차(텍스트 링크, 활성 항목만 `text-blue-600`), 관련 이슈. `xl:sticky xl:top-20`. 박스로 감싸지 않고 타이포만으로 구성.

Don't:

- 좌측 180px 헤더 컬럼 그리드(v1 dossier 패턴) 금지. 섹션 제목은 콘텐츠 위에 놓는다.
- 카드 안에 카드 금지. 본문에서 박스로 감쌀 수 있는 것은 표·인용·알림뿐이다.

### Admin — 검수 작업대

- 공개 화면과 같은 라이트 토큰을 쓴다. 별도 다크 테마, stone 계열 금지.
- 구조: 좌측 좁은 내비(텍스트), 중앙 검토 대상 리스트, 우측 판정/근거 패널.
- 데이터가 없거나 로드 실패해도 골격을 유지한다.

## 6. Components

### Status indicator

§3의 dot + 텍스트 패턴이 유일한 상태 표현이다. 기존 `StatusBadge`는 이 형태로 리팩터링한다. pill 배경이 필요한 곳은 없다.

### Metrics

| Canonical | 축약 (목록) | 전체 (상세) |
| --- | --- | --- |
| 수집 기사 | 기사 | 수집 기사 |
| 쟁점 묶음 | 쟁점 | 쟁점 묶음 |
| 변경 이력 | 변경 | 변경 이력 |
| 검증 완료 | 검증 | 검증 완료 |
| 추가 확인 | 확인 | 추가 확인 |

- 표현: 숫자 `text-2xl font-semibold tabular-nums text-gray-900` + label `text-xs text-gray-500`. 박스로 감싸지 않고 `gap-8`로 나열한다.
- 같은 화면에서 순서를 바꾸지 않는다. 새 metric은 이 표에 먼저 추가한다.

### Debate Map — 쟁점 비교

v1의 6색 tint 매트릭스를 폐기한다. 색 박스 대신 구조로 비교를 만든다.

- 2열 비교 레이아웃: 주장 A | 주장 B. 각 열은 eyebrow(주장 A / 주장 B) + 주장 요약 + 근거 출처 수.
- 그 아래 행 단위로: 충돌 지점(red dot), 확인된 사실(emerald dot), 공통분모(gray dot), 보류(gray dot).
- A/B를 색으로 구분하지 않는다. 위치와 label로 구분한다. 색은 판정 상태에만 쓴다.
- 각 항목에 근거 출처 수를 표기한다("근거 3건"). 출처 없는 항목은 보류로 분류한다.

### Timeline

두 종류를 한 컴포넌트에 섞지 않는다: **사건 타임라인**(발생 기준) / **검증 이력**(확인 기준).

- 수직 단일 축: 좌측에 `w-px bg-gray-200` 선 + 이벤트 dot, 우측에 시점·내용.
- dot 색은 이벤트 유형: 사실 확인 emerald, 충돌/반박 red, 변경 amber, 일반 gray.
- 각 항목: 시점(§4 포맷) + 요약 1~2문장 + 근거 출처 링크.
- 판정 변경은 삭제하지 않고 기록한다: "변경: 미확인 → 사실 (확인 2026.06.08)".
- 항목을 카드로 감싸지 않는다. 행 + 여백 리듬.

### Evidence & Sources

- 각 근거: 출처명(`font-medium text-gray-900`) · 보도 시점 · 원문 링크(`text-blue-600 hover:underline`).
- 발췌는 `border-l-2 border-gray-200 pl-4 text-gray-600`, 1~2문장.
- 출처 없는 주장·판정·수치를 화면에 두지 않는다. 출처 없음 = 미확인.
- 출처에 임의 신뢰 점수를 붙이지 않는다. 신뢰도는 교차 확인 수로 표현한다("기사 4건에서 교차 확인").
- 원문 링크가 사라지면 "원문 접근 불가 (확인 시점 보존)"으로 표기하고 삭제하지 않는다.

### Tables

- 컨테이너: `overflow-x-auto`, table에 `min-w-[...]` 명시. 모바일에서 표만 스크롤.
- Header: `text-xs font-medium text-gray-500`, `border-b border-gray-200`, 실제 `th`. 배경 없거나 `bg-gray-50`.
- Row: `border-b border-gray-100`, hover `bg-gray-50`.
- 셀 안 상태는 dot + 텍스트.

### Forms

- Input: `h-10 rounded-md border border-gray-300 text-[15px]`, focus `ring-2 ring-blue-600/20 border-blue-600`.
- Label은 항상 input 위에. placeholder를 label 대용으로 쓰지 않는다.
- Error: `text-red-600 text-sm`, 필드 바로 아래, 원인과 해결을 명시.

### Buttons

- Primary: `bg-blue-600 text-white hover:bg-blue-700 rounded-md h-10 px-4 font-medium`. **화면 영역당 1개.**
- Secondary: `border border-gray-300 text-gray-700 hover:bg-gray-50`.
- Tertiary / 텍스트 버튼: `text-blue-600 hover:underline`.
- `bg-slate-950` 다크 버튼 계층은 제거한다. primary는 accent 하나다.
- 버튼 텍스트는 동작 결과를 말한다: "제출" 대신 "비교 요청".

### Interaction States

- Hover: 배경 한 단계(`hover:bg-gray-50`)만. transform/scale/shadow 변화 금지.
- Focus-visible: `ring-2 ring-blue-600` 계열. outline 제거 금지.
- Selected: `bg-gray-50` + `border-l-2 border-blue-600`. hover보다 항상 강해야 한다.
- Disabled: `opacity-50 cursor-not-allowed` + 비활성 이유를 인접 텍스트로.
- Motion: `transition-colors` 150ms만 기본 허용. `prefers-reduced-motion` 존중.

## 7. Empty, Loading, Error

세 상태 모두 골격(레이아웃, nav)을 유지한다.

- **Empty**: 무엇이 아직 없는지 + 다음 행동 1개. "등록된 쟁점이 아직 없습니다. 기사 링크를 제출하면 분해가 시작됩니다." 실패 어휘 금지. 일러스트 금지 — 텍스트 두 줄과 버튼이면 충분하다.
- **Loading**: 실제 콘텐츠 배치와 일치하는 skeleton(`bg-gray-100 rounded animate-pulse`). 전체 화면 spinner 금지.
- **Error**: 무엇을 못 불러왔는지 + 재시도. 내부 구현 문구(API, 서버, 상태 코드) 노출 금지. 부분 실패 시 성공한 데이터는 유지.

## 8. Copy Rules

Preferred: 사건, 이슈, 주장, 쟁점, 근거, 원문, 검증, 확인, 변경, 보류, 추가 확인

Avoid: 가짜뉴스 판별기, 댓글, 진영, 성향, AI가 알아서 판단, API/토큰/서버 등 내부 구현 단어

Rules:

- 판정은 단정 + 시점 + 근거 범위: "기사 4건 교차 확인 결과 반박됨 (확인 2026.06.08)".
- 미확인을 부정적으로 쓰지 않는다: "확인 안 됨" → "추가 확인 대기".
- 같은 동작은 흐름 전체에서 같은 이름: "비교 요청" 버튼 → "비교 요청이 접수되었습니다".
- 카피도 절제한다. 화면이 스스로 설명되면 안내 문장을 쓰지 않는다.

## 9. Responsive

- Mobile: 홈은 목록 우선. 상세는 header → key facts → 본문 섹션 순. 표·타임라인은 컨테이너 내부 스크롤, 문서 전체 가로 overflow 금지.
- Desktop: 홈 2-pane, 상세 본문 + 우측 rail(`xl:sticky xl:top-20`).
- 검증 기준: 390px에서 제목·버튼·metric이 겹치지 않는다. 1280px에서 header/nav가 겹치지 않는다.

## 10. Accessibility

- 실제 `a`/`button` 사용. 아이콘-only 버튼은 접근 가능한 이름 필수.
- `focus-visible` 제거 금지.
- 색만으로 상태 전달 금지 — dot에는 항상 텍스트가 붙는다(§3 패턴이 이를 보장).
- gray-500 이상만 본문 텍스트로 사용 (gray-400은 비활성 전용). white 배경 기준 AA 대비 확인.
- 실제 `th`, sticky nav `scroll-margin-top` 유지.

## 11. Implementation Checklist

변경 전:

- 이 문서를 확인했고, 새 색·radius·shadow가 필요한 이유를 말할 수 있다.
- 새 상태/용어는 §3, §6 Metrics 표에 먼저 추가했다.

변경 후:

- `npm run lint` / `npm run build`
- 390px, 1280px 확인. 문서 전체 가로 overflow 확인.
- empty/loading/error 세 상태 확인.
- 모든 판정·수치에 시점 label 확인.

Failure test — 하나라도 해당하면 다시 만든다:

- `font-black`, tint 색 박스, badge pill 나열, 다크 패널이 화면에 있다.
- 섹션이 여백 대신 hairline border로 구분되어 있다.
- 화면을 흑백으로 캡처했을 때 위계가 무너진다 (위계가 색에 의존하고 있다는 뜻).
- 이 화면이 "AI가 만든 대시보드 데모"처럼 보인다.
- 출처 없는 판정, 시점 없는 판정이 있다.

## 12. Migration Order (v1 → v2)

1. Pretendard 적용, `font-black` → `font-bold`/`font-semibold` 일괄 치환
2. 배경 tint 제거 (`#f5f7f2`, `#fbfcf8`, `#eef4ff` → white / gray-50), slate → gray
3. 다크 rail·다크 버튼 계층 제거, accent를 blue-600 단일화
4. StatusBadge → dot + 텍스트 리팩터링, badge 나열 → 평문 메타
5. 섹션 hairline border 제거, 여백 리듬으로 전환
6. Debate Map 색 박스 → 2열 구조 비교로 재구성
7. metric 용어/순서 통일, 시점 label 보강
8. 390px / 1280px overflow 확인

## 13. Changelog

- 2026.06.10 (v2): 디자인 방향 전환. 기록대/원장 컨셉 폐기, 뉴스 미디어·빅테크 기준의 절제된 시스템으로 재정의. Pretendard 도입, 단일 액센트, dot 상태 표현, 여백 기반 레이아웃.