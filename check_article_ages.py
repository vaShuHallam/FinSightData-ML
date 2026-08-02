"""
Quick diagnostic: how old are the articles that got tagged with entities?
Helps confirm whether NewsAPI's free-tier publish delay is why run_signals.py
isn't finding anything within its default 6-hour window.

Usage:
    python check_article_ages.py
"""

from datetime import datetime, timezone

from app.db import get_session
from app.models import Article, ArticleEntity, Entity

with get_session() as s:
    rows = (
        s.query(Entity.name, Article.headline, Article.published_at, Article.fetched_at)
        .join(ArticleEntity, ArticleEntity.article_id == Article.article_id)
        .join(Entity, Entity.entity_id == ArticleEntity.entity_id)
        .all()
    )

now = datetime.now(timezone.utc)

for name, headline, published_at, fetched_at in rows:
    if published_at is not None:
        # SQLite drops timezone info on round-trip; everything in this
        # codebase writes UTC times, so treat a naive value as UTC.
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=timezone.utc)
        age_hours = (now - published_at).total_seconds() / 3600
        age_str = f"{age_hours:.1f}h old"
    else:
        age_str = "no published_at"
    print(f"{name:<20} {age_str:<15} published={published_at}  {headline[:50]}")