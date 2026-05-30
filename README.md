# youtube-growth-engine

Private production-grade content intelligence foundation for the YouTube channel **CuriousSignal** (`@CuriousSignal-z9t`).

CuriousSignal explains strange, fast-moving, and surprising things people are suddenly searching for across technology, internet culture, money, science, business, global trends, and hidden systems. This repository supports private planning and human review only. It does not render videos, upload to YouTube, auto-publish, use copyrighted media, or promise revenue.

## Project Purpose

Phase 1.5 adds real trend intelligence to the Phase 1 trend-to-script engine:

- source-based trend ingestion
- normalized `TrendItem` records
- cross-source topic deduplication
- opportunity scoring with human-readable explanations
- raw and scored trend outputs
- review-ready Shorts scripts and long-form outlines
- quality gate decisions: `approved`, `needs_review`, or `rejected`

Phase 1.6 adds a human review workflow before any topic can become a future video job.

Phase 1.6.1 adds topic quality filtering and topic expansion so raw autocomplete phrases cannot become final video topics unless they are cleaned, accepted or transformed, and scored above the configured thresholds.

Phase 1.6.2 adds review deduplication, lifecycle cleanup commands, and stronger safety blocking for lyric fragments, weak meme phrases, deadly or violent topics, and current-event topics without source support.

Phase 1.7 adds a production queue and scene planning layer. Approved review items can be explicitly converted into Shorts and long-form `VideoJob` packages for a future renderer. No rendering, upload, or publishing happens in this phase.

## Channel Strategy

Content pillars:

1. Internet trends explained
2. Technology and AI shifts
3. Money/business curiosity
4. Science/future discoveries
5. Strange global stories
6. Hidden systems behind everyday things

Audience psychology patterns include hidden reasons, why-now framing, surprising truths, future consequences, money behind the trend, internet behavior shifts, and fear of missing out. The system is built to avoid repetitive, low-effort, misleading, unsupported, or policy-risky AI content.

Publishing mode is private upload first with manual review before publish. Phase 1.5 does not perform video rendering or upload.

## Setup

Requires Python 3.11+.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[test]"
copy .env.example .env
```

Keep `.env` local. Do not commit secrets.

## Trend Sources

Trend source toggles live in `configs/trend_sources.yaml`.

Sources that work without API keys:

- `manual_seed`: always available and used as the safe baseline
- `youtube_suggestions`: uses a lightweight public suggestions endpoint; failures are logged and skipped
- `wikipedia_current_events`: uses the Wikipedia API; failures are logged and skipped
- `hackernews`: uses the public HN Algolia API; failures are logged and skipped

Sources requiring configuration:

- `youtube_search`: requires `YOUTUBE_API_KEY`
- `reddit`: requires `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, and `REDDIT_USER_AGENT`
- `rss`: requires comma-separated `NEWS_RSS_URLS`
- `pytrends`: currently optional and skipped unless implemented with the dependency intentionally installed

Providers are conservative: missing keys or network failures do not crash the pipeline. They log a warning and continue with other sources.

## YouTube API Key

Add this to `.env`:

```text
YOUTUBE_API_KEY=your_key_here
```

The current provider only performs bounded search requests configured in `configs/trend_sources.yaml`. It does not upload, publish, or modify YouTube content.

## Reddit Credentials

Add these to `.env`:

```text
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret
REDDIT_USER_AGENT=CuriousSignalTrendScanner/0.1
```

The Reddit provider is wired for safe credential checks and intentionally avoids unauthenticated scraping. Add OAuth fetch logic behind `app/providers/trends/reddit_provider.py` before enabling production Reddit ingestion.

## Run Trend Scan

```bash
python -m app.cli scan-trends
```

Outputs are written to:

```text
outputs/YYYY-MM-DD/trends_raw.json
outputs/YYYY-MM-DD/trends_rejected.json
outputs/YYYY-MM-DD/trends_cleaned.json
outputs/YYYY-MM-DD/trends_scored.json
outputs/YYYY-MM-DD/daily_run.json
```

The scan command prints raw trend count, rejected trend count, accepted/transformed count, and top scored count.

## Topic Quality Filter

Before scoring, every raw provider phrase goes through `app/services/topic_quality_filter.py` and `app/services/topic_expander.py`.

The filter rejects or heavily penalizes:

- too-short phrases
- vague autocomplete fragments
- incomplete questions
- unclear pronouns without context
- typo-heavy or nonsensical phrases
- low-explanatory-value phrases
- unsafe adult, violent, hateful, or sensitive content
- lyric fragments or meme phrases without clear trend context
- deadly or violent topics unless explicitly source-supported
- specific-person allegations without verified context
- unsupported current-event claims
- weak alignment with CuriousSignal pillars

Examples rejected:

- `why is it spicy`
- `why is he lying`
- `why is he lying wong`
- `why is she mad`
- `what happened to him`
- `who is he`
- `What Love Haddaway Reveals About A Larger Trend`
- `Internet Trends That Were Deadly`

Examples transformed:

- `why is english so hard` -> `Why English feels so difficult even for advanced learners`
- `why is the government shutdown` -> `Why government shutdowns happen and how they affect everyday people`
- `why are people buying gold` -> `Why people suddenly buy gold when the economy feels uncertain`
- `why are ai companions popular` -> `Why AI companion apps are becoming popular so quickly`
- `AI Search Replacing Blue Links` -> `Why AI search engines are changing how people find information online`

Configured thresholds live in `configs/scoring.yaml`:

- `min_topic_quality_score: 70`
- `min_final_score: 75`

Quality report:

```bash
python -m app.cli quality-report
```

It prints total raw phrases, rejected count, accepted count, transformed count, top rejection reasons, and top expanded topics.

## Run Daily Job

```bash
python -m app.cli run-daily
```

The daily job runs trend scan, selects top opportunities, generates content plans, and writes:

```text
outputs/YYYY-MM-DD/
```

Each selected topic receives a structured JSON file plus `manifest.json`.

Generated content plans are also persisted as review items in SQLite with this lifecycle:

- `generated`
- `needs_review`
- `approved`
- `rejected`
- `ready_for_render`

`ready_for_render` only means the item is approved for a future rendering phase. This repo still does not render videos or upload to YouTube.

## Review Dashboard

Start the API:

```bash
uvicorn app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000/review
```

The dashboard shows generated items, status filters, score sorting, topic, pillar, quality risk, and approval status. The detail page shows the trend reason, scoring explanation, Shorts script, long-form outline, title options, description, hashtags, thumbnail ideas, quality gate reasons, AI disclosure recommendation, action buttons, and reviewer notes.

Phase 1.6.1 also shows raw phrase, expanded topic, quality score, quality status, quality reasons, and risk flags.
Phase 1.6.2 also shows content key, duplicate status, source support warnings, and lifecycle warnings.

Review actions:

- Approve
- Reject
- Mark ready for render
- Regenerate script
- Regenerate metadata
- Save reviewer notes

Regeneration in Phase 1.6 updates text fields only. It does not create video assets or publish anything.

CLI summary:

```bash
python -m app.cli review-summary
```

It prints total unique generated items, duplicate count, invalid lifecycle count, approved count, rejected count, ready-for-render count, and the top 5 items by score.

Lifecycle rules:

- `run-daily` creates review items as `needs_review`
- only `approved` items can become `ready_for_render`
- `ready_for_render` requires an approval timestamp
- repeated `run-daily` executions update existing review items by `content_key` instead of creating duplicates

Review cleanup commands:

```bash
python -m app.cli reset-review-statuses
python -m app.cli dedupe-review-items
python -m app.cli clear-dev-data --confirm
```

`reset-review-statuses` fixes invalid `ready_for_render` rows without approval history. `dedupe-review-items` keeps the highest-scoring duplicate review item. `clear-dev-data --confirm` clears generated local SQLite review/job data only; it does not delete code.

## Production Queue

Phase 1.7 introduces `VideoJob` records for production planning. A review item must be `approved` or `ready_for_render` before a job can be created. `run-daily` never creates video jobs automatically.

Create jobs from the review detail page after approving an item:

- Create Shorts Job
- Create Long-Form Job
- Create Both Jobs

CLI job creation:

```bash
python -m app.cli create-jobs --approved
python -m app.cli create-jobs --approved --format short
python -m app.cli create-jobs --approved --format long
python -m app.cli jobs-summary
```

API routes:

- `GET /jobs`
- `GET /jobs/{id}`
- `POST /review/items/{id}/create-short-job`
- `POST /review/items/{id}/create-long-job`
- `POST /review/items/{id}/create-both-jobs`
- `POST /jobs/{id}/regenerate-scene-plan`
- `POST /jobs/{id}/mark-ready-for-render`

Video job JSON packages are saved to:

```text
outputs/YYYY-MM-DD/video_jobs/{job_id}.json
```

Each package includes the source review item, selected format, script or outline, metadata, thumbnail ideas, AI disclosure recommendation, and a structured scene plan. Phase 2 will consume these packages for rendering.

Scene planning rules:

- Shorts: 45-60 seconds, 9:16, 6-10 fast scenes
- Long-form: 6-10 minutes, 16:9, 8-15 sections

The production queue still does not render videos, upload to YouTube, auto-publish, use copyrighted media, or include secrets.

## Run API

```bash
uvicorn app.main:app --reload
```

Routes:

- `GET /health`
- `POST /run/trend-scan`
- `POST /run/daily`
- `GET /trends/raw`
- `GET /trends/scored`
- `GET /topics/top`
- `GET /review/items`
- `GET /review/items/{id}`
- `POST /review/items/{id}/approve`
- `POST /review/items/{id}/reject`
- `POST /review/items/{id}/mark-ready-for-render`
- `POST /review/items/{id}/notes`
- `POST /review/items/{id}/regenerate-script`
- `POST /review/items/{id}/regenerate-metadata`
- `GET /topics`
- `GET /scripts`
- `GET /outputs/latest`

Docker Compose:

```bash
docker compose up --build
```

## Scoring

Each deduplicated trend receives an `OpportunityScore`:

- `trend_velocity`
- `cross_source_validation`
- `curiosity_gap`
- `novelty`
- `emotional_pull`
- `search_intent_strength`
- `saturation_risk`
- `monetization_fit`
- `short_format_fit`
- `long_format_fit`
- `policy_risk`
- `originality_potential`
- `final_score`

Topics seen across multiple sources get a validation boost. Risk dimensions reduce the final score. Every scored topic includes an explanation describing why it was selected, needs review, or was rejected.

## Review Output Quality

Open the latest dated folder under `outputs/`. Review:

- `trends_raw.json` for source provenance and noisy inputs
- `trends_scored.json` for scoring rationale, source count, and risk flags
- topic and pillar fit
- research brief and unsupported claim notes
- Shorts script and long-form outline
- title options for misleading-risk phrasing
- AI disclosure recommendation
- quality gate status and notes

Anything marked `needs_review` or `rejected` should not move forward without human editorial judgment.

## LLM Providers

The provider interface lives in `app/providers/`. Phase 1.5 keeps the deterministic mock provider as the safe default and includes stubs for OpenAI, Gemini, and Ollama. Implement provider-specific API calls behind the `LLMProvider` interface before using real models.

Set provider selection in `.env`:

```text
MODEL_PROVIDER=mock
```

## Tests

```bash
pytest
```

## Roadmap

- Phase 2: video rendering
- Phase 3: private YouTube upload
- Phase 4: analytics feedback loop
- Phase 5: automated scheduling after quality validation
