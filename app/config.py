import json
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///finsight.db")
SQL_ECHO: bool = os.getenv("SQL_ECHO", "0") in ("1", "true", "True")
IS_SQLITE: bool = DATABASE_URL.startswith("sqlite")

NEWSAPI_KEY: str = os.getenv("NEWSAPI_KEY", "")
ALPHAVANTAGE_KEY: str = os.getenv("ALPHAVANTAGE_KEY", "")
REDDIT_CLIENT_ID: str = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET: str = os.getenv("REDDIT_CLIENT_SECRET", "")
REDDIT_USER_AGENT: str = os.getenv("REDDIT_USER_AGENT", "finsight-ai/0.1")

# --- Access control (NFR 4.2 REQ-5) ---
# Settings page is restricted to project team members. A shared team
# password is the pragmatic choice here — the BRD's ten-table schema has
# no user-accounts table, and the team is small enough that per-user login
# would be over-engineering. Stored as an environment secret, same pattern
# as the API keys below. Deliberately no insecure default — if unset, the
# Settings page shows a clear warning rather than silently blocking
# everyone OR silently allowing a blank password to match a blank input.
SETTINGS_PASSWORD: str = os.getenv("SETTINGS_PASSWORD", "")

# --- Sentiment analysis (FinBERT) ---
SENTIMENT_CONFIDENCE_THRESHOLD: float = float(os.getenv("SENTIMENT_CONFIDENCE_THRESHOLD", "0.6"))

# --- Signal aggregation ---
SIGNAL_WINDOW_HOURS: int = int(os.getenv("SIGNAL_WINDOW_HOURS", "6"))
SIGNAL_STRONG_THRESHOLD: float = float(os.getenv("SIGNAL_STRONG_THRESHOLD", "0.6"))
SIGNAL_MODERATE_THRESHOLD: float = float(os.getenv("SIGNAL_MODERATE_THRESHOLD", "0.2"))

# --- Alerts ---
DEFAULT_ALERT_THRESHOLD: float = float(os.getenv("DEFAULT_ALERT_THRESHOLD", "0.60"))

# --- Settings overrides (Settings page / REQ-9) ---
# The BRD's ten-table schema has no dedicated settings table, so
# runtime-tunable values (confidence threshold, aggregation window, default
# alert threshold, per-source credibility overrides) are persisted here
# instead — a lightweight JSON file the Settings page reads and writes.
# IMPORTANT: because Python only executes this module once per process,
# changes saved here take effect the NEXT time a script/the app starts, not
# instantly within an already-running process. The Settings page states
# this explicitly rather than implying a live, instant update.
SETTINGS_FILE = "app_settings.json"
SOURCE_CREDIBILITY_OVERRIDES: dict = {}

if os.path.exists(SETTINGS_FILE):
    with open(SETTINGS_FILE) as f:
        _overrides = json.load(f)
    SENTIMENT_CONFIDENCE_THRESHOLD = _overrides.get("confidence_threshold", SENTIMENT_CONFIDENCE_THRESHOLD)
    SIGNAL_WINDOW_HOURS = _overrides.get("aggregation_window_hours", SIGNAL_WINDOW_HOURS)
    DEFAULT_ALERT_THRESHOLD = _overrides.get("default_alert_threshold", DEFAULT_ALERT_THRESHOLD)
    SOURCE_CREDIBILITY_OVERRIDES = _overrides.get("source_credibility_overrides", {})