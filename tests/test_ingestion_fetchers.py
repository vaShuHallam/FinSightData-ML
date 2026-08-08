def test_newsapi_fetch_uses_sample_data_without_key(load_module):
    fetcher_mod = load_module("app.ingestion.newsapi_fetcher")
    config = load_module("app.config")
    config.NEWSAPI_KEY = ""

    rows = fetcher_mod.NewsAPIFetcher().fetch(query="stocks", max_results=3)
    assert len(rows) == 3
    assert all(r.source_api == "NewsAPI" for r in rows)


def test_alphavantage_parse_datetime_invalid(load_module):
    fetcher_mod = load_module("app.ingestion.alphavantage_fetcher")
    assert fetcher_mod.AlphaVantageFetcher._parse_datetime("bad") is None
