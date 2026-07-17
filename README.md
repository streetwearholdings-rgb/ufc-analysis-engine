# UFC Analysis Engine

The UFC Analysis Engine is a Python 3.12/FastAPI service for explainable fighter profiles, historical ratings, style analysis, performance scoring, matchup comparisons, and leakage-safe model training. It produces analysis features and model evaluation only: it does not produce bets, prices, stakes, parlays, or recommendations.

## Architecture

HTTP routes validate requests and delegate to services. Services coordinate repositories and pure modules under `app/calculations`; SQLAlchemy models own persistence. Calculations are deterministic and versioned with `MODEL_VERSION`. PostgreSQL is the production database and Supabase can supply the hosted PostgreSQL connection.

Key packages:

- `app/api`: thin FastAPI routes
- `app/services`: workflow orchestration
- `app/repositories`: parameterized SQLAlchemy access
- `app/calculations`: testable domain formulas
- `app/database/models`: source and derived tables
- `scripts`: seeding, validation, and rebuild commands

## Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
docker compose up -d db
alembic upgrade head
uvicorn app.main:app --reload
```

Supabase users should set `DATABASE_URL` to its PostgreSQL SQLAlchemy URL. `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` are reserved for later Supabase API integrations and are not needed for direct SQLAlchemy access.

## Environment variables

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | SQLAlchemy PostgreSQL URL |
| `SUPABASE_URL` | Hosted Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Server-only Supabase credential; never expose publicly |
| `APP_ENV`, `LOG_LEVEL` | Runtime environment and logging level |
| `MODEL_VERSION` | Version written to derived analysis records |
| `ELO_INITIAL_RATING`, `ELO_K_FACTOR` | Elo baseline and update magnitude |
| `ELO_METHOD_MULTIPLIER`, `ELO_DOMINANCE_MULTIPLIER`, `ELO_CONTEXT_MULTIPLIER` | Elo context controls |
| `RECENCY_HALF_LIFE_DAYS` | Exponential decay half-life; default 730 days |
| `MINIMUM_OPPONENT_SAMPLE` | Opponent-adjustment sample threshold |
| `API_KEY` | Required `X-API-Key` for mutation/rebuild routes |
| `CORS_ALLOWED_ORIGINS` | JSON array or comma-separated allowed origins |
| `ODDS_API_KEY` | Server-only The Odds API credential, required by odds ingestion |
| `ODDS_API_BASE_URL`, `ODDS_API_SPORT_KEY` | Provider URL and optional MMA sport-key override |
| `ODDS_API_REGIONS` | Comma-separated bookmaker regions; defaults to `au` |
| `ODDS_API_TIMEOUT_SECONDS`, `ODDS_API_MAX_RETRIES` | Provider timeout and transient retry controls |
| `ODDS_API_STALE_AFTER_MINUTES` | Maximum bookmaker update age for fresh market reads |
| `ODDS_API_LOW_QUOTA_WARNING` | Remaining-request threshold for warning logs |
| `ODDS_EVENT_MATCH_TOLERANCE_HOURS` | Provider/internal event-date matching tolerance |
| `CONTEXT_ENGINE_ENABLED` | Enables the optional reviewed-context adjustment layer |
| `CONTEXT_MAX_INDIVIDUAL_ADJUSTMENT` | Per-signal probability-adjustment cap; default `0.02` |
| `CONTEXT_MAX_CATEGORY_ADJUSTMENT` | Per-category cap; default `0.03` |
| `CONTEXT_MAX_TOTAL_ADJUSTMENT` | Total relative context cap; default `0.05` |
| `CONTEXT_MIN_AUTO_APPROVAL_CONFIDENCE` | Minimum confidence for eligible official auto-approval |
| `CONTEXT_MIN_AUTO_APPROVAL_SOURCE_RELIABILITY` | Minimum source reliability for auto-approval |
| `CONTEXT_DEFAULT_MATCH_TOLERANCE_HOURS` | Context event matching tolerance |
| `CONTEXT_REQUIRE_REVIEW_FOR_INJURY` | Keeps injury context pending until human review |
| `CONTEXT_REQUIRE_REVIEW_FOR_SUBJECTIVE_SIGNALS` | Requires review for subjective context |
| `CONTEXT_RECENCY_DECAY_ENABLED` | Enables category-specific exponential decay |

## Database and operations

```bash
alembic upgrade head
python -m scripts.seed_sample_data
python -m scripts.validate_dataset
python -m scripts.rebuild_all_profiles
python -m scripts.recalculate_fighter <fighter-uuid>
```

The seed command is idempotent and uses fictional data only. Dataset validation exits non-zero for invalid rounds, impossible landed/attempted totals, or self-matchups.

## API

Public reads:

```text
GET /health
GET /api/v1/fighters/{fighter_id}
GET /api/v1/fighters/{fighter_id}/rolling-stats
GET /api/v1/fighters/{fighter_id}/ratings
GET /api/v1/fighters/{fighter_id}/style
GET /api/v1/fighters/{fighter_id}/performances
GET /api/v1/matchups/{fighter_a_id}/{fighter_b_id}
GET /api/v1/events/upcoming?from_date=YYYY-MM-DD&limit=25
GET /api/v1/events/{event_id}/fights
GET /api/v1/fights/{fight_id}/analysis
GET /api/v1/context/reviews/pending?limit=50&offset=0
```

Protected calculations:

```bash
curl -X POST -H "X-API-Key: $API_KEY" http://localhost:8000/api/v1/calculations/fighters/FIGHTER_UUID
curl -X POST -H "X-API-Key: $API_KEY" http://localhost:8000/api/v1/calculations/rebuild

curl -X POST -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"reviewer":"internal-reviewer","reason":"Source verified"}' \
  http://localhost:8000/api/v1/admin/context/signals/SIGNAL_UUID/approve

curl -X POST -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"reviewer":"internal-reviewer","reason":"Evidence rejected"}' \
  http://localhost:8000/api/v1/admin/context/signals/SIGNAL_UUID/reject
```

Interactive OpenAPI documentation is available at `/docs`; the schema is available at `/openapi.json`. Administrative operations declare the `X-API-Key` security scheme. Consolidated fight analysis is read-only and composes the latest persisted contextual prediction, matchup confidence, fresh best moneyline odds, market implied probability, expected value, context explanations, pending reviews, versions, timestamps, and quality warnings. It returns `409` until both fighters have persisted prediction records.

Unknown resources return 404, incompatible matchup profiles return 409, invalid identifiers return 422, and invalid API keys return 401. Internal exceptions are not returned verbatim.

## Calculation methodology

- Rates use observed seconds, never scheduled bout time. Per-minute values multiply totals by `60 / elapsed_seconds`; per-15 values use `900 / elapsed_seconds`. Zero exposure returns zero.
- Last-3 and last-5 profiles select completed fights in reverse chronological order. No contests and overturned results are excluded from win-rate denominators.
- Recency uses `exp(-lambda * days)` where `lambda = ln(2) / RECENCY_HALF_LIFE_DAYS`.
- Performance weights are 30% damage, 20% striking, 20% grappling, 15% effective control, and 15% result quality. Components are clamped to 0–100. Control time is multiplied by activity and advancement factors.
- Elo uses `1 / (1 + 10 ** ((opponent - fighter) / 400))`. Histories are chronological and capture pre-fight values; draws score 0.5 and no contests/overturns do not update ratings.
- Opponent offence is adjusted as `output / shrunk_opponent_allowed * division_allowed`. Defensive suppression is expected output minus actual output. Only strictly pre-fight snapshots are accepted.
- Style values are percentile ranked inside weight class. Reliability from fighter sample, cohort sample, and data quality shrinks uncertain values toward 50.
- Matchups report attribute differences and cross-fighter wrestling, knockout, submission, and late-pressure interactions. Confidence is data quality, not outcome probability.

## Tests and quality

```bash
ruff check .
mypy app scripts tests
pytest --cov=app.calculations --cov-report=term-missing --cov-fail-under=80
```

GitHub Actions runs these checks on every push and pull request.

## Phase 3 training pipeline

Phase 3 reconstructs post-fight historical snapshots, then selects only snapshots strictly before each target fight. Draws, no contests, overturned results, and fights without a valid winner are excluded from supervised records.

```bash
python -m scripts.phase3 rebuild-snapshots
python -m scripts.phase3 build-training-dataset --output-csv exports/phase3_training.csv
python -m scripts.phase3 train-baseline --include-mirrored-rows
python -m scripts.phase3 evaluate --include-mirrored-rows
```

Use `--start-date`, `--end-date`, repeated `--weight-class`, and `--min-data-quality` filters to select a cohort. Destructive rebuilds require the explicit `--reset` flag. Training uses chronological train/validation/test partitions; preprocessing fits on training data and optional probability calibration fits on validation data.

## Phase 4A moneyline odds

Phase 4A integrates The Odds API v4 `h2h` market using decimal prices. Obtain a key from The Odds API account portal and set it only in the server environment:

```bash
cp .env.example .env
# Edit .env and set ODDS_API_KEY; never commit that file.
alembic upgrade head
python -m scripts.odds ingest --dry-run
python -m scripts.odds ingest
```

Dry-run performs sport discovery, one upcoming-odds request, validation, matching, and normalisation without database writes. Set `ODDS_API_SPORT_KEY` to a known active MMA key to avoid the discovery request. The client reads quota headers from normal responses, includes them in the summary, and warns below `ODDS_API_LOW_QUOTA_WARNING`; it never makes a quota-only request.

Example non-sensitive output:

```json
{"provider_events_received": 12, "provider_events_matched": 10, "provider_events_unmatched": 2, "snapshots_inserted": 38, "duplicate_snapshots_skipped": 4, "requests_remaining": 450}
```

Matching normalises case, spacing, punctuation, quoted nicknames, accents, apostrophes, and hyphens, then requires the complete fighter pair within the configured event-date tolerance. Reversed provider ordering is supported. Ambiguous and unmatched provider events are retained in `odds_provider_events` with a reviewable status; their snapshots are never linked to an internal fighter.

The `OddsMarketService` is the provider-independent analysis-engine read boundary. It returns the best current decimal price per fighter, raw implied probability, bookmaker update time, age, and bookmaker count. It does not produce betting recommendations.

Current limitations: moneyline only; no aliases or fuzzy matching; the source event entity stores a date rather than an exact scheduled timestamp, so matching precision is date-based; no automatic polling or rematching job; and no public odds API route. Operational scheduling should invoke the CLI at an externally controlled cadence.

## Phase 5 Context Engine

The Context Engine stores sourced, time-sensitive evidence separately from the statistical model. It supports weight-cut, short-notice, opponent-change, weight-class, layoff, turnaround, recent-damage, medical, injury, training-camp, travel, environment, and career-status context. The complete validated label registry is centralized in `app/context/registry.py`.

Sources retain publication and capture timestamps, default and overridden reliability, and supporting text. Duplicate claims share one signal while retaining multiple sources. Opposing directions for the same fighter, fight, category, and period are marked contradicted and excluded until reviewed. Documents are content-hash deduplicated.

Manual workflow:

```bash
alembic upgrade head

python -m scripts.context add \
  --fighter FIGHTER_UUID --fight-id FIGHT_UUID \
  --category short_notice --label short_notice_days --direction negative \
  --severity 0.8 --confidence 0.95 --value 8 \
  --source-type official_ufc --publisher UFC --source-title "Official bout update" \
  --published-at 2026-07-10T08:00:00Z --captured-at 2026-07-10T08:05:00Z \
  --occurred-at 2026-07-10T08:00:00Z --supporting-text "Replacement confirmed."

python -m scripts.context list-pending
python -m scripts.context review SIGNAL_UUID --approve \
  --reviewer internal-reviewer --reason "Official source verified" \
  --reviewed-at 2026-07-10T09:00:00Z

python -m scripts.context features \
  --fighter-id FIGHTER_UUID --fight-id FIGHT_UUID --as-of 2026-07-11T00:00:00Z

python -m scripts.context predict \
  --fight-id FIGHT_UUID --fighter-a-id FIGHTER_A_UUID --fighter-b-id FIGHTER_B_UUID \
  --probability 0.58 --as-of 2026-07-11T00:00:00Z
```

Manual entries always begin pending. Only configured objective labels from high-confidence official, non-manual evidence can auto-approve. Injuries, rumours, inferences, social reports, subjective signals, and contradictions require review. Reviews are append-only.

Recency uses `exp(-ln(2) * age_days / half_life_days)` with centrally defined category half-lives. Fight-only context is scoped to its fight, expiry produces zero weight, and uncertain or non-approved signals never adjust probability. Per-signal, category, and total caps are applied in order. Pairwise adjustment uses the relative fighter effects and preserves `P(A) + P(B) = 1`, with final probabilities bounded to `0.01–0.99`.

Historical feature and prediction commands require an explicit timezone-aware `--as-of`. Queries exclude sources published or captured later, signals recorded or occurring later, and reviews completed later. Stored feature versions and adjustment explanations retain signal IDs and calculation inputs for replay.

Example explanation item:

```json
{"label":"short_notice_replacement","direction":"negative","source_type":"official_ufc","recency_weight":"1","requested_adjustment":"-0.012","applied_adjustment":"-0.012","review_status":"approved"}
```

Known limitations: manual/imported evidence only; no live collection, external LLM call, unrestricted fuzzy matching, emotional analysis, or calibration claim. Exact event-time matching is limited by the current date-only event schema. The LLM-ready schema validates future extracted JSON but never invokes an LLM or auto-approves solely from extraction confidence.

## Docker and Railway

Run the full local stack with `docker compose up --build`. The API waits for PostgreSQL, applies migrations, and starts on port 8000.

For Railway, create a PostgreSQL service, set all required environment variables, and deploy this repository. `railway.json` builds the Dockerfile, runs `alembic upgrade head` as the pre-deploy command, starts Uvicorn on Railway's `PORT`, and checks `/health`.

## Deploying to Render

The root [Render Blueprint](render.yaml) creates the `ufc-analysis-api` Docker web service and the managed `ufc-analysis-db` PostgreSQL database. Render supplies its standard `postgres://` connection string; application settings safely normalize it to SQLAlchemy's `postgresql+psycopg2://` driver URL.

1. Push the `main` branch to a GitHub repository.
2. In Render, choose **New → Blueprint** and connect/select that repository.
3. Confirm the detected `render.yaml` resources.
4. Provide the Blueprint's secret values:
   - `API_KEY`: a long random value required by protected administration routes.
   - `CORS_ORIGINS`: a JSON array or comma-separated list of allowed browser origins, such as `https://app.example.com`.
   - `ODDS_API_KEY`: required only when live odds ingestion is used.
5. Apply the Blueprint and deploy. Automatic deployments track `main`.
6. Render runs `alembic upgrade head` as the pre-deploy migration command. Confirm it succeeds in the deploy logs; if an operator must rerun it, open the service Shell and run `alembic upgrade head`.
7. Verify `https://YOUR-SERVICE.onrender.com/health` returns `{"status":"ok","database":"ok"}`.
8. Verify interactive API documentation at `https://YOUR-SERVICE.onrender.com/docs` and OpenAPI at `/openapi.json`.

The production container runs Python 3.12 as a non-root user, binds Uvicorn to `0.0.0.0:$PORT`, disables reload, honors forwarded proxy headers, logs to stdout/stderr, and checks the dynamically assigned port. `APP_ENV=production` validates that a non-local `DATABASE_URL` and `API_KEY` are configured before startup. Database health failures return HTTP 503 without exposing connection details.

Local production-image verification:

```bash
docker build -t ufc-analysis-engine:render .
docker compose up --build
```

## Model versioning and limitations

Increment `MODEL_VERSION` whenever formulas, coefficients, or normalization populations change. Historical rows retain their version so outputs remain auditable.

Current limitations: round-winner data and positional-advancement events are not present in the source schema, so round-win rate defaults to zero and control advancement defaults to a conservative factor. Ranked-opponent filtering is reserved until rankings are ingested. Confidence values must not be interpreted as prediction probabilities.
