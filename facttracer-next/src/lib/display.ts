const statusLabel: Record<string, string> = {
  blocked: "보류",
  completed: "확인됨",
  dismissed: "기각",
  high: "높음",
  low: "낮음",
  medium: "중간",
  merged: "기존 쟁점 보강",
  needs_review: "최신화 필요",
  open: "접수",
  queued: "접수됨",
  received: "접수됨",
  resolved: "확인됨",
  running: "검토 중",
  trusted: "신뢰",
  updated: "최신화 필요",
  verified: "확인됨",
  watch: "검토 중",
};

const sourceTypeLabel: Record<string, string> = {
  community: "커뮤니티",
  law: "법령",
  media: "언론",
  news: "언론",
  news_search: "언론 검색",
  official: "공식",
  public: "공공자료",
  rss: "RSS",
  social: "SNS",
  statistics: "통계",
  youtube: "YouTube",
};

const claimTypeLabel: Record<string, string> = {
  "추가 근거": "추가 근거 제보",
  "추가 근거 제보": "추가 근거 제보",
  "법적 판단": "해석/평가",
  "법적 주장": "법적 주장",
  "사실 주장": "사실 주장",
  "시점": "사실 주장",
  "수치": "수치 주장",
  "수치 주장": "수치 주장",
  "원인 해석": "원인 해석",
  "책임 주장": "책임 주장",
  "요구 사항": "요구 사항",
  "운동 전략": "운동 전략",
  "의혹 주장": "의혹 주장",
  "낙인 표현": "낙인 표현",
  "인과관계": "해석/평가",
  "인용": "사실 주장",
  "정책 요구": "요구 사항",
  "해석": "해석/평가",
  "해석/평가": "해석/평가",
  "반박": "반박",
  "기타": "추가 근거 제보",
};

const targetTypeLabel: Record<string, string> = {
  claim: "주장",
  comment: "표현",
  issue: "이슈",
  source: "출처",
};

const processingNameLabel: Record<string, string> = {
  "Claim Clusterer": "쟁점 묶음",
  "Evidence Ranker": "근거 우선순위",
  "Evidence Retriever": "근거 연결",
  Collector: "수집",
  Deduplicator: "중복 제거",
  "Harmful Label Filter": "낙인 표현 필터링",
};

export function formatStatus(value?: string | null) {
  if (!value) return "";
  return statusLabel[value] ?? value;
}

export function formatSourceType(value?: string | null) {
  if (!value) return "";
  return sourceTypeLabel[value] ?? value;
}

export function formatClaimType(value?: string | null) {
  if (!value) return "사실 주장";
  return claimTypeLabel[value] ?? value;
}

export function formatTargetType(value?: string | null) {
  if (!value) return "";
  return targetTypeLabel[value] ?? value;
}

export function formatProcessingName(value: string) {
  const trimmed = value.replace(/\s*Agent$/i, "").trim();
  return processingNameLabel[trimmed] ?? trimmed;
}

export function formatDateTime(value?: string | null, fallback = "시점 확인 전") {
  if (!value) return fallback;

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;

  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const hour = String(date.getHours()).padStart(2, "0");
  const minute = String(date.getMinutes()).padStart(2, "0");

  return `${year}.${month}.${day} ${hour}:${minute}`;
}

export function formatUpdatedAt(value?: string | null) {
  const formatted = formatDateTime(value, "업데이트 확인 전");
  return formatted === value ? value : `${formatted} 업데이트`;
}

export function formatCredibility(value?: number | null) {
  if (typeof value !== "number") return "근거 일치도 확인 전";
  if (value >= 0.8) return "근거 일치도 높음";
  if (value >= 0.55) return "근거 일치도 보통";
  return "추가 근거 필요";
}

export function formatEvidenceCount(count?: number | null) {
  if (!count) return "공식 근거 확인 전";
  return `공식 근거 ${count}개 확인`;
}

export function sourceTypeTone(value?: string | null) {
  switch (value) {
    case "official":
    case "public":
      return "text-emerald-600";
    case "statistics":
    case "law":
      return "text-blue-600";
    case "media":
    case "news":
    case "news_search":
    case "rss":
      return "text-gray-700";
    case "social":
    case "youtube":
      return "text-amber-600";
    default:
      return "text-gray-600";
  }
}
