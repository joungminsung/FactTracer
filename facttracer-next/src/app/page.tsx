import Image from "next/image";
import Link from "next/link";
import { CheckCircle2, ChevronRight, Search } from "lucide-react";
import { SiteHeader } from "@/components/site-header";
import { getPublicHome, topicFilters } from "@/lib/api/facttracer";
import { getServerAccessToken } from "@/lib/auth/server-session";
import type { Issue, IssueSortMode, PublicHomeResponse } from "@/lib/api/types";

const newsImageSources = [
  "/images/news/facttracer-news-0.png",
  "/images/news/facttracer-news-1.png",
  "/images/news/facttracer-news-2.png",
  "/images/news/facttracer-news-3.png",
  "/images/news/facttracer-news-4.png",
  "/images/news/facttracer-news-5.png",
  "/images/news/facttracer-news-6.png",
  "/images/news/facttracer-news-7.png",
  "/images/news/facttracer-news-8.png",
  "/images/news/facttracer-news-9.png",
  "/images/news/facttracer-news-10.png",
  "/images/news/facttracer-news-11.png",
];

const fallbackTopics = [
  "정치",
  "사회",
  "경제",
  "국제",
  "재난/환경",
  "과학/기술",
  "라이프",
];

export default async function WebHomePage({
  searchParams,
}: {
  searchParams?: Promise<{
    eventGroup?: string;
    issueId?: string;
    majorTopic?: string;
    q?: string;
    sort?: IssueSortMode;
    topic?: string;
  }>;
}) {
  const params = (await searchParams) ?? {};
  const accessToken = await getServerAccessToken();
  let home: PublicHomeResponse = {
    issueGroups: {},
    issues: [],
    selectedIssue: null,
    topics: topicFilters,
    updateLogs: [],
  };

  try {
    home = await getPublicHome({
      eventGroup: params.eventGroup,
      issueId: params.issueId,
      majorTopic: params.majorTopic,
      query: params.q,
      sort: params.sort ?? "recommended",
      token: accessToken,
      topic: normalizeTopicParam(params.topic),
    });
  } catch {
    home = {
      issueGroups: {},
      issues: [],
      selectedIssue: null,
      topics: topicFilters,
      updateLogs: [],
    };
  }

  const issues = home.issues;
  const visibleTopics = buildVisibleTopics(home.topics);
  const leadIssue = issues[0];
  const secondaryIssues = issues.slice(1, 3);
  const latestIssues = issues
    .filter(
      (issue) =>
        issue.id !== leadIssue?.id &&
        !secondaryIssues.some((secondary) => secondary.id === issue.id),
    )
    .slice(0, 4);
  const topicSections = buildTopicSections(issues, visibleTopics, 8);
  const sidebarTopic = buildSidebarTopic(issues);
  const moreIssues = buildMoreIssues(issues, [
    leadIssue,
    ...secondaryIssues,
    ...latestIssues,
    ...topicSections.map((section) => section.issue),
  ]);
  const activeQuery = params.q?.trim() ?? "";

  return (
    <div className="min-h-screen bg-white text-gray-950">
      <SiteHeader />

      <main className="mx-auto max-w-[1520px] px-5 pb-14 pt-6 sm:px-7 lg:px-9">
        <span className="sr-only">이슈 모니터 감지된 사건 기사 링크</span>

        {issues.length > 0 ? (
          <>
            <div className="grid gap-7 lg:grid-cols-[minmax(0,1fr)_360px]">
              <div className="min-w-0 lg:border-r lg:border-gray-200 lg:pr-7">
                <section aria-labelledby="major-stories">
                  <h1
                    id="major-stories"
                    className="text-[23px] font-extrabold tracking-[-0.01em]"
                  >
                    주요 사건
                  </h1>

                  {leadIssue ? <LeadStory issue={leadIssue} /> : null}

                  {secondaryIssues.length > 0 ? (
                    <div className="mt-5 grid border-b border-gray-200 md:grid-cols-2">
                      {secondaryIssues.map((issue, index) => (
                        <SecondaryStory
                          imageIndex={storyImageIndex(issue, index + 1)}
                          issue={issue}
                          key={issue.id}
                        />
                      ))}
                    </div>
                  ) : null}
                </section>

                <section aria-labelledby="topic-stories" className="mt-4">
                  <h2
                    id="topic-stories"
                    className="text-[22px] font-extrabold tracking-[-0.01em]"
                  >
                    분야별 사건
                  </h2>

                  <div className="mt-4 grid gap-x-6 gap-y-7 sm:grid-cols-2 lg:grid-cols-3">
                    {topicSections.map((section, index) => (
                      <TopicCard
                        imageIndex={topicImageIndex(section.topic, index)}
                        issue={section.issue}
                        key={`${section.topic}-${section.issue.id}-${index}`}
                        topic={section.topic}
                      />
                    ))}
                  </div>
                </section>
              </div>

              <aside className="min-w-0">
                <LatestVerification issues={latestIssues} />
                {sidebarTopic ? (
                  <SidebarTopic
                    imageIndex={10}
                    issue={sidebarTopic.issue}
                    topic={sidebarTopic.topic}
                  />
                ) : null}
              </aside>
            </div>

            {moreIssues.length > 0 ? <MoreStories issues={moreIssues} /> : null}
          </>
        ) : (
          <EmptyHome activeQuery={activeQuery} />
        )}
      </main>
    </div>
  );
}

function LeadStory({ issue }: { issue: Issue }) {
  return (
    <article className="mt-4 grid grid-cols-[minmax(0,1fr)] gap-6 border-b border-gray-200 pb-5 lg:grid-cols-[minmax(390px,0.9fr)_minmax(0,0.58fr)]">
      <Link
        href={`/issues/${issue.id}`}
        aria-label={`${issue.title} 상세 보기`}
        className="block min-w-0"
      >
        <NewsImage
          className="aspect-[2.55/1] min-h-[160px]"
          imageIndex={storyImageIndex(issue, 0)}
          issue={issue}
          sizes="(max-width: 1024px) 100vw, 58vw"
        />
      </Link>

      <div className="flex min-w-0 flex-col justify-center pb-1">
        <Link href={`/issues/${issue.id}`} className="group block">
          <h2 className="text-[27px] font-extrabold leading-[1.22] tracking-[-0.025em] text-gray-950 group-hover:text-blue-700 sm:text-[31px]">
            {issue.title}
          </h2>
          <p className="mt-4 line-clamp-2 max-w-[500px] text-[15px] leading-6 text-gray-600">
            {issue.summary}
          </p>
        </Link>

        <div className="mt-6">
          <StoryMeta issue={issue} />
          <StoryStatus issue={issue} />
        </div>
      </div>
    </article>
  );
}

function SecondaryStory({
  imageIndex,
  issue,
}: {
  imageIndex: number;
  issue: Issue;
}) {
  return (
    <article className="grid grid-cols-[minmax(0,1fr)] gap-4 py-5 md:grid-cols-[minmax(140px,0.82fr)_minmax(0,1fr)] md:px-5 md:first:pl-0 md:last:pr-0">
      <Link
        href={`/issues/${issue.id}`}
        aria-label={`${issue.title} 상세 보기`}
        className="block min-w-0"
      >
        <NewsImage
          className="aspect-[1.55/1] h-full min-h-[136px]"
          imageIndex={imageIndex}
          issue={issue}
          sizes="(max-width: 768px) 100vw, 28vw"
        />
      </Link>
      <div className="flex min-w-0 flex-col justify-between">
        <Link href={`/issues/${issue.id}`} className="group block">
          <h3 className="line-clamp-2 text-[19px] font-extrabold leading-[1.34] tracking-[-0.015em] group-hover:text-blue-700">
            {issue.title}
          </h3>
          <p className="mt-2 line-clamp-2 text-[14px] leading-6 text-gray-600">
            {issue.summary}
          </p>
        </Link>

        <div className="mt-4">
          <StoryMeta issue={issue} />
          <StoryStatus issue={issue} compact />
        </div>
      </div>
    </article>
  );
}

function LatestVerification({ issues }: { issues: Issue[] }) {
  return (
    <section aria-labelledby="latest-verification">
      <h2
        id="latest-verification"
        className="text-[21px] font-extrabold tracking-[-0.01em]"
      >
        최신 정리
      </h2>

      <div className="mt-5 divide-y divide-gray-200 border-b border-gray-200">
        {issues.map((issue, index) => (
          <Link
            className="grid grid-cols-[106px_minmax(0,1fr)] gap-4 py-4 first:pt-0 hover:text-blue-700 sm:grid-cols-[124px_minmax(0,1fr)]"
            href={`/issues/${issue.id}`}
            key={issue.id}
          >
            <NewsImage
              className="aspect-[1.45/1] rounded-[2px]"
              imageIndex={storyImageIndex(issue, index + 3)}
              issue={issue}
              sizes="124px"
            />
            <div className="min-w-0">
              <h3 className="line-clamp-2 text-[16px] font-bold leading-[1.42] tracking-[-0.01em]">
                {issue.title}
              </h3>
              <p className="mt-3 text-[13px] leading-5">
                <span className="font-extrabold text-blue-700">
                  {latestLabel(issue)}
                </span>
                <span className="ml-3 text-gray-500">{formatRelativeTime(issue.updatedAt)}</span>
              </p>
            </div>
          </Link>
        ))}
      </div>

      <Link
        href="/verify"
        className="flex h-11 items-center justify-between border-b border-gray-200 text-[14px] font-semibold hover:text-blue-700"
      >
        전체 보기
        <ChevronRight className="size-4" aria-hidden="true" />
      </Link>
    </section>
  );
}

function TopicCard({
  imageIndex,
  issue,
  topic,
}: {
  imageIndex: number;
  issue: Issue;
  topic: string;
}) {
  return (
    <article className="min-w-0 lg:border-l lg:border-gray-200 lg:pl-6 lg:[&:nth-child(3n+1)]:border-l-0 lg:[&:nth-child(3n+1)]:pl-0">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-[17px] font-extrabold">{topic}</h3>
        <Link
          href={`/?topic=${encodeURIComponent(normalizeTopicParam(topic) ?? topic)}`}
          className="flex items-center gap-1 text-[13px] font-medium text-gray-500 hover:text-blue-700"
        >
          더보기
          <ChevronRight className="size-4" aria-hidden="true" />
        </Link>
      </div>
      <Link href={`/issues/${issue.id}`} className="group block">
        <NewsImage
          className="aspect-[2.05/1]"
          imageIndex={imageIndex}
          issue={issue}
          sizes="(max-width: 768px) 100vw, 22vw"
        />
        <h4 className="mt-2 line-clamp-1 text-[15px] font-semibold tracking-[-0.01em] group-hover:text-blue-700">
          {issue.title}
        </h4>
        <p className="mt-1 text-[13px] text-gray-500">{formatRelativeTime(issue.updatedAt)}</p>
      </Link>
    </article>
  );
}

function SidebarTopic({
  imageIndex,
  issue,
  topic,
}: {
  imageIndex: number;
  issue: Issue;
  topic: string;
}) {
  return (
    <section className="mt-7" aria-labelledby="sidebar-topic">
      <div className="mb-3 flex items-center justify-between">
        <h2 id="sidebar-topic" className="text-[18px] font-extrabold">
          {topic}
        </h2>
        <Link
          href={`/?topic=${encodeURIComponent(normalizeTopicParam(topic) ?? topic)}`}
          className="flex items-center gap-1 text-sm font-medium text-gray-500 hover:text-blue-700"
        >
          더보기
          <ChevronRight className="size-4" aria-hidden="true" />
        </Link>
      </div>
      <Link href={`/issues/${issue.id}`} className="group block">
        <NewsImage
          className="aspect-[2.25/1]"
          imageIndex={imageIndex}
          issue={issue}
          sizes="360px"
        />
        <h3 className="mt-2 line-clamp-1 text-[15px] font-semibold group-hover:text-blue-700">
          {issue.title}
        </h3>
        <p className="mt-1 text-[13px] text-gray-500">{formatRelativeTime(issue.updatedAt)}</p>
      </Link>
    </section>
  );
}

function MoreStories({ issues }: { issues: Issue[] }) {
  return (
    <section className="mt-9 border-t border-gray-200 pt-6" aria-labelledby="more-stories">
      <div className="flex items-end justify-between">
        <h2
          id="more-stories"
          className="text-[22px] font-extrabold tracking-[-0.01em]"
        >
          더 많은 사건
        </h2>
        <Link
          href="/verify"
          className="flex items-center gap-1 text-sm font-semibold text-gray-500 hover:text-blue-700"
        >
          제보/검증
          <ChevronRight className="size-4" aria-hidden="true" />
        </Link>
      </div>

      <div className="mt-4 grid gap-x-6 gap-y-7 sm:grid-cols-2 lg:grid-cols-4">
        {issues.map((issue, index) => (
          <article
            className="min-w-0 border-t border-gray-200 pt-4 first:border-t-0 sm:[&:nth-child(-n+2)]:border-t-0 lg:[&:nth-child(-n+4)]:border-t-0"
            key={`${issue.id}-${index}`}
          >
            <Link href={`/issues/${issue.id}`} className="group block">
              <NewsImage
                className="aspect-[1.8/1]"
                imageIndex={storyImageIndex(issue, index)}
                issue={issue}
                sizes="(max-width: 768px) 100vw, 22vw"
              />
              <p className="mt-3 text-[13px] leading-5 text-gray-500">
                {formatRelativeTime(issue.updatedAt)}
                <span className="mx-2 text-gray-300">|</span>
                {issue.topic}
              </p>
              <h3 className="mt-1 line-clamp-2 text-[17px] font-extrabold leading-[1.35] tracking-[-0.015em] group-hover:text-blue-700">
                {issue.title}
              </h3>
              <p className="mt-2 line-clamp-2 text-[14px] leading-6 text-gray-600">
                {issue.summary}
              </p>
            </Link>
          </article>
        ))}
      </div>
    </section>
  );
}

function EmptyHome({ activeQuery }: { activeQuery: string }) {
  return (
    <section className="mx-auto max-w-2xl border-y border-gray-200 py-16 text-center">
      <h1 className="text-3xl font-extrabold tracking-[-0.02em]">
        주요 사건
      </h1>
      <p className="mt-4 text-gray-600">
        {activeQuery
          ? "검색 조건에 맞는 사건이 아직 없습니다."
          : "공개된 사건이 생기면 이 화면에 표시됩니다."}
      </p>
      <form action="/" className="mx-auto mt-6 flex max-w-md gap-2">
        <label className="flex h-10 min-w-0 flex-1 items-center gap-2 rounded-sm border border-gray-300 px-3 text-gray-500 focus-within:border-gray-700">
          <span className="sr-only">검색어</span>
          <input
            className="min-w-0 flex-1 bg-transparent text-sm text-gray-900 outline-none placeholder:text-gray-400"
            defaultValue={activeQuery}
            name="q"
            placeholder="사건, 키워드 검색"
            type="search"
          />
          <Search className="size-4" aria-hidden="true" />
        </label>
        <button
          className="h-10 rounded-sm bg-gray-950 px-4 text-sm font-bold text-white"
          type="submit"
        >
          검색
        </button>
      </form>
    </section>
  );
}

function StoryMeta({ issue }: { issue: Issue }) {
  return (
    <p className="text-[13px] leading-5 text-gray-500">
      {formatRelativeTime(issue.updatedAt)}
      <span className="mx-3 text-gray-300">|</span>
      {issue.topic}
    </p>
  );
}

function StoryStatus({
  compact = false,
  issue,
}: {
  compact?: boolean;
  issue: Issue;
}) {
  return (
    <p
      className={`inline-flex items-center gap-2 font-extrabold text-blue-700 ${
        compact ? "mt-2 text-[13px]" : "mt-5 text-[14px]"
      }`}
    >
      <CheckCircle2 className="size-4" aria-hidden="true" />
      {statusLabel(issue.status)}
      <ChevronRight className="ml-4 size-4 text-gray-700 sm:ml-10" aria-hidden="true" />
    </p>
  );
}

function NewsImage({
  className,
  imageIndex,
  issue,
  sizes,
}: {
  className: string;
  imageIndex: number;
  issue?: Issue;
  sizes: string;
}) {
  const fallbackSource =
    newsImageSources[imageIndex % newsImageSources.length] ??
    newsImageSources[0];
  const source = issue?.representativeImageUrl || fallbackSource;

  return (
    <div
      aria-hidden="true"
      className={`relative w-full overflow-hidden bg-gray-100 ${className}`}
    >
      <Image
        alt=""
        className="object-cover"
        fill
        unoptimized={Boolean(issue?.representativeImageUrl)}
        sizes={sizes}
        src={source}
      />
    </div>
  );
}

function buildVisibleTopics(topics: string[]): string[] {
  const normalized = topics
    .filter((topic) => topic !== "전체")
    .map((topic) => (topic === "재난" ? "재난/환경" : topic));
  const merged = [...normalized, ...fallbackTopics];
  return Array.from(new Set(merged)).slice(0, 7);
}

function buildTopicSections(issues: Issue[], topics: string[], limit: number) {
  const usedIssueIds = new Set<string>();
  const sections = topics
    .map((topic) => {
      const issue = issues.find(
        (candidate) =>
          !usedIssueIds.has(candidate.id) &&
          topicMatches(candidate.topic, topic),
      );

      if (!issue) return null;
      usedIssueIds.add(issue.id);

      return { issue, topic };
    })
    .filter((section): section is { issue: Issue; topic: string } => Boolean(section));

  const unique = new Map<string, { issue: Issue; topic: string }>();
  for (const section of sections) {
    if (!unique.has(section.topic)) unique.set(section.topic, section);
  }

  return Array.from(unique.values()).slice(0, limit);
}

function topicMatches(issueTopic: string, sectionTopic: string) {
  const normalizedIssue = normalizeTopicParam(issueTopic) ?? issueTopic;
  const normalizedSection = normalizeTopicParam(sectionTopic) ?? sectionTopic;

  return (
    normalizedIssue === normalizedSection ||
    issueTopic === sectionTopic ||
    issueTopic.includes(normalizedSection) ||
    normalizedSection.includes(issueTopic)
  );
}

function buildMoreIssues(issues: Issue[], usedIssues: Array<Issue | undefined>) {
  const usedIds = new Set(
    usedIssues.filter((issue): issue is Issue => Boolean(issue)).map((issue) => issue.id),
  );
  const remaining = issues.filter((issue) => !usedIds.has(issue.id));

  if (remaining.length >= 8) return remaining.slice(0, 12);

  const merged = [...remaining, ...issues.filter((issue) => !remaining.includes(issue))];
  const unique = new Map<string, Issue>();
  for (const issue of merged) {
    if (!unique.has(issue.id)) unique.set(issue.id, issue);
  }

  return Array.from(unique.values()).slice(0, 12);
}

function buildSidebarTopic(issues: Issue[]) {
  const issue =
    issues.find((candidate) => /재난|환경|산불|폭우|지진|피해/.test(candidate.topic)) ??
    issues.find((candidate) => /재난|환경|산불|폭우|지진|피해/.test(candidate.title)) ??
    issues[0];

  return issue ? { issue, topic: "재난/환경" } : null;
}

function storyImageIndex(issue: Issue, fallback: number): number {
  const text = `${issue.topic} ${issue.title}`;

  if (/국회|여당|야당|정부|대통령|발언|정치|법안|특검/.test(text)) return 0;
  if (/선거|투표|득표/.test(text)) return 7;
  if (/부동산|대출|공급|아파트|주택/.test(text)) return 1;
  if (/서해|소청도|어선|해상|구조|실종|해경/.test(text)) return 2;
  if (/전투기|군|국방|북한|핵|외교|국제/.test(text)) return 3;
  if (/개인정보|모바일|정부가|수집/.test(text)) return 4;
  if (/수돗물|발암|검출|물질/.test(text)) return 5;
  if (/건강보험|보험|인상|확정/.test(text)) return 6;
  if (/국회의사당|민생|공방/.test(text)) return 7;
  if (/교통|서울|논의|사회/.test(text)) return 8;
  if (/수출|무역|항만|경제|금융|증시|고용/.test(text)) return 9;
  if (/한화|폭발|사고|공장|노동|산업|조사/.test(text)) return 11;
  if (/산불|재난|환경|폭우|지진|피해/.test(text)) return 10;
  if (/브리핑|발표|조사/.test(text)) return 11;

  return fallback;
}

function topicImageIndex(topic: string, fallback: number): number {
  if (topic === "정치") return 7;
  if (topic === "사회") return 8;
  if (topic === "경제") return 9;
  if (topic.includes("재난")) return 10;
  return fallback + 7;
}

function normalizeTopicParam(topic?: string) {
  if (!topic) return topic;
  if (topic === "재난/환경") return "재난";
  if (topic === "과학/기술") return "과학";
  return topic;
}

function latestLabel(issue: Issue) {
  if (issue.status === "verified" || issue.status === "completed") return "확인된 사실";
  if (issue.status === "resolved") return "반론 확인";
  if (issue.status === "needs_review" || issue.status === "updated") {
    return "쟁점 보강";
  }
  if (issue.status === "blocked") return "확인 중";
  return "정리 중";
}

function statusLabel(status?: string) {
  if (status === "verified" || status === "completed") return "정리 완료";
  if (status === "needs_review" || status === "updated") return "쟁점 보강";
  if (status === "resolved") return "사실관계 확인";
  if (status === "blocked") return "추가 확인 중";
  return "보도 흐름 정리 중";
}

function formatRelativeTime(value?: string | null) {
  if (!value) return "방금 전";

  const timestamp = new Date(value).getTime();
  if (Number.isNaN(timestamp)) return "방금 전";

  const diffMs = Math.max(0, Date.now() - timestamp);
  const minutes = Math.max(1, Math.floor(diffMs / 60000));

  if (minutes < 60) return `${minutes}분 전`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}시간 전`;

  const days = Math.floor(hours / 24);
  return `${days}일 전`;
}
