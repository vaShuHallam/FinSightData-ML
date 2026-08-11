"""
Alert-generation pipeline entry point.

For every active watchlist entry, looks at that entity's most recent signal
and fires an alert if it crosses the user's chosen threshold.

Design notes:
- signal_strength gets computed at aggregation time off the global
  SIGNAL_STRONG_THRESHOLD/MODERATE thresholds, and it's deliberately built
  to share the same four non-neutral values as AlertType ("Strong Bullish",
  "Bullish", "Bearish", "Strong Bearish") — alert_type is just a straight
  copy of whatever strength label the signal already has, no separate
  mapping needed. Neutral signals never alert, no matter what threshold
  the user picked.
- The user's per-watchlist alert_threshold is a separate, personal gate:
  even if a signal is "Bullish" globally, it only becomes an alert for a
  specific user if abs(aggregate_sentiment_score) also clears their chosen
  threshold. Two different users watching the same entity can have
  different alert thresholds and get different alert behavior from the
  same underlying signal.
- It's idempotent per signal — won't fire a second alert for a signal
  that's already got one, so re-running the job when nothing new has
  come in is just a no-op.
"""

import logging
from datetime import datetime, timezone

from app.db import get_session
from app.models import (
    Alert, Article, ArticleEntity, PipelineRun, PipelineRunType,
    PipelineStatus, Signal, Watchlist,
)

logger = logging.getLogger(__name__)

# signal_strength values that should never produce an alert.
_NON_ALERTABLE_STRENGTHS = {"Neutral"}


def run_alert_generation() -> dict:
    """
    Check every active watchlist entry against its entity's latest signal.

    Returns a summary dict: {watchlist_checked, alerts_created}.
    """
    run_id = _start_pipeline_run()
    checked = created = 0
    error_detail = None

    try:
        checked, created = _check_all_watchlist_entries()
        status = PipelineStatus.COMPLETED
    except Exception as exc:
        logger.exception("Alert generation run failed")
        status = PipelineStatus.FAILED
        error_detail = str(exc)

    _finish_pipeline_run(run_id, status, articles_processed=created, error_detail=error_detail)

    summary = {"watchlist_checked": checked, "alerts_created": created, "status": status.value}
    logger.info("Alert generation summary: %s", summary)
    return summary


def _check_all_watchlist_entries() -> tuple[int, int]:
    created = 0

    with get_session() as session:
        watchlist_entries = session.query(Watchlist).filter(Watchlist.is_active.is_(True)).all()
        checked = len(watchlist_entries)

        for entry in watchlist_entries:
            latest_signal = (
                session.query(Signal)
                .filter(Signal.entity_id == entry.entity_id)
                .order_by(Signal.window_end.desc())
                .first()
            )
            if latest_signal is None:
                continue  # no signal computed for this entity yet

            if latest_signal.signal_strength in _NON_ALERTABLE_STRENGTHS:
                continue

            if abs(latest_signal.aggregate_sentiment_score) < entry.alert_threshold:
                continue  # doesn't clear this user's personal threshold

            already_alerted = (
                session.query(Alert)
                .filter(Alert.signal_id == latest_signal.signal_id)
                .filter(Alert.entity_id == entry.entity_id)
                .first()
            )
            if already_alerted is not None:
                continue  # already have an alert for this exact signal

            headline = _representative_headline(
                session, entry.entity_id, latest_signal.window_start, latest_signal.window_end
            )

            session.add(
                Alert(
                    entity_id=entry.entity_id,
                    signal_id=latest_signal.signal_id,
                    alert_type=latest_signal.signal_strength,
                    trigger_headline=headline,
                    threshold_value=entry.alert_threshold,
                    triggered_value=latest_signal.aggregate_sentiment_score,
                )
            )
            created += 1

    return checked, created


def _representative_headline(session, entity_id: int, window_start, window_end) -> str | None:
    """Most recent article headline mentioning this entity within the signal's window."""
    row = (
        session.query(Article.headline)
        .join(ArticleEntity, ArticleEntity.article_id == Article.article_id)
        .filter(ArticleEntity.entity_id == entity_id)
        .filter(Article.published_at >= window_start)
        .filter(Article.published_at <= window_end)
        .order_by(Article.published_at.desc())
        .first()
    )
    return row[0] if row else None


def _start_pipeline_run() -> int:
    with get_session() as session:
        run = PipelineRun(run_type=PipelineRunType.ALERT.value, status=PipelineStatus.RUNNING.value)
        session.add(run)
        session.flush()
        return run.run_id


def _finish_pipeline_run(
    run_id: int, status: PipelineStatus, articles_processed: int, error_detail: str | None
) -> None:
    with get_session() as session:
        run = session.get(PipelineRun, run_id)
        run.status = status.value
        run.articles_processed = articles_processed
        run.errors_count = 1 if status == PipelineStatus.FAILED else 0
        run.error_detail = error_detail
        run.completed_at = datetime.now(timezone.utc)