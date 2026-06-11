import Link from "next/link";
import { ExternalLink } from "lucide-react";
import { Fragment, type ReactNode } from "react";
import { StatusBadge } from "@/components/status-badge";
import type {
  ArticleComparison,
  Claim,
  ClaimCluster,
  ConfirmedFact,
  IssueDetail,
  IssueTimelineEvent,
  NumberChangeEvent,
  Perspective,
  SourceDocument,
} from "@/lib/api/types";
import {
  formatClaimType,
  formatCredibility,
  formatDateTime,
  formatEvidenceCount,
  formatSourceType,
  sourceTypeTone,
} from "@/lib/display";

const claimTypeOrder = [
  "사실 주장",
  "수치 주장",
  "원인 해석",
  "책임 주장",
  "법적 주장",
  "해석/평가",
  "요구 사항",
  "운동 전략",
  "의혹 주장",
  "낙인 표현",
  "반박",
  "추가 근거 제보",
];

function DossierSection({
  children,
  description,
  eyebrow,
  id,
  title,
}: {
  children: ReactNode;
  description: string;
  eyebrow: string;
  icon?: ReactNode;
  id: string;
  title: string;
}) {
  return (
    <section id={id} className="py-7">
      <header>
        <p className="text-sm font-medium text-blue-600">
          {eyebrow}
        </p>
        <h2 className="mt-2 text-[30px] font-bold leading-tight tracking-normal text-gray-950">
          {title}
        </h2>
        <p className="mt-3 max-w-[760px] text-[15px] leading-7 text-gray-700">
          {description}
        </p>
      </header>
      <div className="mt-6 min-w-0">{children}</div>
    </section>
  );
}

function DossierFrame({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`min-w-0 overflow-hidden rounded-[3px] border border-gray-200 bg-white ${className}`}
    >
      {children}
    </div>
  );
}

function EmptyFrame({ children }: { children: ReactNode }) {
  return (
    <DossierFrame>
      <p className="px-4 py-5 text-sm leading-7 text-gray-500">{children}</p>
    </DossierFrame>
  );
}

function LegendDot({
  color,
  label,
}: {
  color: "blue" | "red" | "green" | "gray";
  label: string;
}) {
  const colorClassName = {
    blue: "bg-blue-700",
    gray: "bg-gray-400",
    green: "bg-emerald-600",
    red: "bg-red-600",
  }[color];

  return (
    <span className="inline-flex items-center gap-2 text-sm text-gray-700">
      <span className={`size-3 rounded-full ${colorClassName}`} aria-hidden="true" />
      {label}
    </span>
  );
}

export function IssueMetricStrip({ issue }: { issue: IssueDetail }) {
  return (
    <div className="mt-6 flex flex-wrap gap-8">
      <IssueMetric label="수집 기사" value={issue.articleCount} />
      <IssueMetric label="쟁점 묶음" value={issue.clusterCount} />
      <IssueMetric label="검증 완료" value={issue.verifiedCount} />
      <IssueMetric label="추가 확인" value={issue.needsReviewCount} />
    </div>
  );
}

export function IssueMetric({
  label,
  value,
}: {
  label: string;
  value: number | string;
}) {
  return (
    <div>
      <p className="text-2xl font-semibold tabular-nums text-gray-900">
        {value}
      </p>
      <p className="mt-1 text-xs text-gray-500">{label}</p>
    </div>
  );
}

export function ConfirmedFactList({
  facts,
  sources = [],
  title = "핵심 팩트",
}: {
  facts: ConfirmedFact[];
  sources?: SourceDocument[];
  title?: string;
}) {
  return (
    <DossierSection
      description="공식 자료와 교차 확인된 내용만 먼저 분리합니다."
      eyebrow="핵심 팩트"
      id="facts"
      title={title}
    >
      {facts.length > 0 ? (
        <DossierFrame>
          <div className="max-w-full overflow-x-auto">
            <table className="w-full min-w-[820px] border-collapse text-left text-sm">
              <thead className="bg-gray-50 text-xs font-semibold text-gray-700">
                <tr>
                  <th className="w-36 border-b border-r border-gray-200 px-4 py-3">항목</th>
                  <th className="border-b border-r border-gray-200 px-4 py-3">확인된 내용</th>
                  <th className="w-64 border-b border-r border-gray-200 px-4 py-3">공식 근거</th>
                  <th className="w-24 border-b border-gray-200 px-4 py-3">판정</th>
                </tr>
              </thead>
              <tbody>
                {facts.map((fact, index) => {
                  const source = sources[index % Math.max(sources.length, 1)];

                  return (
                    <tr key={`${fact.label}-${fact.text}-${index}`} className="align-top">
                      <td className="border-b border-r border-gray-100 px-4 py-3 font-medium text-gray-900">
                        {fact.label}
                      </td>
                      <td className="border-b border-r border-gray-100 px-4 py-3 leading-6 text-gray-700">
                        {fact.text}
                      </td>
                      <td className="border-b border-r border-gray-100 px-4 py-3 text-gray-600">
                        {source ? (
                          <>
                            <span className="block font-medium text-gray-800">
                              {source.publisher}
                            </span>
                            <span className="mt-1 block text-xs leading-5 text-gray-500">
                              {source.title}
                            </span>
                          </>
                        ) : (
                          "공식 근거 대조 중"
                        )}
                      </td>
                      <td className="border-b border-gray-100 px-4 py-3">
                        <StatusBadge tone={fact.tone}>{fact.verdict}</StatusBadge>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="grid border-t border-gray-200 md:grid-cols-[180px_minmax(0,1fr)]">
            <div className="border-b border-gray-100 bg-gray-50 px-4 py-4 text-sm font-semibold text-gray-950 md:border-b-0 md:border-r">
              아직 확인 전
            </div>
            <div className="grid gap-2 px-4 py-4 text-sm leading-6 text-gray-600">
              <p>새 공식 발표와 반론 자료가 나오면 판정이 바뀔 수 있습니다.</p>
              <p>익명 제보나 SNS 출처만 있는 내용은 별도 검증 전까지 보류합니다.</p>
            </div>
          </div>
        </DossierFrame>
      ) : (
        <EmptyFrame>
          공식 근거로 확인된 팩트가 아직 없습니다.
        </EmptyFrame>
      )}
    </DossierSection>
  );
}

export function IssueDebateMap({
  clusters,
  facts = [],
}: {
  clusters: ClaimCluster[];
  facts?: ConfirmedFact[];
}) {
  return (
    <DossierSection
      description="주장, 반론, 확인된 사실, 아직 모르는 부분을 쟁점 단위로 분리합니다."
      eyebrow="쟁점 지도"
      id="map"
      title="쟁점 지도"
    >
      {clusters.length > 0 ? (
        <>
          <div className="mb-5 flex flex-wrap gap-x-8 gap-y-3">
            <LegendDot color="blue" label="주장 A" />
            <LegendDot color="red" label="주장 B" />
            <LegendDot color="green" label="확인된 사실" />
            <LegendDot color="gray" label="미해결 질문" />
          </div>
          <DossierFrame>
            <div className="max-w-full overflow-x-auto">
              <table className="w-full min-w-[920px] border-collapse text-left text-sm">
                <thead className="bg-gray-50 text-xs font-semibold text-gray-700">
                  <tr>
                    <th className="w-28 border-b border-r border-gray-200 px-4 py-3 text-center">쟁점</th>
                    <th className="border-b border-r border-gray-200 px-4 py-3 text-blue-700">
                      주장 A
                    </th>
                    <th className="w-56 border-b border-r border-gray-200 px-4 py-3">
                      충돌 지점
                    </th>
                    <th className="w-64 border-b border-r border-gray-200 px-4 py-3">
                      확인된 사실
                    </th>
                    <th className="border-b border-gray-200 px-4 py-3 text-red-700">
                      주장 B
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {clusters.map((cluster, index) => (
                    <DebateCluster
                      key={`${cluster.title}-${index}`}
                      cluster={cluster}
                      confirmedFact={facts[index]}
                      index={index}
                    />
                  ))}
                </tbody>
              </table>
            </div>
            <p className="border-t border-gray-200 px-4 py-3 text-xs leading-5 text-gray-500">
              ※ 확인된 사실은 현재 공개된 자료 기준이며, 새 공식 발표와 반론 자료에 따라 변경될 수 있습니다.
            </p>
          </DossierFrame>
        </>
      ) : (
        <EmptyFrame>
          쟁점 묶음이 없습니다.
        </EmptyFrame>
      )}
    </DossierSection>
  );
}

function DebateCluster({
  cluster,
  confirmedFact,
  index,
}: {
  cluster: ClaimCluster;
  confirmedFact?: ConfirmedFact;
  index: number;
}) {
  const primaryClaims = cluster.claims.slice(0, 2);

  return (
    <Fragment>
      <tr className="align-top">
        <td className="border-b border-r border-gray-200 px-4 py-5 text-center">
          <p className="text-[22px] font-medium tabular-nums text-gray-700">
            {String(index + 1).padStart(2, "0")}
          </p>
          <h3 className="mt-1 font-semibold leading-6 text-gray-950">
            {cluster.title}
          </h3>
        </td>
        <td className="border-b border-r border-gray-200 px-5 py-5 leading-7 text-gray-700">
          <span className="block font-bold text-blue-700">
            {primaryClaims[0] ?? "등록된 첫 번째 주장이 없습니다."}
          </span>
          <span className="mt-3 block text-gray-600">{cluster.question}</span>
        </td>
        <td className="border-b border-r border-gray-200 px-5 py-5 leading-7 text-gray-700">
          <span className="font-semibold text-gray-950">{cluster.conflict}</span>
        </td>
        <td className="border-b border-r border-gray-200 px-5 py-5 leading-7 text-gray-700">
          <span className="font-semibold text-emerald-700">
            {confirmedFact?.text ?? cluster.commonGround}
          </span>
          <span className="mt-3 block">
            <StatusBadge tone={cluster.tone}>{cluster.verdict}</StatusBadge>
          </span>
        </td>
        <td className="border-b border-gray-200 px-5 py-5 leading-7 text-gray-700">
          <span className="block font-bold text-red-700">
            {primaryClaims[1] ?? "비교할 반론이 아직 없습니다."}
          </span>
          <span className="mt-3 block text-gray-600">
            기존 자료만으로 결론을 유지해야 한다는 입장입니다.
          </span>
        </td>
      </tr>
      <tr className="bg-gray-50/80 text-sm">
        <td className="border-b border-r border-gray-200 px-4 py-3 text-center font-medium text-gray-500">
          보충
        </td>
        <td className="border-b border-r border-gray-200 px-5 py-3 leading-6 text-gray-700" colSpan={2}>
          <span className="font-semibold text-gray-950">공통분모</span>
          <span className="ml-3">{cluster.commonGround}</span>
        </td>
        <td className="border-b border-gray-200 px-5 py-3 leading-6 text-gray-700" colSpan={2}>
          <span className="font-semibold text-gray-950">미해결 질문</span>
          <span className="ml-3">어떤 공식 자료가 나오면 현재 판정이 바뀌는가?</span>
        </td>
      </tr>
    </Fragment>
  );
}

export function PerspectiveClaims({
  perspectives,
}: {
  perspectives: Perspective[];
}) {
  return (
    <DossierSection
      description="진영 라벨 대신 주장 유형과 반박 가능 지점을 기준으로 정리합니다."
      eyebrow="관점"
      id="perspectives"
      title="관점별 주장"
    >
      {perspectives.length > 0 ? (
        <div className="grid gap-5">
          <DossierFrame>
            <div className="grid divide-y divide-gray-200 md:grid-cols-3 md:divide-x md:divide-y-0">
            {perspectives.slice(0, 3).map((perspective) => (
              <section
                key={perspective.name}
                className="p-5"
              >
                <h3 className="text-lg font-bold text-gray-950">{perspective.name}</h3>
                <dl className="mt-4 grid gap-4 text-sm leading-6">
                  <PerspectiveField label="핵심 주장" value={perspective.core} />
                  <PerspectiveField label="주로 쓰는 근거" value={perspective.uses} />
                  <PerspectiveField
                    label="반박받는 지점"
                    value={perspective.challengedBy}
                  />
                  <PerspectiveField
                    label="공통분모"
                    value={perspective.commonGround}
                  />
                </dl>
              </section>
            ))}
            </div>
          </DossierFrame>

          <DossierFrame>
            <div className="grid divide-y divide-gray-200 md:grid-cols-2 md:divide-x md:divide-y-0">
              <div className="p-5">
                <h3 className="text-sm font-semibold text-gray-950">공통 확인 기준</h3>
                <p className="mt-2 text-sm leading-6 text-gray-600">
                  공식 문서, 표결 기록, 당사자 발표, 후속 보도를 같은 기준으로 대조합니다.
                </p>
              </div>
              <div className="p-5">
                <h3 className="text-sm font-semibold text-gray-950">표현 정제</h3>
                <p className="mt-2 text-sm leading-6 text-gray-600">
                  낙인성 표현은 진영 라벨이 아니라 주장 유형과 반박 가능 지점으로 재분류합니다.
                </p>
              </div>
            </div>
          </DossierFrame>
          </div>
      ) : (
        <EmptyFrame>
          관점별 주장이 아직 분류되지 않았습니다.
        </EmptyFrame>
      )}
    </DossierSection>
  );
}

function PerspectiveField({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div>
      <dt className="text-xs font-medium text-gray-500">{label}</dt>
      <dd className="mt-1 text-gray-700">{value}</dd>
    </div>
  );
}

export function ClaimVerificationList({ claims }: { claims: Claim[] }) {
  const grouped = new Map<string, Claim[]>();

  claims.forEach((claim) => {
    const type = formatClaimType(claim.type);
    grouped.set(type, [...(grouped.get(type) ?? []), claim]);
  });

  const orderedClaimTypes = [
    ...claimTypeOrder,
    ...[...grouped.keys()].filter((type) => !claimTypeOrder.includes(type)),
  ].filter((type) => grouped.has(type));

  return (
    <DossierSection
      description="주장 유형, 판정, 관련 기사, 근거, 반박, 업데이트 이력을 함께 봅니다."
      eyebrow="주장 검증"
      id="claims"
      title="주장별 검증"
    >
      {orderedClaimTypes.length > 0 ? (
        <div>
          <div className="mb-4 flex flex-wrap gap-2 border-b border-gray-200 pb-3">
            {["전체", ...orderedClaimTypes.slice(0, 4)].map((type, index) => (
              <span
                key={type}
                className={`border-b-2 px-1 pb-2 text-sm font-medium ${
                  index === 0 ? "text-blue-600" : "text-gray-600"
                } ${index === 0 ? "border-blue-600" : "border-transparent"}
                `}
              >
                {type}
              </span>
            ))}
          </div>

          <DossierFrame>
            <div className="max-w-full overflow-x-auto">
              <table className="w-full min-w-[980px] border-collapse text-left text-sm">
                <thead className="bg-gray-50 text-xs font-semibold text-gray-700">
                  <tr>
                    <th className="border-b border-r border-gray-200 px-4 py-3">주장</th>
                    <th className="w-28 border-b border-r border-gray-200 px-4 py-3">유형</th>
                    <th className="w-24 border-b border-r border-gray-200 px-4 py-3">판정</th>
                    <th className="w-64 border-b border-r border-gray-200 px-4 py-3">근거</th>
                    <th className="w-64 border-b border-r border-gray-200 px-4 py-3">반박 가능 지점</th>
                    <th className="w-28 border-b border-gray-200 px-4 py-3">업데이트</th>
                  </tr>
                </thead>
                <tbody>
                  {claims.slice(0, 8).map((claim, index) => (
                    <tr
                      key={claim.id ?? `${claim.type}-${claim.text}-${index}`}
                      className="align-top"
                    >
                      <td className="border-b border-r border-gray-100 px-4 py-3 leading-6 text-gray-800">
                        {claim.text}
                      </td>
                      <td className="border-b border-r border-gray-100 px-4 py-3 text-gray-600">
                        {formatClaimType(claim.type)}
                      </td>
                      <td className="border-b border-r border-gray-100 px-4 py-3">
                        <StatusBadge tone={claim.tone}>{claim.verdict}</StatusBadge>
                      </td>
                      <td className="border-b border-r border-gray-100 px-4 py-3 leading-6 text-gray-600">
                        {claim.evidence}
                        <span className="mt-1 block text-xs text-gray-500">
                          {formatCredibility(claim.confidence)}
                        </span>
                      </td>
                      <td className="border-b border-r border-gray-100 px-4 py-3 leading-6 text-gray-600">
                        {claim.rebuttals?.[0] ?? "반박 가능 지점 대조 중"}
                      </td>
                      <td className="border-b border-gray-100 px-4 py-3 text-xs leading-5 text-gray-500">
                        {claim.updateHistory?.[0]
                          ? formatDateTime(claim.updateHistory[0].changedAt)
                          : claim.status || "변경 없음"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </DossierFrame>

          <ClaimVerificationDetails claim={claims[0]} expanded />
        </div>
      ) : (
        <EmptyFrame>
          검증할 주장이 아직 정리되지 않았습니다.
        </EmptyFrame>
      )}
    </DossierSection>
  );
}

function ClaimVerificationDetails({
  claim,
  expanded = false,
}: {
  claim: Claim;
  expanded?: boolean;
}) {
  const relatedArticles = claim.relatedArticles ?? [];
  const evidences = claim.evidences ?? [];
  const rebuttals = claim.rebuttals ?? [];
  const history = claim.updateHistory ?? [];

  if (
    relatedArticles.length === 0 &&
    evidences.length === 0 &&
    rebuttals.length === 0 &&
    history.length === 0
  ) {
    return null;
  }

  return (
    <DossierFrame className={expanded ? "mt-5" : "mt-4"}>
      {expanded ? (
        <div className="border-b border-gray-200 bg-gray-50 px-4 py-4">
          <p className="text-sm font-semibold text-gray-950">선택 주장 상세</p>
          <p className="mt-1 text-sm leading-6 text-gray-700">{claim.text}</p>
        </div>
      ) : null}
      <div className="grid text-xs leading-5 text-gray-600 md:grid-cols-2">
        {relatedArticles.length > 0 ? (
          <DetailGroup label="관련 기사">
            {relatedArticles.slice(0, 3).map((article) => (
              <a
                key={article.id}
                href={article.url}
                target="_blank"
                rel="noreferrer"
                className="font-medium text-gray-700 hover:text-blue-600"
              >
                {article.title} · {article.outlet} · 보도{" "}
                {formatDateTime(article.publishedAt)}
              </a>
            ))}
          </DetailGroup>
        ) : null}

        {evidences.length > 0 ? (
          <DetailGroup label="근거 자료">
            {evidences.slice(0, 3).map((evidence) => (
              <a
                key={evidence.id}
                href={evidence.url}
                target="_blank"
                rel="noreferrer"
                className="font-medium text-gray-700 hover:text-blue-600"
              >
                {evidence.title} · {formatSourceType(evidence.sourceType)}
              </a>
            ))}
          </DetailGroup>
        ) : null}

        {rebuttals.length > 0 ? (
          <DetailGroup label="반박/충돌 주장">
            {rebuttals.slice(0, 3).map((rebuttal) => (
              <span key={rebuttal}>{rebuttal}</span>
            ))}
          </DetailGroup>
        ) : null}

        {history.length > 0 ? (
          <DetailGroup label="업데이트 이력">
            {history.slice(0, 3).map((event) => (
              <span key={event.id}>
                변경: {event.previousVerdict || "이전 판정"} → {event.currentVerdict}{" "}
                (확인 {formatDateTime(event.changedAt)})
              </span>
            ))}
          </DetailGroup>
        ) : null}
      </div>
    </DossierFrame>
  );
}

function DetailGroup({
  children,
  label,
}: {
  children: ReactNode;
  label: string;
}) {
  return (
    <div className="border-b border-r border-gray-100 p-4">
      <p className="font-semibold text-gray-500">{label}</p>
      <div className="mt-2 grid gap-1.5">{children}</div>
    </div>
  );
}

export function ArticleComparisonTable({
  articles,
}: {
  articles: ArticleComparison[];
}) {
  return (
    <DossierSection
      description="기사마다 어떤 주장과 공식 근거를 담고 있는지 표로 비교합니다."
      eyebrow="기사 비교"
      id="articles"
      title="기사별 검증 비교"
    >
      {articles.length > 0 ? (
        <DossierFrame>
          <div className="max-w-full overflow-x-auto">
            <table className="w-full min-w-[1080px] border-collapse text-left text-sm">
              <thead className="bg-gray-50 text-xs font-semibold text-gray-700">
                <tr>
                  <th className="w-28 border-b border-r border-gray-200 px-4 py-3">언론사</th>
                  <th className="border-b border-r border-gray-200 px-4 py-3">기사 제목</th>
                  <th className="w-36 border-b border-r border-gray-200 px-4 py-3">보도 시각</th>
                  <th className="w-64 border-b border-r border-gray-200 px-4 py-3">핵심 관점</th>
                  <th className="w-24 border-b border-r border-gray-200 px-4 py-3">포함 주장</th>
                  <th className="w-24 border-b border-r border-gray-200 px-4 py-3">공식 근거</th>
                  <th className="w-32 border-b border-r border-gray-200 px-4 py-3">업데이트</th>
                  <th className="w-24 border-b border-gray-200 px-4 py-3">판정</th>
                </tr>
              </thead>
              <tbody>
                {articles.map((article) => (
                  <tr key={article.id} className="align-top hover:bg-gray-50">
                    <td className="border-b border-r border-gray-100 px-4 py-4 font-bold text-gray-900">
                      {article.outlet}
                    </td>
                    <td className="border-b border-r border-gray-100 px-4 py-4">
                      <a
                        href={article.url}
                        target="_blank"
                        rel="noreferrer"
                        className="font-medium leading-6 text-gray-900 hover:text-blue-600"
                      >
                        {article.title}
                      </a>
                    </td>
                    <td className="border-b border-r border-gray-100 px-4 py-4 text-gray-600">
                      {formatDateTime(article.publishedAt)}
                    </td>
                    <td className="border-b border-r border-gray-100 px-4 py-4 leading-6 text-gray-600">
                      {article.note}
                    </td>
                    <td className="border-b border-r border-gray-100 px-4 py-4 text-gray-600">
                      주장 {article.claimCount}개
                    </td>
                    <td className="border-b border-r border-gray-100 px-4 py-4 text-gray-600">
                      {formatEvidenceCount(article.officialSourceCount)}
                    </td>
                    <td className="border-b border-r border-gray-100 px-4 py-4 text-gray-600">
                      {article.outdatedClaims > 0
                        ? `${article.outdatedClaims}개 최신화 필요`
                        : "현재 기준 유지"}
                    </td>
                    <td className="border-b border-gray-100 px-4 py-4">
                      <StatusBadge tone={article.tone}>{article.verdict}</StatusBadge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="grid border-t border-gray-200 md:grid-cols-4 md:divide-x md:divide-gray-200">
            <ArticleDetail label="보도 요지" value={articles[0]?.note} />
            <ArticleDetail
              label="빠진 근거"
              value={
                articles[0]?.officialSourceCount
                  ? "공식 근거 일부 반영"
                  : "공식 근거 확인 전"
              }
            />
            <ArticleDetail
              label="업데이트 필요 지점"
              value={
                articles[0]?.outdatedClaims
                  ? `${articles[0].outdatedClaims}개 주장 최신화 필요`
                  : "현재 기준 유지"
              }
            />
            <a
              href={articles[0]?.url}
              target="_blank"
              rel="noreferrer"
              className="px-4 py-4 text-sm font-medium text-blue-600 hover:underline"
            >
              원문 열기
            </a>
          </div>
        </DossierFrame>
      ) : (
        <EmptyFrame>
          비교할 기사가 없습니다.
        </EmptyFrame>
      )}
    </DossierSection>
  );
}

function ArticleDetail({
  label,
  value,
}: {
  label: string;
  value?: string | number;
}) {
  return (
    <div className="px-4 py-4">
      <p className="text-xs font-medium text-gray-500">{label}</p>
      <p className="mt-1 text-sm leading-6 text-gray-700">
        {value || "확인 전"}
      </p>
    </div>
  );
}

export function SourceDocumentList({
  sources,
}: {
  sources: SourceDocument[];
}) {
  return (
    <DossierSection
      description="공식자료, 언론, 통계, 법령을 구분해 근거 범위를 확인합니다."
      eyebrow="원문 자료"
      id="sources"
      title="원문 자료"
    >
      {sources.length > 0 ? (
        <div>
          <div className="mb-4 flex flex-wrap gap-2 border-b border-gray-200 pb-3 text-sm font-medium">
            {["전체", "공식 문서", "법령/의사록", "정부/공공 발표", "언론 보도", "정당/단체 자료"].map(
              (filter, index) => (
                <span
                  key={filter}
                  className={`border-b-2 px-1 pb-2 ${
                    index === 0
                      ? "border-blue-600 text-blue-600"
                      : "border-transparent text-gray-600"
                  }`}
                >
                  {filter}
                </span>
              ),
            )}
          </div>

          <DossierFrame>
            <div className="max-w-full overflow-x-auto">
              <table className="w-full min-w-[960px] border-collapse text-left text-sm">
                <thead className="bg-gray-50 text-xs font-semibold text-gray-700">
                  <tr>
                    <th className="border-b border-r border-gray-200 px-4 py-3">자료명</th>
                    <th className="w-32 border-b border-r border-gray-200 px-4 py-3">발행처</th>
                    <th className="w-36 border-b border-r border-gray-200 px-4 py-3">날짜</th>
                    <th className="w-32 border-b border-r border-gray-200 px-4 py-3">유형</th>
                    <th className="w-28 border-b border-r border-gray-200 px-4 py-3">신뢰도</th>
                    <th className="w-28 border-b border-r border-gray-200 px-4 py-3">연결 주장</th>
                    <th className="w-20 border-b border-gray-200 px-4 py-3">원문</th>
                  </tr>
                </thead>
                <tbody>
                  {sources.map((source, index) => (
                    <tr key={source.id} className="align-top">
                      <td className="border-b border-r border-gray-100 px-4 py-3 font-medium leading-6 text-gray-900">
                        {source.title}
                      </td>
                      <td className="border-b border-r border-gray-100 px-4 py-3 text-gray-600">
                        {source.publisher}
                      </td>
                      <td className="border-b border-r border-gray-100 px-4 py-3 text-gray-600">
                        {formatDateTime(source.publishedAt)}
                      </td>
                      <td className={`border-b border-r border-gray-100 px-4 py-3 font-medium ${sourceTypeTone(source.sourceType)}`}>
                        {formatSourceType(source.sourceType)}
                      </td>
                      <td className="border-b border-r border-gray-100 px-4 py-3 text-gray-600">
                        {formatCredibility(source.credibility)}
                      </td>
                      <td className="border-b border-r border-gray-100 px-4 py-3 text-gray-600">
                        주장 {index + 1}번 근거
                      </td>
                      <td className="border-b border-gray-100 px-4 py-3">
                        <a
                          href={source.url}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-1 text-sm font-medium text-blue-600 hover:underline"
                        >
                          열기
                          <ExternalLink className="size-3.5" aria-hidden="true" />
                        </a>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="grid border-t border-gray-200 md:grid-cols-4 md:divide-x md:divide-gray-200">
              <SourcePreview label="요약" value={sources[0]?.title} />
              <SourcePreview label="인용 문장" value="원문 확인 후 직접 인용합니다." />
              <SourcePreview label="뒷받침하는 주장" value="공식 근거가 필요한 주장" />
              <SourcePreview label="한계/주의점" value="발행 시점 이후 변경 가능" />
            </div>
          </DossierFrame>
        </div>
      ) : (
        <EmptyFrame>
          원문 자료가 없습니다.
        </EmptyFrame>
      )}
    </DossierSection>
  );
}

function SourcePreview({
  label,
  value,
}: {
  label: string;
  value?: string;
}) {
  return (
    <div className="px-4 py-4">
      <p className="text-xs font-medium text-gray-500">{label}</p>
      <p className="mt-1 text-sm leading-6 text-gray-700">
        {value || "확인 전"}
      </p>
    </div>
  );
}

export function TimelineList({ events }: { events: IssueTimelineEvent[] }) {
  return (
    <DossierSection
      description="기사와 자료에서 확인되는 현실 사건의 발생, 발표, 후속 조치 순서를 정리합니다."
      eyebrow="타임라인"
      id="timeline"
      title="사건 타임라인"
    >
      {events.length > 0 ? (
        <DossierFrame>
          <div className="flex max-w-full gap-3 overflow-x-auto border-b border-gray-200 bg-gray-50 px-4 py-4">
            {events.slice(0, 5).map((event, index) => (
              <div
                key={event.id}
                className={`min-w-40 border-l pl-3 ${
                  index === 0 ? "border-blue-600" : "border-gray-200"
                }`}
              >
                <p className="text-xs text-gray-500">
                  {formatDateTime(event.occurredAt)}
                </p>
                <p className="mt-1 text-sm font-medium leading-5 text-gray-900">
                  {event.title}
                </p>
              </div>
            ))}
          </div>

          <div className="max-w-full overflow-x-auto">
            <table className="w-full min-w-[860px] border-collapse text-left text-sm">
              <thead className="bg-white text-xs font-semibold text-gray-700">
                <tr>
                  <th className="w-36 border-b border-r border-gray-200 px-4 py-3">시각</th>
                  <th className="w-44 border-b border-r border-gray-200 px-4 py-3">사건 진행</th>
                  <th className="border-b border-r border-gray-200 px-4 py-3">내용</th>
                  <th className="w-28 border-b border-r border-gray-200 px-4 py-3">성격</th>
                  <th className="w-28 border-b border-gray-200 px-4 py-3">확인 상태</th>
                </tr>
              </thead>
              <tbody>
                {events.map((event, index) => {
                  const eventTypeLabel = formatTimelineEventType(event.type);

                  return (
                    <tr
                      key={event.id}
                      className={`align-top ${index === 0 ? "bg-blue-50/30" : ""}`}
                    >
                      <td className="border-b border-r border-gray-100 px-4 py-3 text-gray-600">
                        {formatDateTime(event.occurredAt)}
                      </td>
                      <td className="border-b border-r border-gray-100 px-4 py-3 font-medium text-gray-900">
                        {event.title}
                      </td>
                      <td className="border-b border-r border-gray-100 px-4 py-3 leading-6 text-gray-700">
                        {event.description}
                      </td>
                      <td className="border-b border-r border-gray-100 px-4 py-3 text-gray-600">
                        {eventTypeLabel}
                      </td>
                      <td className="border-b border-gray-100 px-4 py-3 text-gray-600">
                        {formatTimelineEventStatus(event.type)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </DossierFrame>
      ) : (
        <EmptyFrame>
          타임라인 항목이 없습니다.
        </EmptyFrame>
      )}
    </DossierSection>
  );
}

function formatTimelineEventType(type: string) {
  const labels: Record<string, string> = {
    article: "기사 보도",
    incident_event: "발생",
    official_statement: "공식 발표",
    followup_action: "후속 조치",
    reported_event: "사건 보도",
    official_event: "공식 확인",
    claim_update: "주장 업데이트",
    correction: "정정 반영",
    new_article: "새 기사 반영",
    official_source: "공식자료 반영",
    source_update: "출처 업데이트",
  };

  return labels[type] ?? type.replaceAll("_", " ");
}

function formatTimelineEventStatus(type: string) {
  const labels: Record<string, string> = {
    followup_action: "후속 진행",
    incident_event: "발생 확인",
    official_event: "공식 확인",
    official_statement: "공식 확인",
    reported_event: "보도 확인",
  };

  return labels[type] ?? "확인 필요";
}

export function NumberChangeList({
  changes,
}: {
  changes: NumberChangeEvent[];
}) {
  return (
    <DossierSection
      description="이전 값, 현재 값, 근거, 반영 시점을 함께 추적합니다."
      eyebrow="수치"
      id="numbers"
      title="수치 변경 기록"
    >
      {changes.length > 0 ? (
        <DossierFrame>
          <div className="max-w-full overflow-x-auto">
            <table className="w-full min-w-[920px] border-collapse text-left text-sm">
              <thead className="bg-gray-50 text-xs font-semibold text-gray-700">
                <tr>
                  <th className="w-32 border-b border-r border-gray-200 px-4 py-3">항목</th>
                  <th className="w-28 border-b border-r border-gray-200 px-4 py-3">이전 값</th>
                  <th className="w-28 border-b border-r border-gray-200 px-4 py-3">현재 값</th>
                  <th className="w-36 border-b border-r border-gray-200 px-4 py-3">변경 시각</th>
                  <th className="w-32 border-b border-r border-gray-200 px-4 py-3">출처</th>
                  <th className="border-b border-r border-gray-200 px-4 py-3">변경 이유</th>
                  <th className="w-24 border-b border-gray-200 px-4 py-3">판정</th>
                </tr>
              </thead>
              <tbody>
                {changes.map((change) => (
                  <tr key={change.id} className="align-top">
                    <td className="border-b border-r border-gray-100 px-4 py-3 font-medium text-gray-900">
                      {change.label}
                    </td>
                    <td className="border-b border-r border-gray-100 px-4 py-3 text-gray-600">{change.previousValue}</td>
                    <td className="border-b border-r border-gray-100 px-4 py-3 font-semibold text-blue-600">
                      {change.currentValue}
                    </td>
                    <td className="border-b border-r border-gray-100 px-4 py-3 text-gray-600">
                      {formatDateTime(change.changedAt)}
                    </td>
                    <td className="border-b border-r border-gray-100 px-4 py-3 text-gray-600">{change.source}</td>
                    <td className="border-b border-r border-gray-100 px-4 py-3 leading-6 text-gray-700">
                      {change.note}
                    </td>
                    <td className="border-b border-gray-100 px-4 py-3">
                      <StatusBadge tone={change.tone ?? "neutral"}>
                        최신 반영
                      </StatusBadge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="grid border-t border-gray-200 md:grid-cols-[180px_minmax(0,1fr)]">
            <div className="border-b border-gray-100 bg-gray-50 px-4 py-4 text-sm font-semibold text-gray-950 md:border-b-0 md:border-r">
              수치 출처 추적
            </div>
            <div className="grid gap-2 px-4 py-4 text-sm leading-6 text-gray-600">
              {changes.slice(0, 3).map((change) => (
                <p key={`${change.id}-source`}>
                  {change.label}: {change.source} 기준으로 {change.currentValue} 반영
                </p>
              ))}
            </div>
          </div>
        </DossierFrame>
      ) : (
        <EmptyFrame>
          추적 중인 수치 변경이 없습니다.
        </EmptyFrame>
      )}
    </DossierSection>
  );
}

export function ReportUseActions({ issueId }: { issueId: string }) {
  return (
    <section id="report-actions" className="py-8">
      <p className="text-xs font-medium uppercase tracking-wide text-gray-500">
        리포트
      </p>
      <h2 className="mt-2 text-lg font-semibold text-gray-900">리포트/활용</h2>
      <p className="mt-3 max-w-[680px] text-[15px] leading-7 text-gray-700">
        목적에 맞춰 발표 자료, 출처 포함 리포트, 기사 비교표로 이어갑니다.
      </p>
      <div className="mt-6 grid gap-3 sm:grid-cols-3">
        <Link
          href={`/reports/${issueId}`}
          className="text-sm font-medium text-blue-600 hover:underline"
        >
          발표용 리포트 보기
        </Link>
        <a href="#sources" className="text-sm font-medium text-blue-600 hover:underline">
          출처 포함 근거 확인
        </a>
        <a href="#articles" className="text-sm font-medium text-blue-600 hover:underline">
          기사 비교표 보기
        </a>
      </div>
    </section>
  );
}
