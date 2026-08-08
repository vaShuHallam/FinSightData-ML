# FinSightData-ML

FinSightData-ML is a machine learning-powered financial analytics platform for ingesting market news, processing financial data, tagging entities, generating sentiment and signals, and presenting decision-support insights through a Streamlit dashboard.

## Features

- Financial news ingestion with sample-data fallbacks for local development
- Entity tagging pipelines for mapping articles to tracked companies and instruments
- FinBERT-based sentiment analysis workflow for financial text
- Signal aggregation and alert generation scripts for downstream monitoring
- Streamlit dashboards for signal feeds, alerts, entity exploration, evaluation, watchlists, and settings
- SQLite-first local development with configurable PostgreSQL support

## Technology stack

- **Language:** Python
- **Storage and ORM:** SQLite, PostgreSQL, SQLAlchemy
- **Data processing:** pandas, numpy, openpyxl
- **Machine learning / NLP:** scikit-learn, transformers, torch, spaCy
- **Visualization and UI:** Streamlit, Plotly
- **External data access:** requests

## Local development setup (supported path)

Use Python 3.11 and the commands below as the canonical local workflow.

1. Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

   On Windows:

   ```powershell
   .venv\Scripts\activate
   ```

2. Install project + test dependencies:

   ```bash
   pip install -r requirements-dev.txt
   ```

3. Copy the example environment file and update it for your environment:

   ```bash
   cp .env.example .env
   ```

## Configuration

FinSightData-ML uses environment variables for runtime configuration. The most important settings are:

- `DATABASE_URL` - local SQLite or production PostgreSQL connection string
- `SQL_ECHO` - enable SQL debug logging
- `NEWSAPI_KEY` and `ALPHAVANTAGE_KEY` - live ingestion credentials
- `SENTIMENT_CONFIDENCE_THRESHOLD` - minimum sentiment confidence before abstaining
- `SIGNAL_WINDOW_HOURS`, `SIGNAL_STRONG_THRESHOLD`, `SIGNAL_MODERATE_THRESHOLD` - signal settings
- `DEFAULT_ALERT_THRESHOLD` - default alert cutoff

For local development, the default database is `sqlite:///finsight.db`.

## Project structure

```text
FinSightData-ML/
├── app/                          # Core packages, models, config, and pipelines
│   ├── alerts/                   # Alert generation logic
│   ├── entity_tagging/           # Rule-based and spaCy tagging components
│   ├── ingestion/                # News ingestion and preprocessing pipelines
│   ├── sentiment/                # Sentiment analyzers and sentiment pipeline
│   ├── services/                 # Dashboard/query service layer
│   ├── signals/                  # Signal aggregation logic
│   ├── config.py                 # Environment-driven settings
│   ├── db.py                     # Database engine and session helpers
│   └── models.py                 # SQLAlchemy models and enums
├── pages/                        # Streamlit multi-page dashboard views
├── app.py                        # Streamlit entrypoint
├── init_db.py                    # Database initialization/reset script
├── run_ingestion.py              # Ingestion CLI
├── run_entity_tagging.py         # Entity tagging CLI
├── run_sentiment.py              # Sentiment analysis CLI
├── run_signals.py                # Signal aggregation CLI
├── run_alerts.py                 # Alert generation CLI
├── seed_*.py                     # Seed scripts for entities, models, and watchlists
├── export_annotation_batch.py    # Evaluation data export utility
├── compute_gold_standard_metrics.py
├── check_finbert.py              # FinBERT verification utility
├── requirements.txt              # Python dependency specification
├── .env.example                  # Example configuration
└── .gitignore                    # Local file and artifact exclusions
```

## Usage examples

Initialize/reset the database:

```bash
python init_db.py --reset
```

Seed baseline data:

```bash
python seed_entities.py
python seed_model_versions.py
python seed_watchlist.py
```

Run the data pipeline stages (offline-safe defaults):

```bash
python run_ingestion.py
python run_entity_tagging.py
python run_sentiment.py --backend auto
python run_signals.py
python run_alerts.py
```

Launch the dashboard:

```bash
streamlit run app.py
```

Run tests:

```bash
pytest -q
```

## Model and data prerequisites

- `run_entity_tagging.py --tagger hybrid` attempts to load spaCy model `en_core_web_trf`; if unavailable, it falls back to rule-based tagging.
- `run_sentiment.py --backend finbert` requires internet/model cache access for `ProsusAI/finbert`.
- `run_sentiment.py --backend auto` falls back to a built-in lexicon analyzer when FinBERT cannot be loaded, allowing end-to-end local validation without external model downloads.
- Live ingestion requires `NEWSAPI_KEY` and/or `ALPHAVANTAGE_KEY`; otherwise bundled sample responses are used.

## Development setup

- Use `.env.example` as the starting point for local configuration.
- Keep generated databases, model artifacts, exports, and secrets out of version control.
- Validate changes with `pytest -q` and the documented CLI pipeline flow before opening a PR.

## Contributing

1. Fork or branch from the main development line
2. Make focused, reviewable changes
3. Validate the affected scripts or dashboard flows locally
4. Open a pull request with a clear description of the change and its impact

## License

This repository does not currently include a license file. Until a license is added by the repository owner, treat the code and assets as proprietary and only use them within the intended collaboration workflow.
