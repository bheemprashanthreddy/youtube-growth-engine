# youtube-growth-engine

Private production-grade content intelligence foundation for the YouTube channel **CuriousSignal** (`@CuriousSignal-z9t`).

CuriousSignal explains strange, fast-moving, and surprising things people are suddenly searching for across technology, internet culture, money, science, business, global trends, and hidden systems. This repository supports private planning, human review, production queueing, local MVP rendering, and explicit private-only YouTube upload plumbing. Upload is disabled by default. It does not auto-publish, make videos public, use copyrighted media, require paid APIs, or promise revenue.

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

Phase 1.7 adds a production queue and scene planning layer. Approved review items can be explicitly converted into Shorts and long-form `VideoJob` packages.

Phase 2.0 adds a local rendering MVP. Ready `VideoJob` records can be rendered into local MP4 files, thumbnail PNGs, and render report JSON files using MoviePy, Pillow, NumPy, FFmpeg, and optional `edge-tts`. No upload or publishing happens in this phase.

Phase 2.1 adds real AI provider integration, provider status diagnostics, stronger content prompts, visual scene planning, premium Shorts layouts, designed thumbnails, render preview mode, and render quality warnings.

Phase 2.1.1 fixes the render contract for Shorts previews and full renders: 1080x1920 output, 30 FPS, duration-correct previews, reliable audio streams with silent fallback, visible captions, multiple-scene preview progression, and media inspection reports.

Phase 2.2 adds a visual asset layer for optional Pexels/Pixabay/local assets, local asset caching, scene-specific visual search queries, asset safety filtering, generated motion graphic fallback, thumbnail variants, and render report asset metadata.

Phase 2.3 adds modular voice narration with Edge TTS, optional OpenAI TTS, silent fallback, per-scene voice caching, and voice metadata in render reports.

Phase 2.4 adds batch rendering, retry/reset commands, output validation, batch reports, and render summaries.

Phase 2.5 adds an optional AI visual generation layer for scene images and thumbnail background concepts. It is disabled by default, provider-based, cached locally, and falls back to stock/local/generated motion graphics when unavailable.

Phase 3.0 adds explicit private-only YouTube upload plumbing. Phase 3.1 adds a final upload review checklist gate. Upload is disabled by default, requires a rendered and validated job, and never publishes publicly.

## Channel Strategy

Content pillars:

1. Internet trends explained
2. Technology and AI shifts
3. Money/business curiosity
4. Science/future discoveries
5. Strange global stories
6. Hidden systems behind everyday things

Audience psychology patterns include hidden reasons, why-now framing, surprising truths, future consequences, money behind the trend, internet behavior shifts, and fear of missing out. The system is built to avoid repetitive, low-effort, misleading, unsupported, or policy-risky AI content.

Publishing mode is private upload first with manual review before publish. This repo does not upload or publish content.

## Setup

Requires Python 3.11+.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[test]"
copy .env.example .env
```

Keep `.env` local. Do not commit secrets.

Local rendering also requires FFmpeg to be available on your system path. MoviePy uses FFmpeg to encode MP4 and audio outputs. If rendering fails with an encoder or binary error, install FFmpeg and rerun:

```bash
python -m app.cli render-summary
```

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

`ready_for_render` means the item is approved for local rendering. It does not upload to YouTube.

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
python -m app.cli normalize-job-titles
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

Each package includes the source review item, selected format, script or outline, metadata, thumbnail ideas, AI disclosure recommendation, and a structured scene plan. Phase 2.0 consumes these packages for local rendering.

Video job titles are normalized before packaging. Existing queued jobs can be cleaned with `python -m app.cli normalize-job-titles`, which removes duplicated question prefixes such as `Why Why` and avoids wrapping already complete explainer titles.

Scene planning rules:

- Shorts: 45-60 seconds, 9:16, 6-10 fast scenes
- Long-form: 6-10 minutes, 16:9, 8-15 sections

The production queue does not upload to YouTube, auto-publish, use copyrighted media, or include secrets.

## Local Rendering

Phase 2.1.1 renders Shorts at 1080x1920 and 30 FPS. Preview renders target 10-15 seconds with at least 3 scenes. Full Shorts renders target 45-60 seconds when the scene plan supports it. The renderer creates dark tech-explainer scenes, stronger typography, short captions, abstract visual metaphors, progress indicators, designed thumbnails, optional TTS narration through `edge-tts`, silent fallback audio if TTS is unavailable, and render quality warnings.

Render one job:

```bash
python -m app.cli render-job --id 1
```

Render ready jobs:

```bash
python -m app.cli render-ready --limit 1
```

Render summary:

```bash
python -m app.cli render-summary
```

Render a quick 10-15 second preview:

```bash
python -m app.cli render-preview --id 1
```

Inspect a rendered file:

```bash
python -m app.cli inspect-render --path renders/shorts/1_preview.mp4
```

API routes:

- `POST /jobs/{id}/render`
- `GET /jobs/{id}/render-report`

The job detail UI shows a Render Job button when the job is `ready_for_render`. Rendered jobs show the MP4 path, thumbnail path, and report path.

Rendered files are saved under:

```text
renders/
  shorts/{job_id}.mp4
  long/{job_id}.mp4
  thumbnails/{job_id}.png
  reports/{job_id}.json
```

Preview renders use `_preview` filenames in the same folders. Short jobs render as 9:16 vertical videos with an audio stream even when silent fallback is used. Long jobs render as 16:9 videos. The long-form renderer may produce a shortened MVP prototype so local rendering stays practical during development.

Render reports include `width`, `height`, `fps`, `duration_seconds`, `has_audio`, `scene_count`, `preview`, and warnings for empty scene text, generic labels such as `WHY NOW?`, captions that are too long, thumbnail text that is too long, or media metadata problems. These warnings are review signals, not automatic publishing approval.

This phase still does not upload videos, publish videos, schedule videos, or use copyrighted media.

## Voice Narration

Voice provider status:

```bash
python -m app.cli voice-provider-status
```

Generate voice files without rendering:

```bash
python -m app.cli generate-voice --id 1
```

Clear generated voice cache:

```bash
python -m app.cli clear-voice-cache --confirm
```

Edge TTS setup:

```text
VOICE_PROVIDER=edge
EDGE_TTS_VOICE=en-US-GuyNeural
EDGE_TTS_RATE=+0%
EDGE_TTS_PITCH=+0Hz
VOICE_CACHE_DIR=storage/voice
VOICE_MAX_SHORT_SECONDS=75
VOICE_MAX_LONG_SECONDS=180
VOICE_MAX_PREVIEW_SECONDS=30
```

OpenAI TTS setup:

```text
VOICE_PROVIDER=openai
OPENAI_API_KEY=your_key_here
OPENAI_TTS_MODEL=tts-1
OPENAI_TTS_VOICE=alloy
VOICE_CACHE_DIR=storage/voice
```

Silent fallback:

```text
VOICE_PROVIDER=silent
```

If Edge or OpenAI TTS fails, rendering falls back to silent WAV audio and still muxes an audio stream into the MP4. Voice files are cached by job id, scene number, scene text, provider, and voice profile. Render reports include provider, voice profile, voice files, fallback status, total audio duration, and warnings.

Long-form voice generation is capped for the MVP so accidental 6-10 minute or malformed scene plans cannot create huge WAV files. By default Shorts voice is capped at 75 seconds, previews at 30 seconds, and long-form full voice at 180 seconds. If a long-form job exceeds the cap, the voice metadata includes `long_form_voice_capped_for_mvp`.

## Batch Rendering

Render one job:

```bash
python -m app.cli render-job --id 1
```

Render ready jobs:

```bash
python -m app.cli render-ready --limit 1
```

Batch render:

```bash
python -m app.cli render-batch --limit 5
python -m app.cli render-batch --format short --limit 5
python -m app.cli render-batch --format long --limit 2
```

Inspect and report:

```bash
python -m app.cli render-summary
python -m app.cli inspect-render --path renders/shorts/1.mp4
python -m app.cli render-report --id 1
```

Retry failed jobs:

```bash
python -m app.cli reset-failed-renders --confirm
```

Batch reports are written to `renders/reports/batch_{timestamp}.json`. Rendering only processes `ready_for_render` jobs by default, continues if one job fails, records failures on the job, and does not upload anything.

## Private YouTube Upload

YouTube upload is private-only and disabled by default. It is never automatic.

Status:

```bash
python -m app.cli youtube-status
```

OAuth setup:

1. Create Google OAuth Desktop credentials for the YouTube Data API.
2. Save the downloaded file as `client_secret.json` at the repo root, or set `YOUTUBE_CLIENT_SECRET_FILE`.
3. Run:

```bash
python -m app.cli youtube-auth
```

Upload configuration:

```text
YOUTUBE_UPLOAD_ENABLED=false
YOUTUBE_PRIVACY_STATUS=private
YOUTUBE_CLIENT_SECRET_FILE=client_secret.json
YOUTUBE_TOKEN_FILE=storage/youtube/token.json
YOUTUBE_CATEGORY_ID=28
YOUTUBE_MADE_FOR_KIDS=false
YOUTUBE_DEFAULT_LANGUAGE=en
YOUTUBE_NOTIFY_SUBSCRIBERS=false
YOUTUBE_DAILY_UPLOAD_LIMIT=3
YOUTUBE_REQUIRE_PRIVATE=true
```

Private upload one rendered job:

```bash
python -m app.cli upload-checklist --job-id 1
python -m app.cli select-thumbnail --job-id 1 --variant a
python -m app.cli mark-upload-reviewed --job-id 1
python -m app.cli upload-video --job-id 1
```

Private upload rendered jobs with a limit:

```bash
python -m app.cli upload-ready --limit 1
```

Upload summary:

```bash
python -m app.cli upload-summary
```

Upload reports are written under `outputs/YYYY-MM-DD/uploads/{job_id}.json`. Upload checks block jobs that are not rendered, missing files, missing thumbnails, missing metadata, missing final upload review approval, disabled by config, non-private, already uploaded, above daily limit, or otherwise unsafe. Private upload uses `privacyStatus=private`; if `YOUTUBE_REQUIRE_PRIVATE=true`, any non-private privacy setting blocks upload. The optional `--bypass-review` flag only bypasses the final review gate; it does not bypass private-only enforcement.

Final upload review checklist:

```bash
python -m app.cli upload-checklist --job-id 1
python -m app.cli select-thumbnail --job-id 1 --variant a
python -m app.cli mark-upload-reviewed --job-id 1
```

The checklist previews final metadata, selected thumbnail, voice metadata, visual asset/license metadata, AI disclosure review status, source/license review status, rendered video inspection status, private privacy mode, upload enablement, authentication, and final approval. The UI job detail page shows the same checklist and only shows the private upload action after the checklist passes.

Credentials and tokens must stay local. `client_secret.json`, `token.json`, `credentials.json`, `storage/youtube/`, `outputs/`, `renders/`, and `storage/` are ignored by Git.

## Operator Workflow

```bash
python -m app.cli run-daily
uvicorn app.main:app --reload --port 8001
python -m app.cli create-jobs --approved
python -m app.cli render-batch --format short --limit 3
python -m app.cli render-summary
python -m app.cli inspect-render --path renders/shorts/1.mp4
python -m app.cli youtube-auth
python -m app.cli youtube-status
python -m app.cli upload-checklist --job-id 1
python -m app.cli select-thumbnail --job-id 1 --variant a
python -m app.cli mark-upload-reviewed --job-id 1
python -m app.cli upload-video --job-id 1
```

Review content in `/review`, jobs in `/jobs`, and uploads in `/uploads`. YouTube Studio remains the place to manually review and publish later.

## Visual Assets

Phase 2.2 can optionally use safe free stock assets to support scenes. Stock footage or images never replace CuriousSignal overlays, captions, progress bars, or explainer graphics. If no provider is configured, rendering uses local generated motion graphics fallback.

Visual provider status:

```bash
python -m app.cli visual-provider-status
```

Configure Pexels:

```text
VISUAL_ASSET_PROVIDER=pexels
PEXELS_API_KEY=your_key_here
ALLOW_STOCK_ASSETS=true
VISUAL_ASSET_CACHE_DIR=storage/assets
```

Configure Pixabay:

```text
VISUAL_ASSET_PROVIDER=pixabay
PIXABAY_API_KEY=your_key_here
ALLOW_STOCK_ASSETS=true
VISUAL_ASSET_CACHE_DIR=storage/assets
```

Local fallback:

```text
VISUAL_ASSET_PROVIDER=local
VISUAL_ASSET_CACHE_DIR=storage/assets
```

Place local assets under `storage/assets/local/`. Verify rights before publishing any local media.

Safety rules:

- Avoid political figures, violence, weapons, disasters, explicit content, medical claims, minors, and brand-heavy visuals.
- Do not use real identifiable people for sensitive or current-event claims.
- Prefer abstract technology, business, logistics, science, environment, data, and system visuals.
- Provider failures never crash rendering; the renderer falls back to generated visuals.
- Render reports include `assets_used`, source URLs when available, license notes, and whether generated fallback was used.

Thumbnail variants:

```bash
python -m app.cli generate-thumbnail-variants --id 1
```

This writes:

```text
renders/thumbnails/{job_id}_a.png
renders/thumbnails/{job_id}_b.png
renders/thumbnails/{job_id}_c.png
```

Variant A is bold text plus abstract metaphor, variant B can use a stock/local/generated visual, and variant C is a minimal premium brand layout.

## AI Visual Generation

Phase 2.5 can optionally generate AI scene images and AI thumbnail background concepts. It is disabled by default and rendering still works without any AI image provider.

Status:

```bash
python -m app.cli ai-visual-status
```

Generate scene images for a job:

```bash
python -m app.cli generate-scene-images --id 1
```

Generate AI thumbnail background concepts:

```bash
python -m app.cli generate-ai-thumbnails --id 1
```

Clear cached AI visuals:

```bash
python -m app.cli clear-ai-visual-cache --confirm
```

Default disabled configuration:

```text
AI_VISUALS_ENABLED=false
AI_VISUAL_PROVIDER=none
AI_VISUAL_CACHE_DIR=storage/ai_visuals
AI_SCENE_IMAGES_ENABLED=false
AI_THUMBNAILS_ENABLED=false
AI_VIDEO_CLIPS_ENABLED=false
```

OpenAI image generation:

```text
AI_VISUALS_ENABLED=true
AI_VISUAL_PROVIDER=openai
AI_SCENE_IMAGES_ENABLED=true
AI_THUMBNAILS_ENABLED=true
OPENAI_API_KEY=your_key_here
OPENAI_IMAGE_MODEL=gpt-image-1
```

Replicate or future provider configuration:

```text
AI_VISUAL_PROVIDER=replicate
REPLICATE_API_TOKEN=your_token_here
REPLICATE_IMAGE_MODEL=provider/model-name
REPLICATE_VIDEO_MODEL=provider/video-model-name
```

AI visuals are cached by prompt hash under `storage/ai_visuals/` and are not regenerated unless force behavior is added later. Generated files live under ignored storage/render folders and should not be committed.

Safety rules:

- Do not generate realistic depictions of real people, public figures, political figures, minors, weapons, gore, disasters, explicit content, medical claims, or misleading realistic news scenes.
- Prefer abstract technology, business, science, logistics, finance, data, interface, and systems visuals.
- Avoid text baked into generated thumbnail backgrounds; the thumbnail renderer overlays the final text.
- If AI-generated visuals are used, render and upload reports mark AI disclosure review as required.

Cost note: OpenAI, Replicate, and similar image providers may bill per generation. Keep `AI_VISUALS_ENABLED=false` unless you intentionally want to generate assets.

Visual priority during rendering:

1. AI-generated scene image when enabled and available
2. Pexels/Pixabay stock asset when enabled and available
3. local asset folder
4. generated motion graphics fallback

## Optional MoneyPrinterTurbo Integration

Phase 2.6 adds MoneyPrinterTurbo as an optional external render engine adapter. This repo remains the brain and operator layer: trend scanning, scoring, review, approval, video jobs, source/risk checks, render reports, and private-only upload checks stay here.

MoneyPrinterTurbo is not vendored into this repository and is not assumed to be installed or running.

Clone MoneyPrinterTurbo separately:

```bash
git clone https://github.com/harry0703/MoneyPrinterTurbo.git C:\MVP\MoneyPrinterTurbo
```

Start the MoneyPrinterTurbo API separately according to its own README. Then configure this repo:

```text
RENDER_ENGINE=moneyprinterturbo
MONEYPRINTERTURBO_ENABLED=true
MONEYPRINTERTURBO_BASE_URL=http://127.0.0.1:8080
MONEYPRINTERTURBO_USE_BACKGROUND_MUSIC=false
```

Adapter endpoint paths are configurable because the exact external API schema may differ by version:

```text
MONEYPRINTERTURBO_CREATE_ENDPOINT=/api/v1/videos
MONEYPRINTERTURBO_STATUS_ENDPOINT=/api/v1/tasks/{task_id}
MONEYPRINTERTURBO_DOWNLOAD_ENDPOINT=/api/v1/videos/{task_id}/download
```

The upstream public docs show the FastAPI service on port `8080`, Swagger/ReDoc at `/docs` and `/redoc`, the `/api/v1/` prefix, `POST /api/v1/videos` for async video generation, and task status polling under `/api/v1/tasks/{task_id}`. Confirm the exact request and response schema against your locally running MoneyPrinterTurbo version before enabling production use.

Check status:

```bash
python -m app.cli render-engine-status
python -m app.cli moneyprinterturbo-status
```

Preview the JSON request without sending it:

```bash
python -m app.cli moneyprinterturbo-request-preview --id 1
```

Render with a specific engine:

```bash
python -m app.cli render-job --id 1 --engine native
python -m app.cli render-job --id 1 --engine moneyprinterturbo
```

MoneyPrinterTurbo outputs are imported into the standard paths:

```text
renders/shorts/{job_id}.mp4
renders/long/{job_id}.mp4
renders/thumbnails/{job_id}.png
renders/reports/{job_id}.json
```

Render reports include the render engine, whether an external service was used, request and response payload paths, imported output paths, warnings, and copyright/music flags.

Copyright and review rules:

- Do not use MoneyPrinterTurbo bundled/default background music unless licensing is explicitly confirmed.
- `MONEYPRINTERTURBO_USE_BACKGROUND_MUSIC=false` is the default.
- Outputs still require human review before YouTube upload.
- Private upload only remains enforced by this repo.
- No public upload or auto-publish behavior is added.

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
- `GET /jobs`
- `GET /jobs/{id}`
- `POST /review/items/{id}/create-short-job`
- `POST /review/items/{id}/create-long-job`
- `POST /review/items/{id}/create-both-jobs`
- `POST /jobs/{id}/regenerate-scene-plan`
- `POST /jobs/{id}/mark-ready-for-render`
- `POST /jobs/{id}/render`
- `POST /jobs/{id}/render-preview`
- `POST /jobs/render-batch`
- `GET /jobs/{id}/render-report`
- `GET /render/summary`
- `GET /visual-provider/status`
- `POST /jobs/{id}/thumbnail-variants`
- `GET /jobs/{id}/upload-checklist`
- `POST /jobs/{id}/mark-upload-reviewed`
- `POST /jobs/{id}/select-thumbnail`
- `POST /jobs/{id}/upload-private`
- `GET /youtube/status`
- `GET /uploads`
- `GET /uploads/{id}`
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

The provider interface lives in `app/providers/`. Phase 2.1 supports real provider calls when configured and falls back to deterministic mock output when keys or base URLs are missing.

Set provider selection in `.env`:

```text
MODEL_PROVIDER=mock
```

Provider status:

```bash
python -m app.cli provider-status
```

Gemini:

```text
MODEL_PROVIDER=gemini
GEMINI_API_KEY=your_key_here
```

OpenAI:

```text
MODEL_PROVIDER=openai
OPENAI_API_KEY=your_key_here
```

Ollama:

```text
MODEL_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
```

If `MODEL_PROVIDER` is set to `gemini`, `openai`, or `ollama` but the required key or base URL is missing, the CLI reports the missing configuration and the app uses mock fallback output. Do not commit real secrets.

## Tests

```bash
pytest
```

## Roadmap

- Phase 2.0: local video rendering MVP
- Phase 2.1: real AI provider integration and premium render templates
- Phase 2.1.1: render resolution, preview duration, audio, captions, and media inspection fixes
- Phase 2.2: visual asset provider layer, scene-specific assets, and thumbnail variants
- Phase 2.3: modular voice and TTS providers
- Phase 2.4: batch render workflow and validation
- Phase 2.5: optional AI scene images and thumbnail concepts
- Phase 3.0: explicit private-only YouTube upload
- Phase 2.x: stronger timing, narration quality, motion polish, and render performance
- Phase 3: private YouTube upload
- Phase 4: analytics feedback loop
- Phase 5: automated scheduling after quality validation
