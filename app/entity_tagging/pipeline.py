"""
Entity-tagging pipeline entry point.

Reads articles that haven't been tagged yet, runs a tagger against each,
and writes results to article_entities.
"""

import logging
from datetime import datetime, timezone

from app.db import get_session
from app.entity_tagging.base import BaseEntityTagger
from app.entity_tagging.rule_based import RuleBasedEntityTagger
from app.models import Article, ArticleEntity, Entity, PipelineRun, PipelineRunType, PipelineStatus

logger = logging.getLogger(__name__)


def build_rule_based_tagger() -> RuleBasedEntityTagger:
    with get_session() as session:
        rows = (
            session.query(Entity.entity_id, Entity.name, Entity.ticker_symbol)
            .filter(Entity.is_active.is_(True))
            .all()
        )
    return RuleBasedEntityTagger.from_db_rows(rows)


def build_hybrid_tagger(spacy_model: str = "en_core_web_trf"):
    """Rule-based for all entities + spaCy specifically for companies. See hybrid_tagger.py."""
    from app.entity_tagging.hybrid_tagger import HybridEntityTagger
    from app.entity_tagging.spacy_tagger import SpacyEntityTagger
    from app.models import EntityType

    rule_based = build_rule_based_tagger()

    with get_session() as session:
        company_rows = (
            session.query(Entity.entity_id, Entity.name, Entity.ticker_symbol)
            .filter(Entity.is_active.is_(True))
            .filter(Entity.entity_type == EntityType.COMPANY.value)
            .all()
        )
    try:
        spacy_tagger = SpacyEntityTagger.from_db_rows(company_rows, model_name=spacy_model)
        return HybridEntityTagger(rule_based, spacy_tagger)
    except Exception as exc:
        logger.warning(
            "spaCy hybrid tagger unavailable (%s). Falling back to rule-based tagger only.",
            exc,
        )
        return rule_based


def run_entity_tagging(tagger: BaseEntityTagger | None = None) -> dict:
    tagger = tagger or build_rule_based_tagger()
    run_id = _start_pipeline_run()
    checked = tagged = mentions_created = 0
    error_detail = None

    try:
        checked, tagged, mentions_created = _tag_untagged_articles(tagger)
        status = PipelineStatus.COMPLETED
    except Exception as exc:
        logger.exception("Entity tagging run failed")
        status = PipelineStatus.FAILED
        error_detail = str(exc)

    _finish_pipeline_run(run_id, status, articles_processed=tagged, error_detail=error_detail)
    summary = {
        "articles_checked": checked, "articles_tagged": tagged,
        "mentions_created": mentions_created, "status": status.value,
    }
    logger.info("Entity tagging summary: %s", summary)
    return summary


def _tag_untagged_articles(tagger: BaseEntityTagger) -> tuple[int, int, int]:
    checked = tagged = mentions_created = 0
    with get_session() as session:
        already_tagged_ids = {aid for (aid,) in session.query(ArticleEntity.article_id).distinct()}
        query = session.query(Article)
        if already_tagged_ids:
            query = query.filter(~Article.article_id.in_(already_tagged_ids))
        articles = query.all()
        checked = len(articles)

        for article in articles:
            mentions = tagger.tag(article.headline, article.body)
            if not mentions:
                continue
            for m in mentions:
                session.add(ArticleEntity(
                    article_id=article.article_id, entity_id=m.entity_id, mention_count=m.mention_count,
                ))
                mentions_created += 1
            tagged += 1

    return checked, tagged, mentions_created


def _start_pipeline_run() -> int:
    with get_session() as session:
        run = PipelineRun(run_type=PipelineRunType.NER.value, status=PipelineStatus.RUNNING.value)
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