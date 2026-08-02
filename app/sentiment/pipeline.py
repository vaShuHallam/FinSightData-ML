"""
Sentiment-analysis pipeline entry point.

Reads articles that don't yet have a sentiment_results row and runs the
analyzer (FinBERT by default) over them in batches, saving results.

Note: this analyzes at the article level (headline + body), matching the
sentiment_results rows where entity_id is null (see the nullable comment in
models.py). Per-entity sentence-level sentiment — needed when one article
covers multiple companies with different sentiment toward each — is a
refinement to layer on once this whole-article version is proven out.
"""

import logging
from datetime import datetime, timezone

from app.db import get_session
from app.models import Article, PipelineRun, PipelineRunType, PipelineStatus, SentimentResult
from app.sentiment.base import BaseSentimentAnalyzer

logger = logging.getLogger(__name__)


def run_sentiment_analysis(analyzer: BaseSentimentAnalyzer, batch_size: int = 16) -> dict:
    """
    Analyze every article that doesn't yet have a sentiment_results row.

    Returns a summary dict: {articles_checked, articles_analyzed, abstained}.
    """
    run_id = _start_pipeline_run()
    checked = analyzed = abstained = 0
    error_detail = None

    try:
        checked, analyzed, abstained = _analyze_unanalyzed_articles(analyzer, batch_size)
        status = PipelineStatus.COMPLETED
    except Exception as exc:
        logger.exception("Sentiment analysis run failed")
        status = PipelineStatus.FAILED
        error_detail = str(exc)

    _finish_pipeline_run(run_id, status, articles_processed=analyzed, error_detail=error_detail)

    summary = {
        "articles_checked": checked,
        "articles_analyzed": analyzed,
        "abstained": abstained,
        "status": status.value,
    }
    logger.info("Sentiment analysis summary: %s", summary)
    return summary


def _analyze_unanalyzed_articles(analyzer: BaseSentimentAnalyzer, batch_size: int) -> tuple[int, int, int]:
    with get_session() as session:
        already_analyzed_ids = {aid for (aid,) in session.query(SentimentResult.article_id).distinct()}
        query = session.query(Article)
        if already_analyzed_ids:
            query = query.filter(~Article.article_id.in_(already_analyzed_ids))
        articles = query.all()

    checked = len(articles)
    if not articles:
        return checked, 0, 0

    texts = [f"{a.headline}. {a.body or ''}" for a in articles]
    predictions = analyzer.analyze_batch(texts, batch_size=batch_size)

    abstained = 0
    now = datetime.now(timezone.utc)
    with get_session() as session:
        for article, pred in zip(articles, predictions):
            session.add(
                SentimentResult(
                    article_id=article.article_id,
                    entity_id=None,  # article-level result; see module docstring
                    sentiment_label=pred.sentiment_label,
                    positive_score=pred.positive_score,
                    negative_score=pred.negative_score,
                    neutral_score=pred.neutral_score,
                    confidence_score=pred.confidence_score,
                    model_version=analyzer.model_version,
                    is_abstained=pred.is_abstained,
                    processed_at=now,
                )
            )
            if pred.is_abstained:
                abstained += 1

    return checked, len(articles), abstained


def _start_pipeline_run() -> int:
    with get_session() as session:
        run = PipelineRun(run_type=PipelineRunType.SENTIMENT.value, status=PipelineStatus.RUNNING.value)
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
