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

# --- Sentiment analysis (FinBERT) ---
SENTIMENT_CONFIDENCE_THRESHOLD: float = float(os.getenv("SENTIMENT_CONFIDENCE_THRESHOLD", "0.6"))

# --- Signal aggregation ---
# How many hours back to look when aggregating sentiment into a signal.
SIGNAL_WINDOW_HOURS: int = int(os.getenv("SIGNAL_WINDOW_HOURS", "6"))

# Aggregate score thresholds (-1.0 to 1.0) that classify signal_strength.
# |score| >= STRONG    -> "Strong Bullish"/"Strong Bearish"
# |score| >= MODERATE  -> "Bullish"/"Bearish"
# otherwise            -> "Neutral"
SIGNAL_STRONG_THRESHOLD: float = float(os.getenv("SIGNAL_STRONG_THRESHOLD", "0.6"))
SIGNAL_MODERATE_THRESHOLD: float = float(os.getenv("SIGNAL_MODERATE_THRESHOLD", "0.2"))