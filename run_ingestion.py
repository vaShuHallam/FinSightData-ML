"""
CLI entry point to run one ingestion cycle.

Usage:
    python run_ingestion.py                                    # NewsAPI, default query
    python run_ingestion.py --query "NVIDIA"
    python run_ingestion.py --source alphavantage --query "AAPL,TSLA"
"""

import argparse
import logging

from Dashboard.ingestion.alphavantage_fetcher import AlphaVantageFetcher
from Dashboard.ingestion.newsapi_fetcher import NewsAPIFetcher
from Dashboard.ingestion.pipeline import run_ingestion

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

DEFAULT_QUERY = "stock market OR earnings OR shares"

FETCHERS = {
    "newsapi": NewsAPIFetcher,
    "alphavantage": AlphaVantageFetcher,
}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run one FinSight AI ingestion cycle.")
    parser.add_argument("--source", choices=list(FETCHERS.keys()), default="newsapi",
                        help="Which source to fetch from (default: newsapi)")
    parser.add_argument("--query", default=None,
                        help="NewsAPI: free-text search. AlphaVantage: comma-separated tickers (e.g. AAPL,TSLA)")
    parser.add_argument("--max-results", type=int, default=20)
    args = parser.parse_args()

    query = args.query or (DEFAULT_QUERY if args.source == "newsapi" else "AAPL,TSLA,MSFT,NVDA,AMZN")

    fetcher = FETCHERS[args.source]()
    summary = run_ingestion(fetcher, query=query, max_results=args.max_results)

    print(f"\nSource:     {args.source}")
    print(f"Fetched:    {summary['fetched']}")
    print(f"Saved:      {summary['saved']}")
    print(f"Duplicates: {summary['duplicates']}")
    print(f"Status:     {summary['status']}")