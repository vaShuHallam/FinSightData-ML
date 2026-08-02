"""
Ingestion pipeline entry point: fetch -> preprocess -> save.

This is Stage 1 (Fetch) + the preprocessing half of Stage 2 from the BRD's
six-stage pipeline. Entity tagging (linking articles to seeded entities via
NER) is a separate step that runs after this, once SpaCy is wired in.
"""

import logging
from datetime import datetime, timezone

from app.db import get_session
from app.ingestion.base import BaseFetcher, RawArticle
from app.ingestion.preprocess import (
    compute_content_hash,
    compute_recency_weight,
    score_credibility,
)
from app.models import Article, PipelineRun, PipelineRunType, PipelineStatus

logger = logging.getLogger(__name__)


def run_ingestion(fetcher: BaseFetcher, query: str, max_results: int = 20) -> dict:
    """
    Fetch articles for `query` via `fetcher`, preprocess, and save new ones.

    Returns a summary dict: {fetched, saved, duplicates}. Also writes a
    pipeline_runs row so ingestion history is auditable from the dashboard,
    per REQ for the pipeline_runs table.
    """
    run_id = _start_pipeline_run()
    fetched = saved = duplicates = 0
    error_detail = None

    try:
        raw_articles = fetcher.fetch(query=query, max_results=max_results)
        fetched = len(raw_articles)
        saved, duplicates = _save_articles(raw_articles)
        status = PipelineStatus.COMPLETED
    except Exception as exc:  # keep ingestion resilient; log and record the failure
        logger.exception("Ingestion run failed")
        status = PipelineStatus.FAILED
        error_detail = str(exc)

    _finish_pipeline_run(run_id, status, articles_processed=saved, error_detail=error_detail)

    summary = {"fetched": fetched, "saved": saved, "duplicates": duplicates, "status": status.value}
    logger.info("Ingestion summary: %s", summary)
    return summary


def _save_articles(raw_articles: list[RawArticle]) -> tuple[int, int]:
    """Insert new articles, skipping ones whose content_hash already exists."""
    saved = duplicates = 0
    now = datetime.now(timezone.utc)

    with get_session() as session:
        existing_hashes = {h for (h,) in session.query(Article.content_hash).all()}

        for raw in raw_articles:
            content_hash = compute_content_hash(raw.headline, raw.source_name)

            if content_hash in existing_hashes:
                duplicates += 1
                continue

            article = Article(
                headline=raw.headline,
                body=raw.body,
                source_name=raw.source_name,
                source_url=raw.source_url,
                source_api=raw.source_api,
                source_credibility_score=score_credibility(raw.source_name),
                published_at=raw.published_at,
                fetched_at=now,
                recency_weight=compute_recency_weight(raw.published_at, now=now),
                is_processed=True,  # ingestion + preprocessing both done at this point
                is_duplicate=False,
                content_hash=content_hash,
            )
            session.add(article)
            existing_hashes.add(content_hash)  # guard against dupes within the same batch
            saved += 1

    return saved, duplicates


def _start_pipeline_run() -> int:
    with get_session() as session:
        run = PipelineRun(run_type=PipelineRunType.FETCH.value, status=PipelineStatus.RUNNING.value)
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
