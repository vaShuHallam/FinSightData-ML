"""
Entity Explorer data-access service (REQ-6).

Same design decision as the other services: internal equivalents of the
BRD's REST endpoints, called directly by Streamlit.
"""

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from app.db import get_session
from app.models import Article, ArticleEntity, Entity, SentimentResult, Signal, Watchlist

TIME_RANGE_TO_HOURS = {"Last 24 hours": 24, "Last 7 days": 24 * 7, "Last 30 days": 24 * 30}
DEFAULT_ALERT_THRESHOLD = 0.60
DEFAULT_WINDOW_HOURS = 6


def _as_utc(dt: datetime) -> datetime:
    """SQLite drops tzinfo on round-trip; everything here is written in UTC."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def get_entity_metadata(entity_id: int, session_id: str) -> dict | None:
    """Entity Metadata Card: name, type, sector, ticker, and whether it's on this user's watchlist."""
    with get_session() as session:
        entity = session.get(Entity, entity_id)
        if entity is None:
            return None

        is_on_watchlist = (
            session.query(Watchlist)
            .filter(Watchlist.entity_id == entity_id, Watchlist.session_id == session_id)
            .first()
            is not None
        )

        return {
            "name": entity.name,
            "entity_type": entity.entity_type,
            "sector": entity.sector,
            "ticker_symbol": entity.ticker_symbol,
            "is_active": entity.is_active,
            "is_on_watchlist": is_on_watchlist,
        }


def get_sentiment_history(entity_id: int, hours: int, window_size_hours: int | None = None) -> list[dict]:
    """Sentiment History Chart data: aggregate_sentiment_score per signal, over `hours`."""
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    with get_session() as session:
        query = (
            session.query(Signal.window_end, Signal.aggregate_sentiment_score)
            .filter(Signal.entity_id == entity_id)
            .filter(Signal.window_end >= since)
        )
        if window_size_hours:
            query = query.filter(Signal.window_size_hours == window_size_hours)

        rows = query.order_by(Signal.window_end).all()
        return [{"timestamp": w, "score": s} for w, s in rows]


def get_signal_distribution(entity_id: int, hours: int) -> list[dict]:
    """
    Signal Distribution Chart data: count of positive/negative/neutral
    ARTICLES per day (derived from article-level sentiment, not summed
    across overlapping signal windows, which would double-count).
    """
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    with get_session() as session:
        rows = (
            session.query(Article.published_at, SentimentResult.sentiment_label)
            .join(ArticleEntity, ArticleEntity.article_id == Article.article_id)
            .join(SentimentResult, SentimentResult.article_id == Article.article_id)
            .filter(ArticleEntity.entity_id == entity_id)
            .filter(Article.published_at >= since)
            .all()
        )

    daily = defaultdict(lambda: {"positive": 0, "negative": 0, "neutral": 0})
    for published_at, label in rows:
        if published_at is None or label is None:
            continue
        day = _as_utc(published_at).date()
        daily[day][label] += 1

    return [
        {"date": day, "positive": counts["positive"], "negative": counts["negative"], "neutral": counts["neutral"]}
        for day, counts in sorted(daily.items())
    ]


def get_recent_articles(entity_id: int, limit: int = 20) -> list[dict]:
    """Recent Articles Table: most recent articles mentioning this entity."""
    with get_session() as session:
        rows = (
            session.query(Article.headline, Article.published_at,
                         SentimentResult.sentiment_label, SentimentResult.confidence_score)
            .join(ArticleEntity, ArticleEntity.article_id == Article.article_id)
            .outerjoin(SentimentResult, SentimentResult.article_id == Article.article_id)
            .filter(ArticleEntity.entity_id == entity_id)
            .order_by(Article.published_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {"headline": h, "published_at": p, "sentiment_label": label, "confidence": conf}
            for h, p, label, conf in rows
        ]


def get_signal_history(entity_id: int) -> list[dict]:
    """Signal History Table: every signal ever generated for this entity."""
    with get_session() as session:
        signals = (
            session.query(Signal)
            .filter(Signal.entity_id == entity_id)
            .order_by(Signal.window_end.desc())
            .all()
        )
        return [
            {
                "signal_strength": s.signal_strength, "aggregate_score": s.aggregate_sentiment_score,
                "article_count": s.article_count, "window_hours": s.window_size_hours,
                "window_start": s.window_start, "window_end": s.window_end,
            }
            for s in signals
        ]


def add_to_watchlist(entity_id: int, session_id: str) -> tuple[bool, str]:
    """
    Add an entity to the user's watchlist with sensible BRD defaults
    (alert_threshold=0.60, window_size_hours=6). Returns (success, message)
    using the exact status-alert wording from the BRD's Watchlist page spec.
    """
    with get_session() as session:
        existing = (
            session.query(Watchlist)
            .filter(Watchlist.entity_id == entity_id, Watchlist.session_id == session_id)
            .first()
        )
        if existing is not None:
            return False, "Entity already on watchlist."

        session.add(
            Watchlist(
                session_id=session_id, entity_id=entity_id,
                alert_threshold=DEFAULT_ALERT_THRESHOLD, window_size_hours=DEFAULT_WINDOW_HOURS,
            )
        )

    return True, "Entity added to your watchlist."
