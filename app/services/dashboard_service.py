

from datetime import datetime, timedelta, timezone

from sqlalchemy import func

from app.db import get_session
from app.models import Alert, Article, Entity, PipelineRun, Signal, Watchlist

# Window-selector labels from the BRD  mapped to hours, since the UI shows human labels but the DB filters on hours.
WINDOW_LABEL_TO_HOURS = {"6h": 6, "12h": 12, "24h": 24, "7 days": 24 * 7}


def get_signal_summary(hours: int = 24) -> dict:
    """
    Returns counts for the BRD's Signal Summary Cards: total signals,
    bullish/bearish/neutral breakdown, and articles processed — all within
    the trailing `hours` window.
    """
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    with get_session() as session:
        signals = session.query(Signal).filter(Signal.window_end >= since).all()

        bullish = sum(1 for s in signals if "Bullish" in s.signal_strength)
        bearish = sum(1 for s in signals if "Bearish" in s.signal_strength)
        neutral = sum(1 for s in signals if s.signal_strength == "Neutral")

        articles_processed = (
            session.query(func.count(Article.article_id))
            .filter(Article.fetched_at >= since)
            .scalar()
        ) or 0

        return {
            "total_signals": len(signals),
            "bullish_signals": bullish,
            "bearish_signals": bearish,
            "neutral_signals": neutral,
            "articles_processed": articles_processed,
        }


def get_sentiment_timeline(entity_ids: list[int] | None = None, hours: int = 24) -> list[dict]:
    """
    Returns every signal in the trailing `hours` window (optionally filtered
    to specific entities), shaped for a line chart: one row per
    entity/timestamp with its aggregate_sentiment_score.
    """
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    with get_session() as session:
        query = (
            session.query(Entity.name, Signal.window_end, Signal.aggregate_sentiment_score)
            .join(Signal, Signal.entity_id == Entity.entity_id)
            .filter(Signal.window_end >= since)
        )
        if entity_ids:
            query = query.filter(Entity.entity_id.in_(entity_ids))

        rows = query.order_by(Signal.window_end).all()
        return [
            {"entity": name, "timestamp": window_end, "score": score}
            for name, window_end, score in rows
        ]


def get_top_signals(limit: int = 20) -> list[dict]:
    """
    Returns the most recent signals, ranked by |aggregate_sentiment_score|
    """
    with get_session() as session:
        rows = (
            session.query(Entity.name, Signal)
            .join(Signal, Signal.entity_id == Entity.entity_id)
            .order_by(func.abs(Signal.aggregate_sentiment_score).desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "entity": name,
                "signal_strength": sig.signal_strength,
                "article_count": sig.article_count,
                "aggregate_score": sig.aggregate_sentiment_score,
                "window_end": sig.window_end,
            }
            for name, sig in rows
        ]


def get_watchlist_signals(session_id: str) -> list[dict]:
    """
    Returns each watchlisted entity's most recent signal, for the sidebar
    Watchlist Panel.
    """
    with get_session() as session:
        entries = session.query(Watchlist).filter(
            Watchlist.session_id == session_id, Watchlist.is_active.is_(True)
        ).all()

        results = []
        for entry in entries:
            entity = session.get(Entity, entry.entity_id)
            latest = (
                session.query(Signal)
                .filter(Signal.entity_id == entry.entity_id)
                .order_by(Signal.window_end.desc())
                .first()
            )
            results.append(
                {
                    "entity": entity.name if entity else "Unknown",
                    "alert_threshold": entry.alert_threshold,
                    "signal_strength": latest.signal_strength if latest else None,
                    "aggregate_score": latest.aggregate_sentiment_score if latest else None,
                }
            )
        return results


def get_unacknowledged_alert_count() -> int:
    """ To get  "unacknowledged alerts" warning banner"""
    with get_session() as session:
        return (
            session.query(func.count(Alert.alert_id))
            .filter(Alert.is_acknowledged.is_(False))
            .scalar()
        ) or 0


def get_pipeline_status() -> dict | None:
    """
    Returns the most recent pipeline run of any type, for the Pipeline
    Status Indicator. None if no pipeline has ever run.
    """
    with get_session() as session:
        run = session.query(PipelineRun).order_by(PipelineRun.run_id.desc()).first()
        if run is None:
            return None
        return {
            "run_type": run.run_type,
            "status": run.status,
            "completed_at": run.completed_at,
            "articles_processed": run.articles_processed,
        }


def get_active_entities() -> list[dict]:
    """used to populate the Entity Filter dropdown."""
    with get_session() as session:
        rows = (
            session.query(Entity.entity_id, Entity.name)
            .filter(Entity.is_active.is_(True))
            .order_by(Entity.name)
            .all()
        )
        return [{"entity_id": eid, "name": name} for eid, name in rows]