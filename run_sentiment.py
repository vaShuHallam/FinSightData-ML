"""
CLI entry point to run one sentiment-analysis cycle.

Runs FinBERT sentiment analysis on every article that doesn't have a
sentiment_results row yet. You'll need transformers and torch installed.

Heads up: the first run also needs internet access, since it has to pull
FinBERT's weights (~440MB) from the HuggingFace Hub. After that they're
cached locally (usually under ~/.cache/huggingface), so later runs don't
need a connection at all.

Because of that first download, don't run this in a network-restricted
sandbox — it'll just hang or throw a connection error. Stick to your own
machine or Colab, where you've actually got a connection.

Usage:
    python run_sentiment.py
    python run_sentiment.py --batch-size 32
"""

import argparse
import logging

from Dashboard.sentiment.finbert_analyzer import FinBERTSentimentAnalyzer
from Dashboard.sentiment.pipeline import run_sentiment_analysis

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run one FinSight AI sentiment-analysis cycle.")
    parser.add_argument("--batch-size", type=int, default=16)
    args = parser.parse_args()

    analyzer = FinBERTSentimentAnalyzer()
    summary = run_sentiment_analysis(analyzer, batch_size=args.batch_size)

    print(f"\nArticles checked:  {summary['articles_checked']}")
    print(f"Articles analyzed: {summary['articles_analyzed']}")
    print(f"Abstained:         {summary['abstained']}")
    print(f"Status:            {summary['status']}")
