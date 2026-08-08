def test_watchlist_service_add_and_get(load_module):
    models = load_module("app.models")
    db = load_module("app.db")
    watchlist_service = load_module("app.services.watchlist_service")

    with db.get_session() as session:
        entity = models.Entity(
            name="Microsoft Corporation",
            ticker_symbol="MSFT",
            entity_type=models.EntityType.COMPANY.value,
            sector="Technology",
            exchange="NASDAQ",
        )
        session.add(entity)
        session.flush()
        entity_id = entity.entity_id

    ok, _ = watchlist_service.add_watchlist_entry(entity_id, "user-a", 0.6, 6)
    assert ok is True

    rows = watchlist_service.get_watchlist("user-a")
    assert len(rows) == 1
    assert rows[0]["entity_name"] == "Microsoft Corporation"
