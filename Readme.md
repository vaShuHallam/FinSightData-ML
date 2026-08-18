# FinSight AI

Real-time financial news sentiment analyser & market signal dashboard.
This repo currently covers **Phase 1 (database)**, **Phase 2 (ingestion)**,
**entity tagging**, and **Phase 3 (FinBERT sentiment)**.

## Development environment

This project was scaffolded inside a sandboxed chat environment with a
restricted network allowlist — fine for the database, ingestion, and entity
tagging phases, but it blocks the two things sentiment analysis needs:
HuggingFace Hub (`huggingface.co`, where FinBERT's weights live) and GitHub
release assets (where SpaCy's models live). Both were confirmed blocked with
direct requests, not assumed — see "Scope decisions" below.

**Development happens in PyCharm from here on** — a proper multi-file
project, not a notebook task, and your own machine has full internet access
so none of the above applies. Open this folder as a PyCharm project, create
a venv, and `pip install -r requirements.txt`.

Before trusting FinBERT in the real pipeline, run `check_finbert.py` once —
a standalone script (not part of the package) that loads the model and
classifies four test headlines, so you can confirm it works before wiring it
into `run_sentiment.py`.

## Project layout

```
finsight-ai/
├── app/
│   ├── __init__.py
│   ├── config.py            # env-driven settings (DATABASE_URL, SQL_ECHO, API keys)
│   ├── db.py                # engine, session factory, get_session(), init_db()
│   ├── models.py            # all 10 SQLAlchemy models + relationships + enums
│   ├── ingestion/
│   │   ├── base.py          # BaseFetcher interface + RawArticle shape
│   │   ├── newsapi_fetcher.py   # NewsAPI adapter (falls back to sample data)
│   │   ├── sample_data.py   # bundled sample response for offline dev/testing
│   │   ├── preprocess.py    # content hashing, credibility scoring, recency weight
│   │   └── pipeline.py      # fetch -> preprocess -> save -> pipeline_runs log
│   ├── entity_tagging/
│   │   ├── base.py          # BaseEntityTagger interface + EntityMention shape
│   │   ├── rule_based.py    # name/ticker string-matching tagger (see Scope decisions)
│   │   └── pipeline.py      # tags untagged articles -> article_entities
│   └── sentiment/
│       ├── base.py               # BaseSentimentAnalyzer interface + SentimentPrediction shape
│       ├── finbert_analyzer.py   # ProsusAI/finbert, batched, GPU-aware
│       └── pipeline.py           # analyzes unanalyzed articles -> sentiment_results
├── init_db.py         # create (or --reset) the schema
├── seed_entities.py         # populate the entities table (run once, before ingestion)
├── seed_model_versions.py   # populate model_versions with the v1 baseline config
├── run_ingestion.py         # CLI: run one ingestion cycle
├── run_entity_tagging.py    # CLI: run one entity-tagging cycle
├── run_sentiment.py         # CLI: run one sentiment-analysis cycle
├── check_finbert.py         # standalone sanity check (not part of the package) — run first
├── requirements.txt   # full stack, grouped by build phase
├── .env.example       # copy to .env and fill in
└── .gitignore
```

## Setup

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # then edit if needed
```

## Create the database

```bash
python init_db.py           # creates all tables
python init_db.py --reset   # drops everything and recreates (dev only)
```

By default this writes a local `finsight.db` SQLite file. You should see all ten
tables listed on success.

## SQLite (dev) → Postgres (prod)

The only thing that changes is `DATABASE_URL`. Set it in `.env` (or as a real
environment secret in deployment):

```bash
# Local development (default — no setup needed)
DATABASE_URL=sqlite:///finsight.db

# Production
DATABASE_URL=postgresql+psycopg2://user:password@host:5432/finsight
```

`app/db.py` reads this one string and configures the engine accordingly, so no
application code changes between environments.

## Using the models

```python
from app.db import get_session
from app.models import Entity, EntityType

with get_session() as session:
    session.add(Entity(name="Barclays PLC", ticker_symbol="BARC",
                        entity_type=EntityType.COMPANY.value, sector="Finance",
                        exchange="LSE"))
    # commit is automatic on clean exit; rollback on exception
```

The `str` enums in `models.py` (`SentimentLabel`, `EntityType`, `SignalStrength`,
etc.) are the source of truth for the allowed categorical values — use them in
application code rather than raw strings to avoid typos. Store `.value`.

## Running ingestion

Seed the entities table first (only needs to be run once — it's safe to
re-run, existing entities are skipped):

```bash
python seed_entities.py
```

Then run an ingestion cycle:

```bash
python run_ingestion.py                       # default query
python run_ingestion.py --query "NVIDIA"
```

Without a `NEWSAPI_KEY` set in `.env`, this automatically falls back to a
bundled sample response (`app/ingestion/sample_data.py`) so the pipeline can
be built and tested before a key is approved. Add the key to `.env` and it
switches to live calls with no code changes. Duplicate articles (matched by
`content_hash`) are skipped automatically, and every run is logged to
`pipeline_runs`.

Then tag articles with the entities they mention:

```bash
python run_entity_tagging.py
```

Only articles with no existing `article_entities` rows are processed, so
re-running after fetching new articles is safe — already-tagged ones are
skipped.

Then, in PyCharm, install the sentiment dependencies and verify FinBERT
works before trusting it in the pipeline:

```bash
pip install transformers torch
python check_finbert.py
```

You should see the Apple/Microsoft headlines classified "positive" and the
Tesla one "negative". Once that looks right:

```bash
python seed_model_versions.py   # once, registers the v1 baseline
python run_sentiment.py
```

First run downloads FinBERT's weights (~440MB, cached after that). Articles
with an existing `sentiment_results` row are skipped on subsequent runs.
Predictions below `SENTIMENT_CONFIDENCE_THRESHOLD` (default 0.6, set in
`.env`) are saved with `is_abstained=True` rather than trusted outright.

## Scope decisions

Decisions made during the build that depart from, or aren't fully specified
by, the BRD — kept here so the reasoning is documented for the report.

- **Reddit API access (deferred).** The BRD scopes Reddit as a third news
  source alongside NewsAPI and Alpha Vantage. Reddit introduced a
  "Responsible Builder Policy" in November 2025 requiring explicit
  pre-approval before any API access — including small, non-commercial,
  personal projects. The self-serve app creation page
  (`reddit.com/prefs/apps`) has not been fully updated for this: the
  "accept terms" step is missing, and submitting the form currently fails
  silently (the page just refreshes, no key is issued). Because there's no
  published timeline for manual approval, Reddit is being treated as an
  optional/stretch source rather than a blocker. NewsAPI and Alpha Vantage
  cover ingestion for now; the `BaseFetcher` interface in
  `app/ingestion/base.py` means a Reddit adapter can be added later as a
  single new file with no changes to the rest of the pipeline, if/when
  approval comes through.

- **Entity tagging: rule-based matcher instead of SpaCy, for now.** The BRD
  specifies SpaCy for named entity recognition. SpaCy's language models are
  distributed via GitHub release assets; a real download attempt in the
  build environment returned an HTTP 403 (the file lives behind
  `release-assets.githubusercontent.com`, outside that environment's
  network allowlist). Rather than ship SpaCy integration code that was
  never actually run, `app/entity_tagging/rule_based.py` implements a
  tested, working alternative: it matches article text against the names
  and ticker symbols already in the `entities` table (handling corporate
  suffixes like "Inc."/"PLC" so "Apple" matches "Apple Inc."). This fully
  populates `article_entities` and unblocks aggregation. `BaseEntityTagger`
  (`app/entity_tagging/base.py`) defines the same interface a real SpaCy
  tagger would implement, so swapping it in later — on a machine without
  this network restriction — is a single new file, no pipeline changes.
  **Known limitation to note in the report:** short tickers that are also
  common English words (e.g. a hypothetical ticker "ALL") can over-match,
  since there's no sentence-level context the way a trained NER model has.

- **FinBERT module: written and reasoned through, not executed in this
  sandbox.** `app/sentiment/finbert_analyzer.py` was built following the
  standard `transformers` batch-inference pattern, but couldn't be run here:
  a direct check confirmed `huggingface.co` (where FinBERT's weights are
  hosted) returns `x-deny-reason: host_not_allowed` from this environment's
  network proxy — the same class of restriction that blocked SpaCy above.
  Before wiring this into the main pipeline, run `check_finbert.py`
  (a standalone script, not part of the package) to confirm it loads and
  classifies correctly — takes about a minute in PyCharm. If it behaves
  unexpectedly, that's the file to debug against; the label mapping is read
  from the model's own config rather than hardcoded, which should make it
  robust, but hasn't been verified against a live model.

## Notes & next steps

- **Migrations:** `init_db.py` uses `create_all`, which is perfect for dev and a
  first build but won't alter existing tables. Once the schema settles, add
  **Alembic** so production schema changes are versioned.
- **Scores as Float:** BRD "Decimal (0.0–1.0)" fields are stored as `Float`
  (double precision) — see the note at the top of `models.py`.
- **Next phase:** signal aggregation (rolling up sentiment_results +
  article_entities into per-entity signals), then threshold-based alerts.
....