import { useMemo, useState } from "react";
import {
  Bell,
  CaretDown,
  CaretRight,
  ChartLineUp,
  CheckCircle,
  Clock,
  Command,
  Database,
  FileMagnifyingGlass,
  Funnel,
  GearSix,
  House,
  ListChecks,
  MagnifyingGlass,
  Monitor,
  NotePencil,
  Phone,
  Rows,
  ShieldCheck,
  SlidersHorizontal,
  Star,
  Tray,
  WarningCircle,
  X,
} from "@phosphor-icons/react";

const topics = [
  { id: "all", label: "전체 이슈", icon: House },
  { id: "politics", label: "정치", icon: ShieldCheck },
  { id: "society", label: "사회", icon: Rows },
  { id: "economy", label: "경제", icon: ChartLineUp },
  { id: "global", label: "국제", icon: Database },
  { id: "science", label: "과학/기술", icon: GearSix },
  { id: "health", label: "보건/의료", icon: WarningCircle },
];

const issues = [
  {
    id: "election-paper",
    title: "선관위 투표용지 부족 사태",
    topic: "정치",
    scope: "선거/민주주의",
    articles: 126,
    clusters: 18,
    changedClaims: 3,
    verified: 11,
    needsReview: 7,
    evidence: "공식 입장 있음",
    status: "검증 진행",
    priority: "높음",
    score: 91,
    updated: "3분 전",
    summary:
      "투표용지 부족 발생 범위와 원인, 재선거 요구의 법적 근거가 핵심 쟁점입니다.",
  },
  {
    id: "metro-fare",
    title: "서울 지하철 요금 500원 인상 검토",
    topic: "사회",
    scope: "교통/생활비",
    articles: 78,
    clusters: 11,
    changedClaims: 2,
    verified: 6,
    needsReview: 5,
    evidence: "공식 입장 없음",
    status: "초기 기준",
    priority: "중간",
    score: 74,
    updated: "12분 전",
    summary: "요금 인상 폭과 적용 시점이 보도마다 다르게 확산되고 있습니다.",
  },
  {
    id: "health-insurance",
    title: "정부, 2026년부터 건강보험료 대폭 인상",
    topic: "경제",
    scope: "정책/보험",
    articles: 64,
    clusters: 9,
    changedClaims: 1,
    verified: 5,
    needsReview: 4,
    evidence: "공식 입장 있음",
    status: "검증 진행",
    priority: "중간",
    score: 69,
    updated: "18분 전",
    summary: "인상률 수치와 적용 대상 범위가 혼재되어 재분류 중입니다.",
  },
  {
    id: "pension",
    title: "국민연금 고갈 시점 2035년으로 앞당겨져",
    topic: "경제",
    scope: "연금/통계",
    articles: 92,
    clusters: 14,
    changedClaims: 4,
    verified: 8,
    needsReview: 6,
    evidence: "공식 입장 있음",
    status: "업데이트 필요",
    priority: "높음",
    score: 86,
    updated: "27분 전",
    summary: "추계 기준 연도와 시나리오 차이가 제목에서 단정적으로 표현되고 있습니다.",
  },
  {
    id: "alert-system",
    title: "수도권 전역 대설 경보 발령 예정",
    topic: "사회",
    scope: "재난/기상",
    articles: 55,
    clusters: 7,
    changedClaims: 0,
    verified: 4,
    needsReview: 3,
    evidence: "공식 입장 있음",
    status: "사실 확인",
    priority: "낮음",
    score: 58,
    updated: "31분 전",
    summary: "기상청 발표와 일부 지역 커뮤니티 확산 문구를 분리해 표시합니다.",
  },
  {
    id: "us-election",
    title: "미국 대선 관련 허위정보 확산",
    topic: "국제",
    scope: "선거/해외",
    articles: 67,
    clusters: 10,
    changedClaims: 2,
    verified: 5,
    needsReview: 5,
    evidence: "공식 입장 있음",
    status: "민감 검토",
    priority: "높음",
    score: 82,
    updated: "1시간 전",
    summary: "해외 선거 관련 조작 주장과 검증 가능한 절차 정보를 분리하고 있습니다.",
  },
];

const claims = [
  {
    id: 1,
    text: "전국적으로 투표용지가 대규모로 부족했다.",
    type: "수치 주장",
    verdict: "사실",
    tone: "positive",
    confidence: 0.86,
    evidence: "선관위 보도자료 (2024-04-11)",
    source: "중앙선거관리위원회",
    update: "변경 없음",
    articles: 28,
  },
  {
    id: 2,
    text: "투표용지 부족으로 투표가 지연되거나 중단되었다.",
    type: "사실 주장",
    verdict: "업데이트 필요",
    tone: "warning",
    confidence: 0.62,
    evidence: "지역 선관위 보고서 일부",
    source: "언론 보도 종합",
    update: "업데이트됨 (1시간 전)",
    articles: 19,
  },
  {
    id: 3,
    text: "선관위는 사전에 투표용지 수요를 예측하지 못했다.",
    type: "원인 해석",
    verdict: "맥락 누락",
    tone: "warning",
    confidence: 0.58,
    evidence: "감사원 보고서, 국회 행안위 회의록",
    source: "국회 회의록",
    update: "변경 없음",
    articles: 15,
  },
  {
    id: 4,
    text: "특정 후보의 기표란이 누락된 투표용지가 배부되었다.",
    type: "의혹 주장",
    verdict: "사실",
    tone: "positive",
    confidence: 0.81,
    evidence: "선관위 보도자료 (2024-04-11)",
    source: "언론 보도 특수",
    update: "변경 없음",
    articles: 12,
  },
  {
    id: 5,
    text: "투표용지 부족 사태는 관리 부실이 주된 원인이다.",
    type: "책임 주장",
    verdict: "업데이트 필요",
    tone: "warning",
    confidence: 0.47,
    evidence: "선관위 입장문, 전문가 인터뷰",
    source: "복수 언론",
    update: "업데이트됨 (2시간 전)",
    articles: 9,
  },
  {
    id: 6,
    text: "투표용지 부족은 특정 정당에 유리하도록 의도된 것이다.",
    type: "낙인/의혹",
    verdict: "근거 부족",
    tone: "danger",
    confidence: 0.18,
    evidence: "주장 출처 불명",
    source: "SNS 게시물",
    update: "변경 없음",
    articles: 4,
  },
];

const updates = [
  {
    time: "3분 전",
    type: "공식 입장",
    text: "중앙선관위, 투표용지 부족 사태 관련 추가 설명자료 발표",
    source: "중앙선거관리위원회",
    tone: "positive",
  },
  {
    time: "12분 전",
    type: "언론 보도",
    text: "감사원, 선관위 투표용지 관리 실태 감사 착수",
    source: "연합뉴스",
    tone: "info",
  },
  {
    time: "29분 전",
    type: "언론 보도",
    text: "여야, 투표용지 부족 사태 관련 공방 이어져",
    source: "KBS",
    tone: "info",
  },
  {
    time: "1시간 전",
    type: "주장 업데이트",
    text: "투표 지연/중단 주장 신뢰도 업데이트",
    source: "FactTracer 분석팀",
    tone: "warning",
  },
  {
    time: "2시간 전",
    type: "공식 입장",
    text: "선관위, 지역별 투표용지 인쇄 현황 공개",
    source: "중앙선거관리위원회",
    tone: "positive",
  },
];

const articles = [
  {
    publisher: "연합뉴스",
    title: "선관위 투표용지 부족 사태 감사 착수",
    published: "06-08 09:34",
    claims: 4,
    official: "인용",
    freshness: "최신 반영",
    status: "대체로 사실",
  },
  {
    publisher: "KBS",
    title: "일부 투표소 지연 신고 잇따라",
    published: "06-08 08:58",
    claims: 3,
    official: "부분 인용",
    freshness: "업데이트 필요",
    status: "초기 기준",
  },
  {
    publisher: "지역신문A",
    title: "전국 50곳 부족 주장 제기",
    published: "06-08 08:21",
    claims: 5,
    official: "미인용",
    freshness: "후속 미반영",
    status: "맥락 누락",
  },
  {
    publisher: "정책브리핑",
    title: "투표용지 인쇄·배부 절차 설명자료",
    published: "06-07 22:10",
    claims: 2,
    official: "원문",
    freshness: "최신 반영",
    status: "사실",
  },
];

const perspectives = [
  {
    name: "관리 책임 강조 관점",
    claim: "현장 관리 실패와 재발 방지 대책이 핵심입니다.",
    evidence: "투표 지연 보도, 선관위 사과, 후속 조사 필요성",
    objection: "고의성 여부는 현재 자료만으로 단정할 수 없습니다.",
    common: "투표용지 부족 발생 자체는 확인 가능한 사안입니다.",
  },
  {
    name: "선거 불신 확대 경계 관점",
    claim: "검증되지 않은 조작 주장은 문제 해결보다 불신만 키울 수 있습니다.",
    evidence: "공식 조사 전 단계의 불확실성, 근거 없는 SNS 확산",
    objection: "관리 책임 문제를 축소해서는 안 된다는 반론이 있습니다.",
    common: "공식 조사와 판정 변경 이력 공개가 필요합니다.",
  },
  {
    name: "재선거 요구 집중 관점",
    claim: "메시지를 법적 요구와 참정권 침해 여부에 집중해야 합니다.",
    evidence: "투표 지연 및 포기 사례 보도, 법적 판단 필요 주장",
    objection: "재선거 요건 충족 여부는 법적 판단이 필요합니다.",
    common: "선관위의 추가 자료 공개가 선행되어야 합니다.",
  },
];

const adminRows = [
  {
    id: "ISS-260608-001",
    title: "선관위 투표용지 부족 사태",
    topic: "정치·선거",
    articles: 126,
    firstSeen: "06-08 09:41",
    status: "검토 대기",
    priority: "높음",
  },
  {
    id: "ISS-260608-002",
    title: "서울 지하철 요금 500원 인상 검토",
    topic: "사회",
    articles: 78,
    firstSeen: "06-08 09:02",
    status: "검토 중",
    priority: "중간",
  },
  {
    id: "ISS-260607-015",
    title: "정부, 2026년부터 건강보험료 대폭 인상",
    topic: "경제",
    articles: 64,
    firstSeen: "06-07 23:18",
    status: "검토 대기",
    priority: "중간",
  },
  {
    id: "ISS-260607-014",
    title: "국민연금 고갈 시점 2035년으로 앞당겨져",
    topic: "경제",
    articles: 92,
    firstSeen: "06-07 21:44",
    status: "검토 대기",
    priority: "높음",
  },
];

const adminLogs = [
  "10:12 · Claim Verifier Agent 완료 · 18개 클러스터 재계산",
  "10:08 · Evidence Retriever Agent · 공식자료 후보 4건 감지",
  "09:54 · Toxicity Filter Agent · 낙인 표현 7건 정제",
  "09:41 · Issue Detector Agent · 자동 이슈 후보 생성",
];

const mobileAlerts = [
  "새 공식 입장이 등록되었습니다.",
  "국민연금 고갈 시점 판정이 변경되었습니다.",
  "미국 대선 관련 주장 클러스터가 추가되었습니다.",
  "의대 정원 확대 후속 조치 발표가 감지되었습니다.",
];

const issueStructures = {
  "election-paper": {
    confirmedFacts: [
      ["발생", "일부 투표소에서 투표용지 부족 또는 배부 지연이 확인됨", "공식자료 확인"],
      ["시점", "초기 보도 수치와 후속 조사 수치가 서로 다른 기준으로 확산됨", "초기/후속 분리"],
      ["주의", "조직적 방해·특정 세력 개입 주장은 현재 확인 가능한 근거 부족", "낙인 정제"],
    ],
    clusters: [
      {
        title: "부족 투표소 수",
        claims: ["14곳 초기 파악", "전국 50곳 후속 주장"],
        conflict: "집계 기준과 발표 시점이 다름",
        status: "수치 충돌",
      },
      {
        title: "원인",
        claims: ["투표율 예측 실패", "현장 배분 실패"],
        conflict: "사전 계획 책임과 현장 대응 책임의 경계",
        status: "맥락 필요",
      },
      {
        title: "요구 사항",
        claims: ["재선거 요구", "진상조사 우선"],
        conflict: "법적 절차를 바로 요구할지, 조사 결과를 기다릴지",
        status: "법적 판단 필요",
      },
    ],
    evidenceMatrix: [
      ["최신 공식 기준", "선관위 설명자료", "2024-04-11", "주요 주장 4건에 연결"],
      ["초기 보도 기준", "언론 종합", "06-08 08:21", "후속 수치 미반영 가능"],
      ["검증 어려움", "SNS 게시물", "출처 불명", "조직적 개입 단정 불가"],
    ],
    perspectiveSnapshot: [
      ["관리 책임 강조", "책임자 문책과 제도 개선", "발생 사실·사과", "고의성 여부"],
      ["선거 불신 확대 경계", "조작 단정은 불신을 키움", "공식 조사 전 불확실성", "관리 책임 축소 우려"],
      ["재선거 요구 집중", "참정권 침해 여부가 핵심", "투표 지연 사례", "재선거 요건"],
    ],
  },
  default: {
    confirmedFacts: [
      ["확인", "여러 기사에서 같은 사건을 다른 수치와 조건으로 설명하고 있음", "수집 완료"],
      ["분리", "기사 작성 시점과 후속 업데이트 반영 여부를 구분해야 함", "재분류 중"],
      ["주의", "제목의 단정 표현과 원문 근거 사이의 차이를 검토 중", "맥락 점검"],
    ],
    clusters: [
      {
        title: "수치 기준",
        claims: ["초기 보도 수치", "후속 자료 수치"],
        conflict: "기준일·대상·집계 방식 차이",
        status: "수치 비교",
      },
      {
        title: "정책 해석",
        claims: ["대상 확대", "부담 증가"],
        conflict: "정책 조건과 실제 적용 범위",
        status: "맥락 필요",
      },
      {
        title: "요구 사항",
        claims: ["제도 개선", "공식 해명 요구"],
        conflict: "즉시 대응과 절차적 검토의 우선순위",
        status: "검토 대기",
      },
    ],
    evidenceMatrix: [
      ["공식자료 후보", "기관 발표/보도자료", "감지됨", "출처 신뢰도 산정 중"],
      ["언론 보도", "복수 언론", "수집됨", "중복 제거 완료"],
      ["추가 확인", "사용자 제보/원문", "대기", "관리자 검토 필요"],
    ],
    perspectiveSnapshot: [
      ["사실 확인 우선", "최신 수치와 근거를 먼저 확정", "복수 보도", "공식자료 지연"],
      ["영향 강조", "사용자 피해와 정책 영향을 중시", "사례 보도", "과장 표현"],
      ["절차 중심", "법적·행정 절차를 우선 검토", "제도 자료", "해석 차이"],
    ],
  },
};

function cx(...classes) {
  return classes.filter(Boolean).join(" ");
}

function ToneDot({ tone = "info" }) {
  return <span className={cx("tone-dot", `tone-${tone}`)} aria-hidden="true" />;
}

function Verdict({ children, tone }) {
  return <span className={cx("verdict", `verdict-${tone}`)}>{children}</span>;
}

function SurfaceButton({ icon: Icon, label, active, onClick }) {
  return (
    <button className={cx("surface-button", active && "is-active")} onClick={onClick}>
      {Icon ? <Icon size={18} weight={active ? "fill" : "regular"} /> : null}
      <span>{label}</span>
    </button>
  );
}

function AppHeader({ activeSurface, setActiveSurface, onRequestOpen }) {
  const surfaces = [
    { id: "home", label: "쟁점 홈", icon: Monitor },
    { id: "issue", label: "이슈 상세", icon: FileMagnifyingGlass },
    { id: "mobile", label: "앱", icon: Phone },
  ];

  return (
    <header className="topbar">
      <div className="brand" role="button" tabIndex={0} onClick={() => setActiveSurface("home")}>
        <span className="brand-mark">FactTracer</span>
        <span className="brand-sub">AI 기반 사실 검증 플랫폼</span>
      </div>
      <label className="global-search">
        <MagnifyingGlass size={18} />
        <input placeholder="검색어, 주장, 기사 URL 입력" />
      </label>
      <nav className="surface-nav" aria-label="프로토타입 화면">
        {surfaces.map((surface) => (
          <SurfaceButton
            key={surface.id}
            icon={surface.icon}
            label={surface.label}
            active={activeSurface === surface.id}
            onClick={() => setActiveSurface(surface.id)}
          />
        ))}
      </nav>
      <button
        className={cx("ops-entry", activeSurface === "admin" && "is-active")}
        onClick={() => setActiveSurface("admin")}
      >
        <Command size={17} />
        <span>운영 콘솔</span>
      </button>
      <button className="primary-action" onClick={onRequestOpen}>
        <NotePencil size={18} weight="bold" />
        <span>검증 요청</span>
      </button>
    </header>
  );
}

function TopicRail({ activeTopic, setActiveTopic }) {
  return (
    <aside className="topic-rail">
      <div className="rail-heading">
        <span>토픽</span>
        <button className="text-command">관리</button>
      </div>
      <div className="topic-list">
        {topics.map((topic) => {
          const Icon = topic.icon;
          return (
            <button
              key={topic.id}
              className={cx("topic-row", activeTopic === topic.id && "is-active")}
              onClick={() => setActiveTopic(topic.id)}
            >
              <Icon size={20} />
              <span>{topic.label}</span>
            </button>
          );
        })}
      </div>
      <div className="rail-section compact">
        <div className="section-line-title">
          <span>최근 본 이슈</span>
          <button className="text-command">전체 보기</button>
        </div>
        {issues.slice(0, 5).map((issue) => (
          <div className="recent-row" key={issue.id}>
            <Clock size={14} />
            <span>{issue.title}</span>
            <time>{issue.updated}</time>
          </div>
        ))}
      </div>
    </aside>
  );
}

function IssueStream({
  activeTopic,
  setActiveTopic,
  filteredIssues,
  selectedIssueId,
  setSelectedIssueId,
  setActiveSurface,
}) {
  const openIssue = (id) => {
    setSelectedIssueId(id);
    setActiveSurface("issue");
  };
  const selectedIssue =
    filteredIssues.find((issue) => issue.id === selectedIssueId) ?? filteredIssues[0] ?? issues[0];
  const structure = issueStructures[selectedIssue.id] ?? issueStructures.default;

  return (
    <main className="stream-surface">
      <div className="surface-title-row">
        <div>
          <h1>사건별 팩트 구조</h1>
          <p>
            이슈를 많이 보여주기보다, 한 사건 안에서 무엇이 확인됐고 어디서 충돌하는지 먼저 보여줍니다.
          </p>
        </div>
        <div className="live-status">
          <ToneDot tone="positive" />
          <span>업데이트 1분 전</span>
          <button className="icon-command" aria-label="새로고침">
            <Clock size={18} />
          </button>
        </div>
      </div>

      <div className="filter-strip">
        <div className="topic-filter-row" aria-label="토픽 필터">
          {topics.slice(0, 6).map((topic) => (
            <button
              key={topic.id}
              className={cx("topic-chip", activeTopic === topic.id && "is-active")}
              onClick={() => setActiveTopic(topic.id)}
            >
              {topic.label}
            </button>
          ))}
        </div>
        <label className="check-control">
          <input type="checkbox" />
          <span>검증 진행 중만 보기</span>
        </label>
        <button className="filter-control">
          <Funnel size={15} />
          공식자료 있음
        </button>
      </div>

      <div className="fact-home">
        <section className="issue-chooser" aria-label="사건 선택">
          <div className="compact-head">
            <span>감지된 사건</span>
            <small>숫자는 보조 지표입니다</small>
          </div>
          {filteredIssues.map((issue) => (
            <button
              className={cx("brief-issue-row", selectedIssue.id === issue.id && "is-active")}
              key={issue.id}
              onClick={() => setSelectedIssueId(issue.id)}
            >
              <span>
                <strong>{issue.title}</strong>
                <small>{issue.topic} · 기사 {issue.articles} · 클러스터 {issue.clusters}</small>
              </span>
              <em>{issue.changedClaims}개 변경</em>
            </button>
          ))}
        </section>

        <section className="fact-briefing" aria-label="선택 사건 팩트 구조">
          <div className="briefing-title">
            <span className="eyebrow">{selectedIssue.topic} 〉 {selectedIssue.scope}</span>
            <h2>{selectedIssue.title}</h2>
            <p>{selectedIssue.summary}</p>
            <div className="briefing-metrics">
              <span>검증 완료 <strong>{selectedIssue.verified}</strong></span>
              <span>추가 확인 <strong>{selectedIssue.needsReview}</strong></span>
              <span>변경 주장 <strong>{selectedIssue.changedClaims}</strong></span>
              <span>{selectedIssue.evidence}</span>
            </div>
          </div>

          <div className="structure-block">
            <div className="block-head">
              <h3>현재까지 확인된 것</h3>
              <button className="text-command" onClick={() => openIssue(selectedIssue.id)}>상세 보기</button>
            </div>
            {structure.confirmedFacts.map(([label, text, status]) => (
              <div className="fact-row" key={`${label}-${text}`}>
                <span>{label}</span>
                <strong>{text}</strong>
                <Verdict tone={status.includes("부족") || status.includes("정제") ? "danger" : status.includes("분리") || status.includes("중") ? "warning" : "positive"}>
                  {status}
                </Verdict>
              </div>
            ))}
          </div>

          <div className="structure-block">
            <div className="block-head">
              <h3>충돌하는 주장 클러스터</h3>
              <small>PRD의 핵심 단위: Issue → Claim Cluster → Claim → Evidence</small>
            </div>
            <div className="cluster-map">
              <div className="cluster-head">
                <span>쟁점</span>
                <span>주장 A</span>
                <span>주장 B</span>
                <span>충돌 이유</span>
                <span>상태</span>
              </div>
              {structure.clusters.map((cluster) => (
                <div className="cluster-row" key={cluster.title}>
                  <strong>{cluster.title}</strong>
                  <span>{cluster.claims[0]}</span>
                  <span>{cluster.claims[1]}</span>
                  <span>{cluster.conflict}</span>
                  <Verdict tone={cluster.status.includes("필요") || cluster.status.includes("충돌") ? "warning" : "info"}>
                    {cluster.status}
                  </Verdict>
                </div>
              ))}
            </div>
          </div>

          <div className="structure-columns">
            <div className="structure-block">
              <div className="block-head">
                <h3>근거 기준</h3>
              </div>
              {structure.evidenceMatrix.map(([type, source, date, note]) => (
                <div className="evidence-row" key={`${type}-${source}`}>
                  <strong>{type}</strong>
                  <span>{source}</span>
                  <time>{date}</time>
                  <small>{note}</small>
                </div>
              ))}
            </div>
            <div className="structure-block">
              <div className="block-head">
                <h3>관점 이해</h3>
              </div>
              {structure.perspectiveSnapshot.map(([name, core, verifiable, hard]) => (
                <div className="perspective-brief-row" key={name}>
                  <strong>{name}</strong>
                  <span>{core}</span>
                  <small>검증 가능: {verifiable}</small>
                  <small>검증 어려움: {hard}</small>
                </div>
              ))}
            </div>
          </div>
        </section>
      </div>
      <div className="surface-footnote">
        <WarningCircle size={16} />
        <span>FactTracer는 사람이나 진영이 아니라 주장과 근거를 분류하고, 낙인 표현은 정제합니다.</span>
      </div>
    </main>
  );
}

function HomeRail({ onRequestOpen, setActiveSurface, setMobileTab }) {
  return (
    <aside className="right-rail">
      <section className="rail-section">
        <div className="section-line-title">
          <h2>직접 기사 검증</h2>
          <button className="text-command" onClick={onRequestOpen}>
            자세히 보기
          </button>
        </div>
        <div className="inline-form">
          <input placeholder="기사 URL을 입력하세요" />
          <button onClick={onRequestOpen}>검증 시작</button>
        </div>
      </section>
      <section className="rail-section">
        <div className="section-line-title">
          <h2>구조화된 제보 흐름</h2>
          <button className="text-command" onClick={onRequestOpen}>제출</button>
        </div>
        <div className="participation-flow">
          {["사용자 주장 제출", "욕설/낙인 필터링", "기존 클러스터와 비교", "AI 요약 후 쟁점 지도 반영"].map((step, index) => (
            <span key={step}>
              <b>{index + 1}</b>
              {step}
            </span>
          ))}
        </div>
      </section>
      <section className="rail-section">
        <div className="section-line-title">
          <h2>관심 관점</h2>
          <button
            className="text-command"
            onClick={() => {
              setMobileTab("home");
              setActiveSurface("mobile");
            }}
          >
            앱 알림 보기
          </button>
        </div>
        <div className="viewpoint-list">
          {["관리 책임", "참정권 침해", "법적 쟁점", "제도 개선", "언론 보도 문제"].map((viewpoint, index) => (
            <button key={viewpoint} className={index === 0 ? "is-active" : ""}>
              {viewpoint}
            </button>
          ))}
        </div>
      </section>
      <section className="rail-section">
        <div className="section-line-title">
          <h2>업데이트 트리거</h2>
          <button className="text-command">전체 로그</button>
        </div>
        {updates.slice(0, 4).map((update) => (
          <div className="update-row" key={`${update.time}-${update.type}`}>
            <ToneDot tone={update.tone} />
            <span>
              <strong>{update.type}</strong>
              <small>{update.text}</small>
            </span>
            <time>{update.time}</time>
          </div>
        ))}
      </section>
    </aside>
  );
}

function HomeScreen({
  activeTopic,
  setActiveTopic,
  selectedIssueId,
  setSelectedIssueId,
  setActiveSurface,
  onRequestOpen,
  setMobileTab,
}) {
  const filteredIssues = useMemo(() => {
    if (activeTopic === "all") return issues;
    const selected = topics.find((topic) => topic.id === activeTopic)?.label;
    return issues.filter((issue) => issue.topic === selected);
  }, [activeTopic]);

  return (
    <div className="workspace home-workspace">
      <IssueStream
        activeTopic={activeTopic}
        setActiveTopic={setActiveTopic}
        filteredIssues={filteredIssues}
        selectedIssueId={selectedIssueId}
        setSelectedIssueId={setSelectedIssueId}
        setActiveSurface={setActiveSurface}
      />
      <HomeRail onRequestOpen={onRequestOpen} setActiveSurface={setActiveSurface} setMobileTab={setMobileTab} />
    </div>
  );
}

function IssueHeader({ issue }) {
  return (
    <div className="issue-header">
      <div className="breadcrumb">{issue.topic} 〉 {issue.scope}</div>
      <div className="issue-title-line">
        <h1>{issue.title}</h1>
        <button className="icon-command" aria-label="관심 이슈 저장">
          <Star size={22} />
        </button>
      </div>
      <p>{issue.summary}</p>
      <div className="metric-line" aria-label="이슈 지표">
        <span>관련 기사 <strong>{issue.articles}</strong></span>
        <span>주장 클러스터 <strong>{issue.clusters}</strong></span>
        <span>검증 완료 <strong>{issue.verified}</strong></span>
        <span>추가 확인 필요 <strong>{issue.needsReview}</strong></span>
        <span>업데이트 <strong>{issue.updated}</strong></span>
      </div>
    </div>
  );
}

function IssueTabs({ activeTab, setActiveTab }) {
  const tabs = ["핵심 팩트", "쟁점 지도", "주장별 검증", "기사별 비교", "관점별 주장", "타임라인", "원문 자료", "사용자 제보"];
  return (
    <div className="tab-strip" role="tablist">
      {tabs.map((tab) => (
        <button key={tab} className={cx(activeTab === tab && "is-active")} onClick={() => setActiveTab(tab)}>
          {tab}
        </button>
      ))}
    </div>
  );
}

function CoreFacts() {
  const facts = [
    ["확인된 사실", "일부 투표소에서 투표용지 부족 또는 배부 지연이 발생했습니다.", "공식자료 확인"],
    ["확인된 사실", "선관위는 발생 지역별 인쇄·배부 현황을 추가로 공개했습니다.", "공식자료 확인"],
    ["확인 대기", "전국 50곳 부족 주장은 후속 조사 기준과 초기 보도 기준이 섞여 있습니다.", "재검증 중"],
    ["주의 표현", "조직적 방해 또는 특정 세력 개입 주장은 현재 확인 가능한 근거가 부족합니다.", "근거 부족"],
  ];
  return (
    <div className="analysis-list">
      {facts.map(([label, text, status], index) => (
        <div className="analysis-row" key={text}>
          <span className="row-index">{index + 1}</span>
          <span className="analysis-label">{label}</span>
          <strong>{text}</strong>
          <Verdict tone={status.includes("부족") ? "danger" : status.includes("중") ? "warning" : "positive"}>{status}</Verdict>
        </div>
      ))}
    </div>
  );
}

function IssueMap() {
  const rows = [
    {
      title: "원인",
      a: "투표율 예측 실패",
      b: "현장 배분 실패",
      conflict: "사전 수요 예측과 현장 대응 책임을 어디까지 나눌지",
      common: "투표용지 부족 발생은 공식자료로 확인 가능",
    },
    {
      title: "요구 사항",
      a: "재선거 요구",
      b: "진상조사 요구",
      conflict: "법적 절차를 바로 요구할지, 조사 결과를 먼저 기다릴지",
      common: "선관위 추가 자료 공개 필요",
    },
    {
      title: "운동 전략",
      a: "참정권 침해 프레임",
      b: "부정선거 의혹 제기",
      conflict: "대중 설득력을 위해 메시지를 좁힐지, 의혹을 포함할지",
      common: "확인 가능한 근거와 추측성 주장을 분리해야 함",
    },
  ];
  return (
    <div className="map-list">
      <div className="map-head">
        <span>쟁점</span>
        <span>관점 A</span>
        <span>관점 B</span>
        <span>충돌 이유</span>
        <span>공통분모</span>
      </div>
      {rows.map((row) => (
        <div className="map-row" key={row.title}>
          <strong>{row.title}</strong>
          <span>{row.a}</span>
          <span>{row.b}</span>
          <span>{row.conflict}</span>
          <span>{row.common}</span>
        </div>
      ))}
    </div>
  );
}

function ClaimLedger() {
  return (
    <div className="claim-ledger" role="table" aria-label="주장별 검증">
      <div className="claim-head claim-grid" role="row">
        <span>#</span>
        <span>주장</span>
        <span>유형</span>
        <span>판정</span>
        <span>신뢰도</span>
        <span>공식근거</span>
        <span>변경상태</span>
      </div>
      {claims.map((claim) => (
        <div className="claim-row claim-grid" key={claim.id} role="row">
          <span>{claim.id}</span>
          <strong>{claim.text}</strong>
          <span>{claim.type}</span>
          <Verdict tone={claim.tone}>{claim.verdict}</Verdict>
          <span className="confidence">
            <span>{claim.confidence.toFixed(2)}</span>
            <i style={{ "--value": `${claim.confidence * 100}%` }} />
          </span>
          <span>
            {claim.evidence}
            <small>{claim.source}</small>
          </span>
          <span className={claim.update.includes("업데이트") ? "number-hot" : ""}>{claim.update}</span>
        </div>
      ))}
    </div>
  );
}

function ArticleCompare() {
  return (
    <div className="data-table">
      <div className="article-grid table-head">
        <span>언론사</span>
        <span>기사 제목</span>
        <span>작성 시점</span>
        <span>포함 주장</span>
        <span>공식자료</span>
        <span>최신성</span>
        <span>상태</span>
      </div>
      {articles.map((article) => (
        <div className="article-grid table-row static-row" key={article.title}>
          <strong>{article.publisher}</strong>
          <span>{article.title}</span>
          <time>{article.published}</time>
          <span>{article.claims}</span>
          <span>{article.official}</span>
          <span>{article.freshness}</span>
          <Verdict
            tone={article.status === "사실" || article.status === "대체로 사실" ? "positive" : article.status === "초기 기준" ? "warning" : "danger"}
          >
            {article.status}
          </Verdict>
        </div>
      ))}
    </div>
  );
}

function PerspectiveRows() {
  return (
    <div className="perspective-list">
      {perspectives.map((perspective, index) => (
        <div className="perspective-row" key={perspective.name}>
          <span className="row-index">{String.fromCharCode(65 + index)}</span>
          <div>
            <h3>{perspective.name}</h3>
            <p>{perspective.claim}</p>
          </div>
          <div>
            <small>근거</small>
            <span>{perspective.evidence}</span>
          </div>
          <div>
            <small>반론</small>
            <span>{perspective.objection}</span>
          </div>
          <div>
            <small>공통분모</small>
            <span>{perspective.common}</span>
          </div>
        </div>
      ))}
    </div>
  );
}

function Timeline() {
  const timeline = [
    ["14:10", "초기 보도", "일부 투표소 부족"],
    ["15:30", "후속 보도", "선관위 사과 예정 보도"],
    ["17:20", "수치 등장", "부족 투표소 14곳 보도"],
    ["다음날", "충돌 수치", "전국 50곳 부족 주장 등장"],
    ["현재", "공식 확인", "지역별 투표용지 인쇄 현황 공개"],
  ];
  return (
    <div className="timeline">
      {timeline.map(([time, label, text]) => (
        <div className="timeline-row" key={`${time}-${text}`}>
          <time>{time}</time>
          <span>{label}</span>
          <strong>{text}</strong>
        </div>
      ))}
    </div>
  );
}

function Sources() {
  const sources = [
    ["중앙선거관리위원회", "공식 보도자료", "2024-04-11", "0.94"],
    ["국회 행정안전위원회", "회의록", "2024-04-12", "0.88"],
    ["감사원", "감사 착수 발표", "2024-04-13", "0.82"],
    ["연합뉴스", "언론 보도", "2024-04-11", "0.73"],
  ];
  return (
    <div className="data-table">
      <div className="source-grid table-head">
        <span>출처</span>
        <span>자료 유형</span>
        <span>발행일</span>
        <span>신뢰도</span>
      </div>
      {sources.map(([name, type, date, score]) => (
        <div className="source-grid table-row static-row" key={name}>
          <strong>{name}</strong>
          <span>{type}</span>
          <time>{date}</time>
          <span>{score}</span>
        </div>
      ))}
    </div>
  );
}

function UserClaimForm() {
  return (
    <div className="structured-form">
      <label>
        <span>내 주장</span>
        <textarea placeholder="검증 가능한 주장이나 관점을 입력하세요." />
      </label>
      <label>
        <span>그렇게 생각하는 이유</span>
        <textarea placeholder="수치, 날짜, 기관명, 조건을 함께 적어주세요." />
      </label>
      <label>
        <span>근거 링크</span>
        <input placeholder="https://example.com/source" />
      </label>
      <div className="segmented">
        {["사실 주장", "해석/평가", "요구 사항", "운동 전략", "반박", "추가 근거"].map((type, index) => (
          <button key={type} className={index === 0 ? "is-active" : ""}>
            {type}
          </button>
        ))}
      </div>
      <button className="primary-action wide">
        <Tray size={18} />
        주장 제출
      </button>
    </div>
  );
}

function IssueTabContent({ activeTab }) {
  if (activeTab === "핵심 팩트") return <CoreFacts />;
  if (activeTab === "쟁점 지도") return <IssueMap />;
  if (activeTab === "주장별 검증") return <ClaimLedger />;
  if (activeTab === "기사별 비교") return <ArticleCompare />;
  if (activeTab === "관점별 주장") return <PerspectiveRows />;
  if (activeTab === "타임라인") return <Timeline />;
  if (activeTab === "원문 자료") return <Sources />;
  return <UserClaimForm />;
}

function UpdateRail() {
  return (
    <aside className="right-rail issue-update-rail">
      <section className="rail-section">
        <div className="section-line-title">
          <h2>실시간 업데이트</h2>
          <button className="text-command">전체</button>
        </div>
        {updates.map((update) => (
          <div className="update-row deep" key={`${update.time}-${update.text}`}>
            <time>{update.time}</time>
            <ToneDot tone={update.tone} />
            <span>
              <strong>{update.type}</strong>
              <small>{update.text}</small>
              <em>출처: {update.source}</em>
            </span>
          </div>
        ))}
      </section>
      <section className="rail-section">
        <div className="section-line-title">
          <h2>판정 원칙</h2>
        </div>
        <div className="principle-list">
          <span>기사 전체 판정 금지</span>
          <span>주장 단위 판정</span>
          <span>공식자료 우선</span>
          <span>법적 쟁점 자동 단정 금지</span>
        </div>
      </section>
    </aside>
  );
}

function IssueSidebar({ selectedIssueId, setSelectedIssueId }) {
  return (
    <aside className="topic-rail issue-list-rail">
      <div className="rail-heading">
        <span>이슈 탐색</span>
        <button className="text-command">필터</button>
      </div>
      <div className="topic-list issue-index">
        {issues.map((issue) => (
          <button
            key={issue.id}
            className={cx("issue-index-row", selectedIssueId === issue.id && "is-active")}
            onClick={() => setSelectedIssueId(issue.id)}
          >
            <span>{issue.title}</span>
            <small>{issue.updated} · 기사 {issue.articles}</small>
          </button>
        ))}
      </div>
      <div className="rail-section compact">
        <div className="section-line-title">
          <span>상태 기준</span>
        </div>
        <div className="legend-list">
          <span><ToneDot tone="positive" /> 사실/공식자료</span>
          <span><ToneDot tone="warning" /> 업데이트 필요</span>
          <span><ToneDot tone="danger" /> 근거 부족</span>
        </div>
      </div>
    </aside>
  );
}

function IssueScreen({ selectedIssueId, setSelectedIssueId }) {
  const [activeTab, setActiveTab] = useState("핵심 팩트");
  const issue = issues.find((item) => item.id === selectedIssueId) ?? issues[0];

  return (
    <div className="workspace three-column issue-workspace">
      <IssueSidebar selectedIssueId={issue.id} setSelectedIssueId={setSelectedIssueId} />
      <main className="issue-surface">
        <IssueHeader issue={issue} />
        <IssueTabs activeTab={activeTab} setActiveTab={setActiveTab} />
        <section className="tab-content" aria-live="polite">
          <IssueTabContent activeTab={activeTab} />
        </section>
      </main>
      <UpdateRail />
    </div>
  );
}

function MiniPhone({ setActiveSurface, setMobileTab }) {
  return (
    <button
      className="mini-phone"
      onClick={() => {
        setMobileTab("home");
        setActiveSurface("mobile");
      }}
      aria-label="모바일 앱 미리보기 열기"
    >
      <div className="phone-status">9:41</div>
      <div className="phone-title">FactTracer</div>
      <div className="phone-tabs">
        <span className="is-active">홈</span>
        <span>이슈</span>
        <span>검증</span>
        <span>알림</span>
      </div>
      <div className="phone-list">
        {issues.slice(0, 4).map((issue, index) => (
          <span key={issue.id}>
            <b>{index + 1}</b>
            <em>{issue.title}</em>
            <small>{issue.updated}</small>
          </span>
        ))}
      </div>
    </button>
  );
}

function MobileAppScreen({ mobileTab, setMobileTab, setSelectedIssueId, setActiveSurface }) {
  const tabs = [
    { id: "home", label: "홈" },
    { id: "issues", label: "이슈" },
    { id: "check", label: "검증하기" },
    { id: "alerts", label: "알림" },
    { id: "me", label: "내 정보" },
  ];

  return (
    <div className="mobile-workspace">
      <section className="mobile-stage">
        <div className="mobile-screen">
          <div className="mobile-statusbar">
            <span>9:41</span>
            <span>LTE 100%</span>
          </div>
          <header className="mobile-header">
            <strong>FactTracer</strong>
            <Bell size={20} />
          </header>
          <div className="mobile-content">
            {mobileTab === "home" && (
              <>
                <div className="mobile-section-title">
                  <span>실시간 이슈 TOP 5</span>
                  <button onClick={() => setMobileTab("issues")}>더보기</button>
                </div>
                {issues.slice(0, 5).map((issue, index) => (
                  <button
                    className="mobile-issue-row"
                    key={issue.id}
                    onClick={() => {
                      setSelectedIssueId(issue.id);
                      setActiveSurface("issue");
                    }}
                  >
                    <b>{index + 1}</b>
                    <span>
                      <strong>{issue.title}</strong>
                      <small>관련 기사 {issue.articles} · 주장 {issue.clusters}</small>
                    </span>
                    <time>{issue.updated}</time>
                  </button>
                ))}
              </>
            )}
            {mobileTab === "issues" && (
              <div className="mobile-list">
                {issues.map((issue) => (
                  <button key={issue.id} className="mobile-wide-row">
                    <span>{issue.title}</span>
                    <small>{issue.status} · {issue.evidence}</small>
                  </button>
                ))}
              </div>
            )}
            {mobileTab === "check" && (
              <div className="mobile-form">
                <label>
                  <span>기사 URL</span>
                  <input placeholder="https://news.example.com/article" />
                </label>
                <label>
                  <span>직접 입력</span>
                  <textarea placeholder="검증할 주장 또는 본문을 붙여넣으세요." />
                </label>
                <button>검증 요청</button>
              </div>
            )}
            {mobileTab === "alerts" && (
              <div className="mobile-list">
                {mobileAlerts.map((alert, index) => (
                  <div className="mobile-wide-row" key={alert}>
                    <span>{alert}</span>
                    <small>{index + 3}분 전 · 관심 이슈</small>
                  </div>
                ))}
              </div>
            )}
            {mobileTab === "me" && (
              <div className="mobile-list">
                {["관심 관점: 관리 책임", "저장한 리포트 8개", "제보한 근거 3건", "알림 설정"].map((item) => (
                  <button className="mobile-wide-row" key={item}>
                    <span>{item}</span>
                    <CaretRight size={16} />
                  </button>
                ))}
              </div>
            )}
          </div>
          <nav className="mobile-tabs">
            {tabs.map((tab) => (
              <button key={tab.id} className={mobileTab === tab.id ? "is-active" : ""} onClick={() => setMobileTab(tab.id)}>
                {tab.label}
              </button>
            ))}
          </nav>
        </div>
      </section>
      <aside className="mobile-notes">
        <div className="surface-title-row">
          <div>
            <h1>알림 우선순위</h1>
            <p>관심 이슈의 상태 변화만 압축해서 전달합니다.</p>
          </div>
        </div>
        <div className="mobile-spec-list">
          <div>
            <strong>공식자료 등장</strong>
            <span>선관위 설명자료 감지 · 푸시 대상</span>
          </div>
          <div>
            <strong>새 수치 충돌</strong>
            <span>14곳, 50곳 수치 클러스터 재계산</span>
          </div>
          <div>
            <strong>판정 변경</strong>
            <span>초기 기준에서 업데이트 필요로 변경</span>
          </div>
        </div>
      </aside>
    </div>
  );
}

function AdminSidebar({ adminTab, setAdminTab }) {
  const groups = [
    ["검토 관리", ["관리자 검토 큐", "재검증 관리", "승인 이력", "정책 및 기준"]],
    ["데이터 관리", ["이슈 관리", "출처 관리", "언론사 관리", "문서 관리"]],
    ["모델/에이전트", ["에이전트 모니터링", "프롬프트 관리", "모델 성능"]],
    ["통계/리포트", ["검증 통계", "이용 리포트", "리스크 리포트"]],
  ];
  return (
    <aside className="admin-sidebar">
      {groups.map(([group, items]) => (
        <div className="admin-nav-group" key={group}>
          <strong>{group}</strong>
          {items.map((item) => (
            <button key={item} className={adminTab === item ? "is-active" : ""} onClick={() => setAdminTab(item)}>
              <ListChecks size={17} />
              <span>{item}</span>
            </button>
          ))}
        </div>
      ))}
    </aside>
  );
}

function AdminScreen() {
  const [adminTab, setAdminTab] = useState("관리자 검토 큐");
  const [selectedAdminId, setSelectedAdminId] = useState(adminRows[0].id);
  const selected = adminRows.find((row) => row.id === selectedAdminId) ?? adminRows[0];

  return (
    <div className="admin-workspace">
      <AdminSidebar adminTab={adminTab} setAdminTab={setAdminTab} />
      <main className="admin-main">
        <div className="surface-title-row admin-title">
          <div>
            <h1>{adminTab}</h1>
            <p>검토가 필요한 항목을 확인하고 공개, 보류, 재검증을 처리합니다.</p>
          </div>
          <button className="filter-control">
            <SlidersHorizontal size={16} />
            작업 기준
          </button>
        </div>
        <div className="admin-tabs">
          {["이슈 후보", "신고된 주장", "에이전트 로그", "재검증"].map((tab, index) => (
            <button className={index === 0 ? "is-active" : ""} key={tab}>
              {tab}
            </button>
          ))}
        </div>
        <div className="admin-filters">
          <button>전체 상태 <CaretDown size={14} /></button>
          <button>전체 주제 <CaretDown size={14} /></button>
          <button>전체 언론사 <CaretDown size={14} /></button>
          <label>
            <input placeholder="키워드 검색" />
            <MagnifyingGlass size={16} />
          </label>
        </div>
        <div className="admin-table">
          <div className="admin-grid table-head">
            <span>ID</span>
            <span>이슈 제목</span>
            <span>주제</span>
            <span>언론 보도량</span>
            <span>첫 감지</span>
            <span>상태</span>
            <span>우선순위</span>
            <span>작업</span>
          </div>
          {adminRows.map((row) => (
            <button
              className={cx("admin-grid table-row", selectedAdminId === row.id && "is-selected")}
              key={row.id}
              onClick={() => setSelectedAdminId(row.id)}
            >
              <span>{row.id}</span>
              <strong>{row.title}</strong>
              <span>{row.topic}</span>
              <span>{row.articles}</span>
              <time>{row.firstSeen}</time>
              <Verdict tone={row.status === "검토 중" ? "warning" : "info"}>{row.status}</Verdict>
              <span className={row.priority === "높음" ? "priority-high" : ""}>{row.priority}</span>
              <span className="link-like">열기</span>
            </button>
          ))}
        </div>
        <div className="admin-detail">
          <section>
            <span className="eyebrow">{selected.id}</span>
            <h2>{selected.title}</h2>
            <div className="metric-line">
              <span>첫 감지 <strong>{selected.firstSeen}</strong></span>
              <span>관련 기사 <strong>{selected.articles}</strong></span>
              <span>주장 클러스터 <strong>18개</strong></span>
              <span>민감도 <strong>{selected.priority}</strong></span>
            </div>
            <ClaimLedger />
          </section>
          <aside>
            <h3>검토 작업</h3>
            <label>
              <span>우선순위</span>
              <select defaultValue={selected.priority}>
                <option>높음</option>
                <option>중간</option>
                <option>낮음</option>
              </select>
            </label>
            <label>
              <span>검토 담당자</span>
              <select defaultValue="- 미배정 -">
                <option>- 미배정 -</option>
                <option>리서처 A</option>
                <option>검토자 B</option>
              </select>
            </label>
            <label>
              <span>검토 메모</span>
              <textarea placeholder="메모를 입력하세요..." />
            </label>
            <button className="primary-action wide">검토 열기</button>
            <button className="secondary-action wide">재검증 실행</button>
            <div className="admin-log-list">
              <h3>이력</h3>
              {adminLogs.map((log) => (
                <span key={log}>{log}</span>
              ))}
            </div>
          </aside>
        </div>
      </main>
    </div>
  );
}

function RequestDrawer({ open, onClose }) {
  const [mode, setMode] = useState("url");
  return (
    <div className={cx("drawer-backdrop", open && "is-open")} aria-hidden={!open}>
      <aside className="request-drawer" role="dialog" aria-label="검증 요청">
        <div className="drawer-head">
          <div>
            <h2>직접 검증 요청</h2>
            <p>URL, 텍스트, 이미지/PDF, 유튜브 링크를 기존 이슈와 매칭합니다.</p>
          </div>
          <button className="icon-command" onClick={onClose} aria-label="닫기">
            <X size={20} />
          </button>
        </div>
        <div className="segmented">
          {[
            ["url", "기사 URL"],
            ["text", "텍스트"],
            ["file", "이미지/PDF"],
            ["video", "유튜브"],
          ].map(([id, label]) => (
            <button key={id} className={mode === id ? "is-active" : ""} onClick={() => setMode(id)}>
              {label}
            </button>
          ))}
        </div>
        <label className="drawer-field">
          <span>{mode === "url" ? "기사 URL" : mode === "text" ? "검증할 텍스트" : mode === "file" ? "파일 설명" : "유튜브 링크"}</span>
          {mode === "text" ? (
            <textarea placeholder="검증할 주장, 수치, 출처 문장을 붙여넣으세요." />
          ) : (
            <input placeholder={mode === "file" ? "업로드 파일은 프로토타입에서 생략됩니다." : "https://example.com"} />
          )}
        </label>
        <label className="drawer-field">
          <span>관련 쟁점</span>
          <select>
            <option>자동 매칭</option>
            <option>부족 투표소 수</option>
            <option>원인</option>
            <option>책임 소재</option>
            <option>운동 전략</option>
          </select>
        </label>
        <div className="process-list">
          {["욕설/낙인 필터링", "주장 유형 분류", "기존 클러스터 유사도 비교", "검토 큐 등록"].map((step, index) => (
            <span key={step}>
              <CheckCircle size={16} weight={index < 2 ? "fill" : "regular"} />
              {step}
            </span>
          ))}
        </div>
        <button className="primary-action wide" onClick={onClose}>검증 요청 제출</button>
      </aside>
    </div>
  );
}

export function App() {
  const [activeSurface, setActiveSurface] = useState("home");
  const [activeTopic, setActiveTopic] = useState("all");
  const [selectedIssueId, setSelectedIssueId] = useState("election-paper");
  const [mobileTab, setMobileTab] = useState("home");
  const [requestOpen, setRequestOpen] = useState(false);

  return (
    <div className="app">
      <AppHeader
        activeSurface={activeSurface}
        setActiveSurface={setActiveSurface}
        onRequestOpen={() => setRequestOpen(true)}
      />
      {activeSurface === "home" && (
        <HomeScreen
          activeTopic={activeTopic}
          setActiveTopic={setActiveTopic}
          selectedIssueId={selectedIssueId}
          setSelectedIssueId={setSelectedIssueId}
          setActiveSurface={setActiveSurface}
          onRequestOpen={() => setRequestOpen(true)}
          setMobileTab={setMobileTab}
        />
      )}
      {activeSurface === "issue" && (
        <IssueScreen selectedIssueId={selectedIssueId} setSelectedIssueId={setSelectedIssueId} />
      )}
      {activeSurface === "mobile" && (
        <MobileAppScreen
          mobileTab={mobileTab}
          setMobileTab={setMobileTab}
          setSelectedIssueId={setSelectedIssueId}
          setActiveSurface={setActiveSurface}
        />
      )}
      {activeSurface === "admin" && <AdminScreen />}
      <RequestDrawer open={requestOpen} onClose={() => setRequestOpen(false)} />
    </div>
  );
}
