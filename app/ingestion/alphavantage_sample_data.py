"""
Sample Alpha Vantage NEWS_SENTIMENT-shaped response, used when
ALPHAVANTAGE_KEY is missing/invalid, or as a fallback if the live schema
ever drifts from what's expected (see the parsing note in
alphavantage_fetcher.py).

Shape mirrors https://www.alphavantage.co/documentation/#news-sentiment
"""

SAMPLE_ALPHAVANTAGE_RESPONSE = {
    "items": "5",
    "sentiment_score_definition": "x <= -0.35: Bearish; -0.35 < x <= -0.15: "
                                   "Somewhat-Bearish; -0.15 < x < 0.15: Neutral; "
                                   "0.15 <= x < 0.35: Somewhat_Bullish; x >= 0.35: Bullish",
    "relevance_score_definition": "0 < x <= 1, with a higher score indicating higher relevance.",
    "feed": [
        {
            "title": "Barclays raises price target on major UK banks after strong earnings",
            "url": "https://example.com/av-barclays-price-target",
            "time_published": "20260728T091500",
            "authors": ["Jane Analyst"],
            "summary": "Barclays analysts raised price targets across several UK banking "
                       "stocks following a stronger-than-expected round of quarterly earnings, "
                       "citing resilient net interest margins and lower-than-feared loan losses.",
            "source": "Reuters",
            "source_domain": "reuters.com",
            "overall_sentiment_score": 0.28,
            "overall_sentiment_label": "Somewhat-Bullish",
            "ticker_sentiment": [
                {"ticker": "BARC", "relevance_score": "0.85", "ticker_sentiment_score": "0.31",
                 "ticker_sentiment_label": "Somewhat-Bullish"}
            ],
        },
        {
            "title": "JPMorgan trims growth outlook amid tariff uncertainty",
            "url": "https://example.com/av-jpmorgan-outlook",
            "time_published": "20260728T083000",
            "authors": ["John Reporter"],
            "summary": "JPMorgan economists trimmed their growth forecasts for the coming "
                       "quarter, pointing to renewed tariff uncertainty and softer consumer "
                       "spending data as headwinds for the broader financial sector.",
            "source": "Bloomberg",
            "source_domain": "bloomberg.com",
            "overall_sentiment_score": -0.22,
            "overall_sentiment_label": "Somewhat-Bearish",
            "ticker_sentiment": [
                {"ticker": "JPM", "relevance_score": "0.79", "ticker_sentiment_score": "-0.25",
                 "ticker_sentiment_label": "Somewhat-Bearish"}
            ],
        },
        {
            "title": "Gold prices steady as investors weigh central bank commentary",
            "url": "https://example.com/av-gold-steady",
            "time_published": "20260728T073000",
            "authors": [],
            "summary": "Gold prices held steady in early trading as investors digested mixed "
                       "commentary from central bank officials, with no clear signal on the "
                       "near-term path for interest rates.",
            "source": "MarketWatch",
            "source_domain": "marketwatch.com",
            "overall_sentiment_score": 0.02,
            "overall_sentiment_label": "Neutral",
            "ticker_sentiment": [],
        },
        {
            "title": "S&P 500 edges higher as tech earnings beat expectations",
            "url": "https://example.com/av-sp500-tech-earnings",
            "time_published": "20260727T200000",
            "authors": ["Alex Market"],
            "summary": "The S&P 500 edged higher in Thursday trading as several major "
                       "technology companies posted quarterly earnings that beat analyst "
                       "expectations, helping offset concerns about slowing consumer demand.",
            "source": "CNBC",
            "source_domain": "cnbc.com",
            "overall_sentiment_score": 0.19,
            "overall_sentiment_label": "Somewhat-Bullish",
            "ticker_sentiment": [],
        },
        {
            "title": "Crude oil slides on oversupply concerns and weak demand data",
            "url": "https://example.com/av-oil-slides",
            "time_published": "20260727T153000",
            "authors": ["Sam Energy"],
            "summary": "Crude oil prices slid more than two percent after new data showed "
                       "rising global inventories and weaker-than-expected demand from major "
                       "importers, reviving concerns about a supply glut heading into next year.",
            "source": "Reuters",
            "source_domain": "reuters.com",
            "overall_sentiment_score": -0.31,
            "overall_sentiment_label": "Somewhat-Bearish",
            "ticker_sentiment": [],
        },
    ],
}
