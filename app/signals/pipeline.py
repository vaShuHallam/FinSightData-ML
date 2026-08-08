"""
Signal-aggregation pipeline entry point.

For every entity mentioned by at least one article in the trailing window,
computes one Signal row via app/signals/aggregator.py and saves it.

Design notes:
- Prefers entity-specific sentiment rows when available
  (SentimentResult.entity_id == ArticleEntity.entity_id) and falls back to
  article-level rows (entity_id is null) for backward compatibility.
- Unlike ingestion/tagging, this does NOT check "already processed" — signals
  are an intentional time series. Every run produces a fresh snapshot for the
  current trailing window, which is what a "signal over time" chart on the
  dashboard needs. Running this repeatedly is expected, not a bug.
- Window filtering uses COALESCE(published_at, fetched_at) so articles with
  an unparsed publish date still count, using when they were fetched instead.
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import aliased

from app import config
from app.db import get_session
from app.models import (
    Article, ArticleEntity, PipelineRun, PipelineRunType,
    PipelineStatus, SentimentResult, Signal,
)
from app.signals.aggregator import ArticleContribution, aggregate

logger = logging.getLogger(__name__)


def run_signal_aggregation(window_hours: int | None = None) -> dict:
    """
    Aggregate sentiment into one Signal row per entity with recent mentions.

    Returns a summary dict: {entities_checked, signals_created}.
    """
    window_hours = window_hours or config.SIGNAL_WINDOW_HOURS
    run_id = _start_pipeline_run()
    checked = created = 0
    error_detail = None

    try:
        checked, created = _aggregate_all_entities(window_hours)
        status = PipelineStatus.COMPLETED
    except Exception as exc:
        logger.exception("Signal aggregation run failed")
        status = PipelineStatus.FAILED
        error_detail = str(exc)

    _finish_pipeline_run(run_id, status, articles_processed=created, error_detail=error_detail)

    summary = {"entities_checked": checked, "signals_created": created, "status": status.value}
    logger.info("Signal aggregation summary: %s", summary)
    return summary


def _aggregate_all_entities(window_hours: int) -> tuple[int, int]:
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(hours=window_hours)

    with get_session() as session:
        effective_time = func.coalesce(Article.fetched_at, Article.published_at)

        entity_sentiment = aliased(SentimentResult)
        article_sentiment = aliased(SentimentResult)

        rows = (
            session.query(
                ArticleEntity.entity_id,
                ArticleEntity.mention_count,
                func.coalesce(entity_sentiment.sentiment_label, article_sentiment.sentiment_label),
                func.coalesce(entity_sentiment.positive_score, article_sentiment.positive_score),
                func.coalesce(entity_sentiment.negative_score, article_sentiment.negative_score),
                Article.recency_weight,
                Article.source_credibility_score,
            )
            .join(Article, Article.article_id == ArticleEntity.article_id)
            .outerjoin(
                entity_sentiment,
                and_(
                    entity_sentiment.article_id == Article.article_id,
                    entity_sentiment.entity_id == ArticleEntity.entity_id,
                ),
            )
            .outerjoin(
                article_sentiment,
                and_(
                    article_sentiment.article_id == Article.article_id,
                    article_sentiment.entity_id.is_(None),
                ),
            )
            .filter(or_(entity_sentiment.result_id.isnot(None), article_sentiment.result_id.isnot(None)))
            .filter(effective_time >= window_start)
            .all()
        )

        by_entity: dict[int, list[ArticleContribution]] = defaultdict(list)
        for entity_id, mention_count, label, pos, neg, recency, credibility in rows:
            by_entity[entity_id].append(
                ArticleContribution(
                    sentiment_label=label,
                    positive_score=pos,
                    negative_score=neg,
                    recency_weight=recency if recency is not None else 0.5,
                    source_credibility_score=credibility if credibility is not None else 0.6,
                    mention_count=mention_count,
                )
            )

        created = 0
        for entity_id, contributions in by_entity.items():
            result = aggregate(
                contributions,
                strong_threshold=config.SIGNAL_STRONG_THRESHOLD,
                moderate_threshold=config.SIGNAL_MODERATE_THRESHOLD,
            )
            session.add(
                Signal(
                    entity_id=entity_id,
                    window_start=window_start,
                    window_end=now,
                    window_size_hours=window_hours,
                    aggregate_sentiment_score=result.aggregate_sentiment_score,
                    article_count=result.article_count,
                    positive_count=result.positive_count,
                    negative_count=result.negative_count,
                    neutral_count=result.neutral_count,
                    signal_strength=result.signal_strength,
                )
            )
            created += 1

    return len(by_entity), created


def _start_pipeline_run() -> int:
    with get_session() as session:
        run = PipelineRun(run_type=PipelineRunType.AGGREGATE.value, status=PipelineStatus.RUNNING.value)
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