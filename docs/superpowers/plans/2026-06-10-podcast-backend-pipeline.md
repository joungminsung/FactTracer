# Podcast Backend Pipeline

## Goal

Build the first backend slice for FactTracer podcasts:

- Podcast content is a separate product surface, not nested inside news articles.
- Episodes are generated and published automatically from verified public issues.
- Recommendation uses the existing issue ranking and personalization logic first.
- Episode detail supports a player drawer/full player with transcript, source context, and next queue.

## Scope

1. Add persistent podcast episode records.
2. Add deterministic script generation from issue cache data.
3. Add feed/detail endpoints for personalized, latest, ranking, featured, and category views.
4. Add a scheduler/job hook for automatic episode generation.
5. Keep TTS/audio generation as metadata-ready placeholder for this slice.

## Implementation Steps

1. Write failing tests for feed ranking, episode detail, automatic generation, and scheduler job wiring.
2. Add `PodcastEpisode` model columns and SQLite additive schema support.
3. Add serializers and Pydantic schemas for feed cards, detail scripts, queue, and generation responses.
4. Implement `app.services.podcasts.generator` using `rank_issues(..., sort="personalized")` and `build_issue_cache_payload`.
5. Add `app.api.routes.podcasts` under `/v1/podcasts`.
6. Wire `generate_podcasts` into jobs and scheduler.
7. Run targeted tests, then the backend test suite if feasible.

## Non-goals

- Real TTS/audio rendering.
- Paid personalization model training.
- Final UI behavior.
