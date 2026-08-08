import importlib

import pytest


@pytest.fixture
def load_module(tmp_path, monkeypatch):
    db_path = tmp_path / "finsight_test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("SQL_ECHO", "0")
    monkeypatch.setenv("SENTIMENT_BACKEND", "lexicon")

    import app.config as config
    import app.db as db

    importlib.reload(config)
    importlib.reload(db)
    db.drop_db()
    db.init_db()

    def _load(module_name: str):
        module = importlib.import_module(module_name)
        return importlib.reload(module)

    return _load
