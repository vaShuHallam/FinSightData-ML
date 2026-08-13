"""
Alert-generation pipeline entry point.

Now incorporates the lightweight relevance-learning layer
(app/alerts/relevance_learning.py): each entity's historical feedback
adjusts its effective alert threshold before checking whether the latest
signal clears it.
"""

import logging
from datetime import datetime, timezone

from app.alerts.relevance_learning import apply_adjustment, compute_adjustment
from app.db import get_session
from app.models import (
    Alert, Article, ArticleEntity, PipelineRun, PipelineRunType,
    PipelineStatus, Signal, UserFeedback, Watchlist,
)

logger = logging.getLogger(__name__)

_NON_ALERTABLE_STRENGTHS = {"Neutral"}


def run_alert_generation() -> dict:
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


def _get_relevance_adjusted_threshold(session, entity_id: int, base_threshold: float) -> tuple[float, dict]:
    """Returns (effective_threshold, debug_info) — debug_info is logged, not stored."""
    scores = [
        fb.relevance_score
        for fb in session.query(UserFeedback)
        .join(Alert, Alert.alert_id == UserFeedback.alert_id)
        .filter(Alert.entity_id == entity_id)
        .all()
    ]

    adjustment = compute_adjustment(scores, entity_id=entity_id)
    effective = apply_adjustment(base_threshold, adjustment.threshold_adjustment)

    debug_info = {
        "feedback_count": adjustment.feedback_count,
        "average_relevance": adjustment.average_relevance,
        "adjustment": adjustment.threshold_adjustment,
        "base_threshold": base_threshold,
        "effective_threshold": effective,
    }
    return effective, debug_info


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
                continue
            if latest_signal.signal_strength in _NON_ALERTABLE_STRENGTHS:
                continue

            effective_threshold, debug_info = _get_relevance_adjusted_threshold(
                session, entry.entity_id, entry.alert_threshold
            )
            if debug_info["feedback_count"] >= 2:
                logger.info("Entity %s: relevance-adjusted threshold %s -> %s (avg rating %s over %d ratings)",
                           entry.entity_id, debug_info["base_threshold"], round(effective_threshold, 3),
                           debug_info["average_relevance"], debug_info["feedback_count"])

            if abs(latest_signal.aggregate_sentiment_score) < effective_threshold:
                continue

            already_alerted = (
                session.query(Alert)
                .filter(Alert.signal_id == latest_signal.signal_id)
                .filter(Alert.entity_id == entry.entity_id)
                .first()
            )
            if already_alerted is not None:
                continue

            headline = _representative_headline(
                session, entry.entity_id, latest_signal.window_start, latest_signal.window_end
            )

            session.add(Alert(
                entity_id=entry.entity_id, signal_id=latest_signal.signal_id,
                alert_type=latest_signal.signal_strength, trigger_headline=headline,
                threshold_value=entry.alert_threshold,  # the user's OWN chosen threshold, for transparency
                triggered_value=latest_signal.aggregate_sentiment_score,
            ))
            created += 1

    return checked, created


def _representative_headline(session, entity_id: int, window_start, window_end) -> str | None:
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


def _finish_pipeline_run(run_id, status, articles_processed, error_detail):
    with get_session() as session:
        run = session.get(PipelineRun, run_id)
        run.status = status.value
        run.articles_processed = articles_processed
        run.errors_count = 1 if status == PipelineStatus.FAILED else 0
        run.error_detail = error_detail
        run.completed_at = datetime.now(timezone.utc)