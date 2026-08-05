import hashlib
import math
from datetime import datetime, timezone
from typing import Optional

SOURCE_CREDIBILITY: dict[str, float] = {
    "Reuters": 0.95, "Bloomberg": 0.95, "Financial Times": 0.93,
    "The Wall Street Journal": 0.93, "CNBC": 0.85, "BBC News": 0.88,
    "Associated Press": 0.90, "MarketWatch": 0.82,
}
DEFAULT_CREDIBILITY = 0.60
RECENCY_HALF_LIFE_HOURS = 6.0


def compute_content_hash(headline: str, source_name: Optional[str]) -> str:
    basis = f"{headline.strip().lower()}|{(source_name or '').strip().lower()}"
    return hashlib.md5(basis.encode("utf-8")).hexdigest()


def score_credibility(source_name: Optional[str]) -> float:
    from app import config
    if not source_name:
        return DEFAULT_CREDIBILITY
    if source_name in config.SOURCE_CREDIBILITY_OVERRIDES:
        return config.SOURCE_CREDIBILITY_OVERRIDES[source_name]
    return SOURCE_CREDIBILITY.get(source_name, DEFAULT_CREDIBILITY)


def compute_recency_weight(published_at, now=None, half_life_hours=RECENCY_HALF_LIFE_HOURS) -> float:
    if published_at is None:
        return 0.5
    now = now or datetime.now(timezone.utc)
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    age_hours = max((now - published_at).total_seconds() / 3600.0, 0.0)
    weight = math.pow(0.5, age_hours / half_life_hours)
    return round(weight, 4)