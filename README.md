# FinSight AI

Real-time financial news sentiment analyser & market signal dashboard.

The system ingests live financial news, classifies sentiment per article using
FinBERT, tags which company/sector each article concerns, aggregates scores
into per-entity signals, and raises threshold-based alerts — all surfaced
through an 8-page Streamlit dashboard


## Project layout

```
finsight-ai/
├── app/
│   ├── config.py            # env-driven settings (DATABASE_URL, thresholds)
│   ├── db.py                 # engine, session factory, get_session(), init_db()
│   ├── models.py              # all 10 SQLAlchemy models + relationships + enums
│   ├── ingestion/             # NewsAPI / Alpha Vantage fetchers, dedup pipeline
│   ├── sentiment/             # FinBERT analyzer
│   ├── entity_tagging/        # rule-based + spaCy hybrid tagger
│   ├── signals/                # weighted signal aggregation
│   ├── alerts/                 # threshold-based alert generation
│   └── services/                # data-access layer — every dashboard page reads
│                                  # exclusively from here, never queries the DB directly
├── pages/                      # 7 additional Streamlit pages (Signal Feed, Alert
│                                  # Centre, Entity Explorer, Article Inspector,
│                                  # Evaluation Dashboard, Watchlist, Settings)
├── dashboard.py                 # main Dashboard page — run with `streamlit run dashboard.py`
│                                  # (renamed from app.py)
├── run_ingestion.py              # pipeline stage 1: fetch news
├── run_sentiment.py               # pipeline stage 2: FinBERT scoring
├── run_entity_tagging.py           # pipeline stage 3: tag entities
├── run_signals.py                    # pipeline stage 4: aggregate signals
├── run_alerts.py                      # pipeline stage 5: generate alerts
├── init_db.py                          # create (or --reset) the schema
├── seed_entities.py / seed_model_versions.py / seed_watchlist.py
├── compute_gold_standard_metrics.py     # evaluation script (v1/v2 metrics)
├── requirements.txt
├── .env.example
└── .gitignore
```

## Setup

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # then fill in your NewsAPI / Alpha Vantage keys
```

## Running the full pipeline

```bash
python init_db.py                    # 1. create tables
python seed_entities.py              # 2. seed tracked companies/sectors
python seed_model_versions.py

python run_ingestion.py              # 3. fetch live articles
python run_sentiment.py              # 4. score sentiment (FinBERT)
python run_entity_tagging.py         # 5. tag entities
python run_signals.py                # 6. aggregate signals
python run_alerts.py                 # 7. generate alerts

streamlit run dashboard.py            # 8. launch the dashboard
```

No manual model download is required — `run_sentiment.py` downloads and caches
FinBERT (`ProsusAI/finbert`, ~440MB) from HuggingFace on first run only; every
prediction after that runs locally with no further network dependency.

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

## Evaluation

```bash
python compute_gold_standard_metrics.py --version-label v1
```

Reads annotator label files, computes Cohen's kappa on the gold standard,
scores FinBERT's predictions (macro F1, per-class F1, entity precision/recall,
abstention rate), and writes `evaluation_results_v1.json` — read by the
Evaluation Dashboard page. Re-run with `--version-label v2` after implementing
targeted improvements to produce a v1-vs-v2 comparison.

## Notes & next steps

- **Migrations:** `init_db.py` uses `create_all`, which is perfect for dev and a
  first build but won't alter existing tables. Once the schema settles, add
  **Alembic** so production schema changes are versioned.
- **Scores as Float:** BRD "Decimal (0.0–1.0)" fields are stored as `Float`
  (double precision) — see the note at the top of `models.py`.
- **`.env` is not tracked in git** — each team member keeps their own local
  copy (from `.env.example`) with their own API keys. Do not commit `.env`.
- **Known limitation:** the current rule-based entity tagger favours precision
  over recall (~0.98 vs ~0.20) since spaCy's NER model could not be downloaded
  in the original build environment (blocked network policy). A hybrid
  tagger combining both already exists in `app/entity_tagging/`; switching to
  it and re-running evaluation as v2 is the planned next iteration.
