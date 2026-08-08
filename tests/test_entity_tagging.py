from datetime import datetime, timezone


def test_rule_based_tagger_counts_mentions(load_module):
    tagger_mod = load_module("app.entity_tagging.rule_based")
    tagger = tagger_mod.RuleBasedEntityTagger.from_db_rows([(1, "Apple Inc.", "AAPL")])

    mentions = tagger.tag("Apple beats estimates", "AAPL jumped while Apple Inc. rallied")
    assert len(mentions) == 1
    assert mentions[0].entity_id == 1
    assert mentions[0].mention_count >= 2


def test_hybrid_tagger_fallbacks_to_rule_based_when_spacy_unavailable(load_module, monkeypatch):
    models = load_module("app.models")
    db = load_module("app.db")
    pipeline = load_module("app.entity_tagging.pipeline")

    with db.get_session() as session:
        session.add(
            models.Entity(
                name="Apple Inc.",
                ticker_symbol="AAPL",
                entity_type=models.EntityType.COMPANY.value,
                sector="Technology",
                exchange="NASDAQ",
            )
        )
        session.add(
            models.Article(
                headline="Apple headline",
                body="Apple body",
                source_name="Reuters",
                source_api="NewsAPI",
                fetched_at=datetime.now(timezone.utc),
                is_processed=True,
                is_duplicate=False,
                content_hash="h1",
            )
        )

    def _raise(*args, **kwargs):
        raise RuntimeError("spacy missing")

    spacy_module = load_module("app.entity_tagging.spacy_tagger")
    monkeypatch.setattr(spacy_module.SpacyEntityTagger, "from_db_rows", _raise)
    tagger = pipeline.build_hybrid_tagger()
    assert tagger.__class__.__name__ == "RuleBasedEntityTagger"
