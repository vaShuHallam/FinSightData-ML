import pytest
from sqlalchemy.exc import IntegrityError


def test_sqlite_foreign_keys_enforced(load_module):
    models = load_module("app.models")
    db = load_module("app.db")

    with pytest.raises(IntegrityError):
        with db.get_session() as session:
            session.add(models.ArticleEntity(article_id=999, entity_id=999, mention_count=1))
