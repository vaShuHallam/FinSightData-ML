from datetime import datetime, timedelta, timezone

from app.ingestion import preprocess
from app import config


def test_content_hash_is_normalized_for_case_and_whitespace():
    first = preprocess.compute_content_hash("  Apple beats estimates  ", " Reuters ")
    second = preprocess.compute_content_hash("apple beats estimates", "reuters")

    assert first == second


def test_content_hash_changes_when_source_or_headline_changes():
    base = preprocess.compute_content_hash("Apple beats estimates", "Reuters")

    assert base != preprocess.compute_content_hash("Apple misses estimates", "Reuters")
    assert base != preprocess.compute_content_hash("Apple beats estimates", "Bloomberg")


def test_score_credibility_uses_known_source_and_default_for_unknown():
    assert preprocess.score_credibility("Reuters") == 0.95
    assert preprocess.score_credibility("Unknown Source") == preprocess.DEFAULT_CREDIBILITY
    assert preprocess.score_credibility(None) == preprocess.DEFAULT_CREDIBILITY


def test_score_credibility_respects_runtime_override(monkeypatch):
    monkeypatch.setattr(config, "SOURCE_CREDIBILITY_OVERRIDES", {"Reuters": 0.72})

    assert preprocess.score_credibility("Reuters") == 0.72


def test_recency_weight_is_half_at_one_half_life():
    now = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
    published_at = now - timedelta(hours=preprocess.RECENCY_HALF_LIFE_HOURS)

    assert preprocess.compute_recency_weight(published_at, now=now) == 0.5


def test_recency_weight_never_increases_for_older_articles():
    now = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
    fresh = preprocess.compute_recency_weight(now, now=now)
    old = preprocess.compute_recency_weight(now - timedelta(hours=12), now=now)

    assert fresh == 1.0
    assert old < fresh


def test_recency_weight_handles_naive_datetimes_as_utc():
    now = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
    naive_published_at = datetime(2026, 1, 1, 6)
    aware_published_at = datetime(2026, 1, 1, 6, tzinfo=timezone.utc)

    assert preprocess.compute_recency_weight(naive_published_at, now=now) == preprocess.compute_recency_weight(
        aware_published_at, now=now
    )


def test_recency_weight_defaults_to_half_when_publication_time_is_missing():
    assert preprocess.compute_recency_weight(None) == 0.5
