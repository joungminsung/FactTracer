# Backend Collection, Classification, Ranking Design

Date: 2026-06-10
Scope: FactTracer backend news collection, incident grouping, issue synthesis, representative image selection, and issue ranking.

## Goal

Improve backend collection quality so large public incidents are reliably discovered, grouped, enriched, ranked, and exposed to the frontend with useful metadata.

The system should automatically:

- Group narrowly related reports into the same incident.
- Group separate incidents under the same large public topic when incident signals share the same public context.
- Choose a representative image for each issue.
- Detect when issue detail sections are thin and run targeted re-search.
- Rank issues by public importance, controversy, freshness, and user interest.

## Current Context

The current backend has these useful foundations:

- `Issue.topic` stores broad public categories such as `정치`, `사회`, `경제`.
- `DiscoveryTopic`, `DiscoveredIncident`, and `SearchKeyword` drive Google News based discovery.
- `backfill_issue_sources` can search follow-up articles for an issue.
- `page_builder.refresh_issue_cache` builds public detail sections from stored articles, claims, evidence, perspectives, timeline, and number changes.
- The frontend currently uses local temporary news images selected by title/topic heuristics.

The current gaps are:

- No persistent `majorTopic` layer for special collections such as `2026 지방선거`.
- No persistent `eventGroup` layer for same-incident grouping across multiple issues.
- No backend representative image fields in `Issue` or API responses.
- Quality checks are mostly source-count based and do not evaluate whether summary, facts, claims, debate map, timeline, article comparison, perspectives, or number changes are rich enough.
- Main page ordering is mostly recent-update oriented and does not model controversy, impact, momentum, personalization, or category-specific ranking.

## Classification Model

The backend will classify public news in four visible levels:

1. `topic`
   Broad category. Existing canonical values remain: `정치`, `사회`, `경제`, `국제`, `재난`, `보건`.

2. `majorTopic`
   A large public topic or seasonal collection that can contain multiple incidents.
   Examples: `2026 지방선거`, `의료대란`, `부동산 공급정책`.

3. `eventGroup`
   A same-incident grouping.
   Example: `선관위 투표용지 부족 사태`.

4. `issue`
   The current public card/detail object.
   Examples: `투표용지 부족 투표소 91곳 논란`, `후속 집회와 고발 움직임`.

Example mapping:

- `topic`: `정치`
- `majorTopic`: `2026 지방선거`
- `eventGroup`: `선관위 투표용지 부족 사태`
- `issue`: `투표용지 부족 투표소 91곳 논란`

Separate incidents such as `선관위 투표용지 부족 사태` and `인천 사전투표 동일 득표 논란` should not be forced into the same issue or event group. They should share `majorTopic = 2026 지방선거`.

## Data Model

Add `MajorTopic`:

- `id`
- `name`
- `slug`
- `topic`
- `summary`
- `status`
- `keywords_json`
- `aliases_json`
- `signal_json`
- `created_at`
- `updated_at`
- `last_seen_at`

Add `EventGroup`:

- `id`
- `major_topic_id`
- `topic`
- `name`
- `slug`
- `summary`
- `status`
- `keywords_json`
- `aliases_json`
- `signal_json`
- `article_count`
- `issue_count`
- `created_at`
- `updated_at`
- `last_seen_at`

Extend `Issue`:

- `major_topic_id`
- `event_group_id`
- `major_topic_name`
- `event_group_name`
- `representative_image_url`
- `representative_image_source`
- `representative_image_source_url`
- `representative_image_confidence`
- `representative_image_updated_at`
- `quality_score`
- `quality_status`
- `quality_report_json`
- `quality_attempts`
- `last_quality_checked_at`
- `next_quality_retry_at`
- `ranking_json`

Add `ImageCandidate`:

- `id`
- `issue_id`
- `article_id`
- `url`
- `source_url`
- `publisher`
- `source_type`
- `width`
- `height`
- `mime_type`
- `confidence`
- `status`
- `reason`
- `created_at`
- `updated_at`

Add `UserInterestProfile`:

- `user_id`
- `topic_weights_json`
- `major_topic_weights_json`
- `event_group_weights_json`
- `publisher_weights_json`
- `updated_at`

This can be derived from existing saved issues, verification requests, submitted claims, and metric events. It should not require manual onboarding.

## Classification Pipeline

The pipeline runs after article collection and before issue publishing/cache refresh.

1. Collect articles from discovery, keyword search, source collectors, or issue follow-up search.
2. Normalize article title, URL, publisher, summary, body text, and image metadata.
3. Cluster collected articles into same-incident candidate clusters.
4. Classify each cluster into `topic`, `majorTopic`, and `eventGroup`.
5. Match to existing `EventGroup` by normalized title, keywords, article signals, entities, dates, and incident similarity.
6. Match or create `MajorTopic` when the event belongs to a larger public theme.
7. Match or create `Issue` under the event group.
8. Save search keywords for continued follow-up.
9. Enqueue parse, claim extraction, verification, synthesis, representative image selection, and quality scoring jobs.

Matching rules:

- Same event group requires strong overlap in incident-specific entities, location, time window, claim subject, and core event phrase.
- Same major topic requires broad shared context but can have different event groups.
- The classifier must prefer creating a new event group over incorrectly merging separate incidents.
- The classifier must prefer reusing a major topic when large context is clearly shared.

AI output for classification must be constrained to structured JSON and then validated by deterministic rules. Invalid or weak AI output falls back to keyword/entity matching.

## Collection And Re-Search Quality Loop

Collection becomes a loop:

```text
collect -> analyze -> synthesize -> score quality -> re-search if needed
```

Initial collection sources:

- `DiscoveryTopic`
- `SearchKeyword`
- official/source collectors
- existing issue follow-up search
- manual verification requests

Search query expansion should be purpose-based:

- Core incident: `선관위 투표용지 부족`
- Official response: `중앙선관위 설명자료`, `선관위 해명`
- Follow-up action: `고발`, `감사`, `수사`, `집회`, `기자회견`
- Numbers: `91곳`, `50곳`, `부족 투표소`
- Adjacent controversy: `동일 득표`, `사전투표 논란`, `개표 논란`

Add an issue quality report with these dimensions:

- `articleCoverage`: article count and distinct publisher count.
- `sourceDiversity`: mix of media, official, public, statistics, law, and social sources.
- `officialCoverage`: official or public source presence.
- `claimCoverage`: number of extracted claims and active claim clusters.
- `factCoverage`: non-empty confirmed facts with evidence.
- `evidenceCoverage`: share of claims with credible evidence.
- `perspectiveCoverage`: at least two public-facing perspectives when the issue contains competing claims.
- `timelineCoverage`: initial, follow-up, and official/source update events where available.
- `numberCoverage`: numeric claims have comparable values and evidence.
- `parseHealth`: low title-only article ratio.
- `missingSignals`: explicit list of missing requirements.

Re-search triggers:

- Article count is below threshold.
- Distinct publisher count is below threshold.
- Official or public source is missing for high-impact issues.
- Claim count is too low compared with article count.
- Confirmed facts are empty.
- Evidence coverage is low.
- Many claims remain `근거 부족`.
- Timeline only lists article titles and has no meaningful follow-up or official update.
- Number-change section is empty while numeric claims are present.
- Representative image confidence is low.

Retry controls:

- Default maximum quality attempts: 3.
- High-impact, election, disaster, and public safety issues: 5.
- Store `quality_attempts`, `last_quality_checked_at`, and `next_quality_retry_at`.
- Each retry must add targeted search queries based on `missingSignals`.
- Stop retrying when the issue reaches `quality_status = sufficient` or retry budget is exhausted.

## Issue Detail Synthesis

`page_builder` should continue to assemble DB-backed sections, but add an `issue_synthesis` stage before cache refresh.

The synthesis stage creates or improves:

- summary
- confirmed facts
- claim clusters
- claim verification summaries
- article comparison
- perspectives
- timeline
- source documents
- number changes

Rules:

- AI may summarize and organize only stored articles, claims, evidence, and source documents.
- AI must not invent facts, URLs, dates, numbers, or official statements.
- Every synthesized section should retain enough source linkage for frontend citations and admin debugging.
- If inputs are insufficient, the section records a missing signal instead of producing filler text.
- Synthesis results should be stored in cache fields already returned by `IssueDetail`, with additional quality metadata in `Issue.quality_report_json`.

## Representative Image Selection

Image selection is fully automatic.

Candidate extraction:

- Parse `og:image`.
- Parse `twitter:image`.
- Parse RSS media thumbnails.
- Parse JSON collector fields such as `image`, `thumbnail`, and `urlToImage`.
- Prefer official/public source image candidates when available.

Candidate validation:

- URL is reachable.
- MIME type is image-like.
- Image is large enough for card/detail surfaces.
- URL is not an obvious tracker, spacer, logo sprite, favicon, or profile icon.
- Duplicate images are collapsed.

Scoring:

- Official/public source image: strong positive.
- Candidate from highly relevant article: positive.
- Recent article for active incident: positive.
- Adequate dimensions and aspect ratio: positive.
- Generic logo/icon/profile image: negative.
- Broken URL or unsupported MIME: excluded.
- Low relevance to issue title/event group: negative.
- Safety or personal-harm risk: excluded or marked `needs_review`.

Selected result is stored on `Issue`:

- `representative_image_url`
- `representative_image_source`
- `representative_image_source_url`
- `representative_image_confidence`
- `representative_image_updated_at`

Re-selection happens when:

- New high-confidence candidates arrive.
- Current image fails validation.
- Current confidence is below threshold.
- Event group changes.

Frontend compatibility:

- API returns `representativeImageUrl`.
- Frontend uses it when present.
- Existing temporary image heuristics remain fallback only.

## Ranking And Personalization

Add `IssueRankingService` to compute ranking for home, topic pages, major-topic pages, and event-group pages.

Ranking signals:

- `freshnessScore`: recent issue update, new article, official source update, or verdict change.
- `controversyScore`: article count, distinct publisher count, claim conflict count, needs-review count, report count.
- `impactScore`: high-impact topic, official institution mention, public safety/election/economy relevance, number changes.
- `verificationScore`: confirmed facts, official evidence, verdict changes, resolved claims.
- `momentumScore`: recent article growth, follow-up search growth, new source diversity.
- `personalScore`: user interest from saved issues, views, verification requests, submitted claims, and preferred topics.
- `diversityPenalty`: prevents one topic or major topic from dominating the first screen.

Default main rank:

```text
mainRank =
  impactScore * 0.25
+ controversyScore * 0.22
+ freshnessScore * 0.20
+ momentumScore * 0.15
+ verificationScore * 0.10
+ personalScore * 0.08
- diversityPenalty
```

Category rank:

```text
categoryRank =
  controversyScore * 0.28
+ freshnessScore * 0.24
+ impactScore * 0.20
+ momentumScore * 0.16
+ verificationScore * 0.08
+ personalScore * 0.04
```

Major-topic rank:

```text
majorTopicRank =
  eventGroupImportance * 0.30
+ controversyScore * 0.25
+ freshnessScore * 0.20
+ momentumScore * 0.15
+ verificationScore * 0.10
```

Supported sort modes:

- `recommended`: default mixed rank for main page.
- `latest`: latest updated incidents.
- `controversial`: highest controversy.
- `highImpact`: highest public impact.
- `needsReview`: most claims needing evidence or admin review.
- `officialUpdated`: issues with official source, number, or verdict updates.
- `personalized`: stronger user interest weighting for logged-in users.

API examples:

```http
GET /v1/issues/home?sort=recommended
GET /v1/issues/home?topic=정치&sort=controversial
GET /v1/issues/home?majorTopic=2026%20지방선거&sort=latest
GET /v1/issues/home?eventGroup=선관위%20투표용지%20부족%20사태&sort=officialUpdated
```

Personalization rules:

- Logged-in users receive a bounded `personalScore`.
- Personalization should reorder similarly important items, not hide major public-interest incidents.
- Non-logged-in users use public-interest ranking without `personalScore`.
- User interest signals should decay over time so old interests do not dominate.

API response additions:

- `majorTopic`
- `majorTopicId`
- `eventGroup`
- `eventGroupId`
- `representativeImageUrl`
- `rankScore`
- `rankReason`

Example:

```json
{
  "title": "선관위 투표용지 부족 사태",
  "topic": "정치",
  "majorTopic": "2026 지방선거",
  "eventGroup": "선관위 투표용지 부족 사태",
  "representativeImageUrl": "https://example.com/image.jpg",
  "rankReason": "공식자료 반영, 후속 기사 증가, 수치 주장 충돌"
}
```

## Error Handling And Safety

- Classification confidence below threshold should create separate event groups rather than merge unrelated incidents.
- Representative image failures should fall back to frontend temporary images.
- Quality retries must be bounded by attempt count and cooldown.
- AI failures must fall back to deterministic keyword/entity logic.
- Synthesis must not publish unsupported claims as confirmed facts.
- Public labels must remain neutral and avoid partisan or defamatory wording.
- Admin logs should record classification, quality, image, synthesis, and ranking decisions in `AgentRun`.

## Rollout

1. Add schema and serializers while preserving existing API fields.
2. Backfill `majorTopic` and `eventGroup` for existing issues from title, topic, summary, and claim clusters.
3. Add image candidate extraction and automatic representative image selection.
4. Add issue quality scoring and bounded re-search jobs.
5. Add issue synthesis before cache refresh.
6. Add ranking service and sort query parameters.
7. Update frontend types and image rendering fallback.

The API should remain backward-compatible. New fields are additive.

## Testing Strategy

Backend tests should cover:

- Similar election incidents share `majorTopic` but not `eventGroup`.
- Same incident follow-up articles reuse the existing `eventGroup`.
- Low-confidence classification does not merge unrelated incidents.
- Quality report detects missing official sources, weak claim coverage, empty facts, and weak timeline.
- Quality retry creates targeted search keywords based on missing signals.
- Retry budget prevents infinite re-search.
- Image candidates are extracted, validated, scored, and selected.
- Broken or low-quality image candidates are rejected.
- Ranking modes produce expected ordering for recommended, latest, controversial, highImpact, needsReview, officialUpdated, and personalized.
- Logged-in personalization changes close-score ordering without suppressing major public-interest issues.
- Public API returns new fields while existing fields still match the frontend contract.

Frontend tests should cover:

- Issue cards use `representativeImageUrl` when present.
- Existing temporary image fallback still works.
- Major topic and event group fields can be displayed or used for links without breaking older payloads.
- Sort parameters are passed correctly from main, topic, and special collection views.

## Acceptance Criteria

- A high-volume incident discovered through search is not split into many unrelated issues when titles differ but incident signals match.
- Separate election controversies are grouped under `2026 지방선거` without being merged into one issue.
- Each public issue can expose a backend-selected representative image or fall back safely.
- Detail pages stop publishing thin filler sections and instead trigger bounded targeted re-search.
- The main page can sort by recommendation, latest update, controversy, impact, review need, official updates, and personalization.
- Category and major-topic views use ranking formulas suited to that context.
- Existing clients remain functional because all API changes are additive.
