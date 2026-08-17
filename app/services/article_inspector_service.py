"""
Article Inspector data-access service (REQ-7) — the transparency feature.

Same design decision as the other services: internal equivalents of the
BRD's REST endpoints, called directly by Streamlit.
"""

from datetime import date, datetime, time

from app.db import get_session
from app.models import Article, ArticleEntity, Entity, SentimentResult

SENTIMENT_OPTIONS = ["All", "positive", "negative", "neutral"]


def get_articles(
   
    search: str = "",
    sentiment: str | None = None,
    entity_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[dict]:
    """
    Returns articles for the Article List, each with its sentiment label
    badge, newest first.
    """
    with get_session() as session:
         # Start the query by retrieving:The complete Article object ,The sentiment label associated with the article
        query = (
            session.query(Article, SentimentResult.sentiment_label)
            .outerjoin(SentimentResult, SentimentResult.article_id == Article.article_id)
        )
        # Only apply the search filter if the user entered text
        if search:
            like = f"%{search}%"
             # Search both the article headline AND article body.
            query = query.filter(
                (Article.headline.ilike(like)) | (Article.body.ilike(like))
            )
        if sentiment and sentiment != "All":
            query = query.filter(SentimentResult.sentiment_label == sentiment)
        if entity_id:
            query = query.join(ArticleEntity, ArticleEntity.article_id == Article.article_id).filter(
                ArticleEntity.entity_id == entity_id
            )
        if date_from:
            query = query.filter(Article.published_at >= datetime.combine(date_from, time.min))
        if date_to:
            query = query.filter(Article.published_at <= datetime.combine(date_to, time.max))

        rows = query.order_by(Article.published_at.desc()).all()

        return [
            {
                "article_id": a.article_id,
                "headline": a.headline,
                "source_name": a.source_name,
                "published_at": a.published_at,
                "sentiment_label": label,
            }
            for a, label in rows
        ]


def get_article_detail(article_id: int) -> dict | None:
    """
    Full detail for the Article Detail Panel: metadata, FinBERT scores,
    credibility, recency weight, and detected entities.
    """
    with get_session() as session:
        article = session.get(Article, article_id)
        if article is None:
            return None
         # Find the sentiment result belonging to this article.
        sentiment = (
            session.query(SentimentResult)
            .filter(SentimentResult.article_id == article_id)
            .first()
        )

        entity_names = (
            session.query(Entity.name, Entity.entity_id)
            .join(ArticleEntity, ArticleEntity.entity_id == Entity.entity_id)
            .filter(ArticleEntity.article_id == article_id)
            .all()
        )

        return {
            "headline": article.headline,
            "body": article.body,
            "source_name": article.source_name,
            "source_url": article.source_url,
            "published_at": article.published_at,
            "source_credibility_score": article.source_credibility_score,
            "recency_weight": article.recency_weight,
            "sentiment_label": sentiment.sentiment_label if sentiment else None,
            "positive_score": sentiment.positive_score if sentiment else None,
            "negative_score": sentiment.negative_score if sentiment else None,
            "neutral_score": sentiment.neutral_score if sentiment else None,
            "confidence_score": sentiment.confidence_score if sentiment else None,
            "is_abstained": sentiment.is_abstained if sentiment else None,
            "model_version": sentiment.model_version if sentiment else None,
            "entities": [{"name": n, "entity_id": eid} for n, eid in entity_names],
        }
