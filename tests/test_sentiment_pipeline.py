from datetime import datetime, timezone


def test_lexicon_analyzer_shapes_predictions(load_module):
    analyzer_mod = load_module("app.sentiment.lexicon_analyzer")
    analyzer = analyzer_mod.LexiconSentimentAnalyzer(confidence_threshold=0.4)

    preds = analyzer.analyze_batch(
        ["Company reports strong growth and record profits", "Stock slides after weak outlook"]
    )
    assert len(preds) == 2
    assert preds[0].sentiment_label == "positive"
    assert preds[1].sentiment_label == "negative"
    assert all(0.0 <= p.confidence_score <= 1.0 for p in preds)


def test_sentiment_pipeline_writes_article_and_entity_results(load_module):
    models = load_module("app.models")
    db = load_module("app.db")
    sentiment_pipeline = load_module("app.sentiment.pipeline")
    analyzer_mod = load_module("app.sentiment.lexicon_analyzer")

    with db.get_session() as session:
        entity = models.Entity(
            name="Apple Inc.",
            ticker_symbol="AAPL",
            entity_type=models.EntityType.COMPANY.value,
            sector="Technology",
            exchange="NASDAQ",
        )
        session.add(entity)
        session.flush()

        article = models.Article(
            headline="Apple posts strong growth",
            body="Apple Inc. posted strong growth and profits.",
            source_name="Reuters",
            source_api="NewsAPI",
            fetched_at=datetime.now(timezone.utc),
            is_processed=True,
            is_duplicate=False,
            content_hash="a1",
        )
        session.add(article)
        session.flush()
        session.add(models.ArticleEntity(article_id=article.article_id, entity_id=entity.entity_id, mention_count=1))

    analyzer = analyzer_mod.LexiconSentimentAnalyzer(confidence_threshold=0.1)
    summary = sentiment_pipeline.run_sentiment_analysis(analyzer, batch_size=8)
    assert summary["articles_analyzed"] == 1
    assert summary["entity_snippets_analyzed"] == 1

    with db.get_session() as session:
        rows = session.query(models.SentimentResult).all()
        assert len(rows) == 2
        assert any(r.entity_id is None for r in rows)
        assert any(r.entity_id is not None for r in rows)
