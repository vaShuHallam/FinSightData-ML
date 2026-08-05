# FinSight AI

Real-time financial news sentiment analyser & market signal dashboard.
This repo currently covers **Phase 1: the database layer** (BRD REQ-1 — all ten tables).

## Project layout

```
finsight-ai/
├── app/
│   ├── __init__.py
│   ├── config.py      # env-driven settings (DATABASE_URL, SQL_ECHO)
│   ├── db.py          # engine, session factory, get_session(), init_db()
│   └── models.py      # all 10 SQLAlchemy models + relationships + enums
├── init_db.py         # create (or --reset) the schema
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

## Notes & next steps

- **Migrations:** `init_db.py` uses `create_all`, which is perfect for dev and a
  first build but won't alter existing tables. Once the schema settles, add
  **Alembic** so production schema changes are versioned.
- **Scores as Float:** BRD "Decimal (0.0–1.0)" fields are stored as `Float`
  (double precision) — see the note at the top of `models.py`.
- **Next phase:** ingestion + preprocessing (populating `articles`, setting
  `content_hash`, `source_credibility_score`, `recency_weight`).
```