"""
Preprocessing helpers applied to every article before it's considered "ready"
(is_processed=True): dedup hashing, source credibility, and recency weight.

These are intentionally simple, explainable functions — the BRD's research
contribution is the pipeline design and evaluation, not exotic scoring
heuristics here. Tune the constants below as you see how real data behaves.
"""

import hashlib
import math
from datetime import datetime, timezone
from typing import Optional

# Static credibility scores by source name (0.0-1.0). Sources not listed fall
# back to DEFAULT_CREDIBILITY. Tune this table as you onboard more sources.
SOURCE_CREDIBILITY: dict[str, float] = {
    "Reuters": 0.95,
    "Bloomberg": 0.95,
    "Financial Times": 0.93,
    "The Wall Street Journal": 0.93,
    "CNBC": 0.85,
    "BBC News": 0.88,
    "Associated Press": 0.90,
}
DEFAULT_CREDIBILITY = 0.60  # unknown/unlisted sources

# Recency weight uses exponential decay: weight = 0.5 ** (age_hours / HALF_LIFE_HOURS)
# An article loses half its recency weight every HALF_LIFE_HOURS. 6h matches the
# BRD's default watchlist window_size_hours, so a fresh article dominates its window.
RECENCY_HALF_LIFE_HOURS = 6.0


def compute_content_hash(headline: str, source_name: Optional[str]) -> str:
    """
    MD5 of headline + source name, used to detect duplicate articles (e.g. the
    same story picked up under a slightly different URL, or re-fetched on the
    next pipeline cycle). Not cryptographic — just a cheap, stable dedup key.
    """
    basis = f"{headline.strip().lower()}|{(source_name or '').strip().lower()}"
    return hashlib.md5(basis.encode("utf-8")).hexdigest()


def score_credibility(source_name: Optional[str]) -> float:
    """Look up a static credibility score for a source, with a safe default."""
    if not source_name:
        return DEFAULT_CREDIBILITY
    return SOURCE_CREDIBILITY.get(source_name, DEFAULT_CREDIBILITY)


def compute_recency_weight(
    published_at: Optional[datetime],
    now: Optional[datetime] = None,
    half_life_hours: float = RECENCY_HALF_LIFE_HOURS,
) -> float:
    """
    Exponential decay weight in (0.0, 1.0] based on article age.

    A published_at of None (couldn't be parsed) gets a conservative mid-range
    weight rather than 0 or 1, so it neither dominates nor is silently dropped
    from aggregation.
    """
    if published_at is None:
        return 0.5

    now = now or datetime.now(timezone.utc)
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)

    age_hours = max((now - published_at).total_seconds() / 3600.0, 0.0)
    weight = math.pow(0.5, age_hours / half_life_hours)
    return round(weight, 4)
