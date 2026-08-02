"""
Signal Feed data-access service (REQ-4).

Same design decision as dashboard_service.py: these functions are the
internal equivalent of the BRD's REST endpoints (GET /api/v1/signals, etc.),
called directly by Streamlit instead of over HTTP.
"""

from datetime import date, datetime, time, timezone

from sqlalchemy import func

from app.db import get_session
from app.models import Article, ArticleEntity, Entity, SentimentResult, Signal

SORT_OPTIONS = ["Signal Strength", "Date", "Entity Name", "Article Count"]
STRENGTH_OPTIONS = ["Strong Bullish", "Bullish", "Neutral", "Bearish", "Strong Bearish"]
ENTITY_TYPE_OPTIONS = ["Company", "Index", "Sector", "Commodity"]


def get_all_signals(
    search: str = "",
    strengths: list[str] | None = None,
    entity_types: list[str] | None = None,
    window_hours: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    sort_by: str = "Signal Strength",
) -> list[dict]:
    """
    Stands in for: GET /api/v1/signals (with filtering/sorting applied
    server-side, per REQ-4's Search/Filter/Sort features).
    """
    with get_session() as session:
        query = (
            session.query(Entity.name, Entity.entity_type, Signal)
            .join(Signal, Signal.entity_id == Entity.entity_id)
        )

        if search:
            query = query.filter(Entity.name.ilike(f"%{search}%"))
        if strengths:
            query = query.filter(Signal.signal_strength.in_(strengths))
        if entity_types:
            query = query.filter(Entity.entity_type.in_(entity_types))
        if window_hours:
            query = query.filter(Signal.window_size_hours == window_hours)
        if date_from:
            query = query.filter(Signal.window_end >= datetime.combine(date_from, time.min))
        if date_to:
            query = query.filter(Signal.window_end <= datetime.combine(date_to, time.max))

        rows = query.all()

    results = [
        {
            "signal_id": sig.signal_id,
            "entity_id": sig.entity_id,
            "entity_name": name,
            "entity_type": etype,
            "signal_strength": sig.signal_strength,
            "aggregate_score": sig.aggregate_sentiment_score,
            "article_count": sig.article_count,
            "window_hours": sig.window_size_hours,
            "window_start": sig.window_start,
            "window_end": sig.window_end,
        }
        for name, etype, sig in rows
    ]

    if sort_by == "Signal Strength":
        results.sort(key=lambda r: abs(r["aggregate_score"]), reverse=True)
    elif sort_by == "Date":
        results.sort(key=lambda r: r["window_end"], reverse=True)
    elif sort_by == "Entity Name":
        results.sort(key=lambda r: r["entity_name"])
    elif sort_by == "Article Count":
        results.sort(key=lambda r: r["article_count"], reverse=True)

    return results


def get_signal_detail(signal_id: int) -> dict | None:
    """Fields for the Signal Detail View: entity, strength, score, sentiment breakdown."""
    with get_session() as session:
        row = (
            session.query(Entity.name, Entity.entity_id, Signal)
            .join(Signal, Signal.entity_id == Entity.entity_id)
            .filter(Signal.signal_id == signal_id)
            .first()
        )
        if row is None:
            return None
        name, entity_id, sig = row
        return {
            "entity_name": name,
            "entity_id": entity_id,
            "signal_strength": sig.signal_strength,
            "aggregate_score": sig.aggregate_sentiment_score,
            "positive_count": sig.positive_count,
            "negative_count": sig.negative_count,
            "neutral_count": sig.neutral_count,
            "window_start": sig.window_start,
            "window_end": sig.window_end,
        }


def get_contributing_articles(entity_id: int, window_start: datetime, window_end: datetime) -> list[dict]:
    """
    Stands in for: GET /api/v1/articles?signal_id=

    Articles that mention this entity within the signal's window, with
    their individual sentiment label and confidence — for the Contributing
    Articles table in the Signal Detail View.
    """
    with get_session() as session:
        rows = (
            session.query(Article.article_id, Article.headline,
                         SentimentResult.sentiment_label, SentimentResult.confidence_score)
            .join(ArticleEntity, ArticleEntity.article_id == Article.article_id)
            .join(SentimentResult, SentimentResult.article_id == Article.article_id)
            .filter(ArticleEntity.entity_id == entity_id)
            .filter(Article.published_at >= window_start)
            .filter(Article.published_at <= window_end)
            .order_by(Article.published_at.desc())
            .all()
        )
        return [
            {"article_id": aid, "headline": h, "sentiment_label": label, "confidence": conf}
            for aid, h, label, conf in rows
        ]
