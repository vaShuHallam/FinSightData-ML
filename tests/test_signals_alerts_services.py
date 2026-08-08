from datetime import datetime, timedelta, timezone


def test_signal_and_alert_pipeline_generates_alert(load_module):
    models = load_module("app.models")
    db = load_module("app.db")
    signals = load_module("app.signals.pipeline")
    alerts = load_module("app.alerts.pipeline")
    article_service = load_module("app.services.article_inspector_service")

    now = datetime.now(timezone.utc)
    with db.get_session() as session:
        entity = models.Entity(
            name="Tesla Inc.",
            ticker_symbol="TSLA",
            entity_type=models.EntityType.COMPANY.value,
            sector="Automotive",
            exchange="NASDAQ",
        )
        session.add(entity)
        session.flush()

        article = models.Article(
            headline="Tesla posts strong growth",
            body="Tesla shares rise on strong growth",
            source_name="Reuters",
            source_api="NewsAPI",
            published_at=now - timedelta(hours=1),
            fetched_at=now,
            recency_weight=1.0,
            source_credibility_score=0.95,
            is_processed=True,
            is_duplicate=False,
            content_hash="tsla-1",
        )
        session.add(article)
        session.flush()
        session.add(models.ArticleEntity(article_id=article.article_id, entity_id=entity.entity_id, mention_count=2))
        session.add(
            models.SentimentResult(
                article_id=article.article_id,
                entity_id=entity.entity_id,
                sentiment_label="positive",
                positive_score=0.9,
                negative_score=0.05,
                neutral_score=0.05,
                confidence_score=0.9,
                model_version="v1",
                is_abstained=False,
                processed_at=now,
            )
        )
        session.add(
            models.Watchlist(
                session_id="tester",
                entity_id=entity.entity_id,
                alert_threshold=0.2,
                window_size_hours=6,
                is_active=True,
            )
        )

    signal_summary = signals.run_signal_aggregation(window_hours=24)
    alert_summary = alerts.run_alert_generation()
    assert signal_summary["signals_created"] == 1
    assert alert_summary["alerts_created"] == 1

    rows = article_service.get_articles()
    assert len(rows) == 1


def test_neutral_signal_does_not_alert(load_module):
    models = load_module("app.models")
    db = load_module("app.db")
    signals = load_module("app.signals.pipeline")
    alerts = load_module("app.alerts.pipeline")

    now = datetime.now(timezone.utc)
    with db.get_session() as session:
        entity = models.Entity(
            name="Amazon.com Inc.",
            ticker_symbol="AMZN",
            entity_type=models.EntityType.COMPANY.value,
            sector="Consumer",
            exchange="NASDAQ",
        )
        session.add(entity)
        session.flush()
        article = models.Article(
            headline="Amazon mixed quarter",
            body="Amazon results were mixed and mostly in line",
            source_name="Reuters",
            source_api="NewsAPI",
            published_at=now - timedelta(hours=1),
            fetched_at=now,
            recency_weight=1.0,
            source_credibility_score=1.0,
            is_processed=True,
            is_duplicate=False,
            content_hash="amzn-1",
        )
        session.add(article)
        session.flush()
        session.add(models.ArticleEntity(article_id=article.article_id, entity_id=entity.entity_id, mention_count=1))
        session.add(
            models.SentimentResult(
                article_id=article.article_id,
                entity_id=entity.entity_id,
                sentiment_label="neutral",
                positive_score=0.5,
                negative_score=0.5,
                neutral_score=0.0,
                confidence_score=0.5,
                model_version="v1",
                is_abstained=False,
                processed_at=now,
            )
        )
        session.add(
            models.Watchlist(
                session_id="tester",
                entity_id=entity.entity_id,
                alert_threshold=0.1,
                window_size_hours=6,
                is_active=True,
            )
        )

    signals.run_signal_aggregation(window_hours=24)
    alert_summary = alerts.run_alert_generation()
    assert alert_summary["alerts_created"] == 0
