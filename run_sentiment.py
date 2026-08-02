"""
CLI entry point to run one sentiment-analysis cycle.

Analyzes every article that doesn't yet have a sentiment_results row, using
FinBERT. Requires transformers + torch installed, and internet access to
HuggingFace Hub on first run (downloads ~440MB of model weights, cached
locally after that) — run this on your own machine or Colab, not inside a
network-restricted sandbox.

Usage:
    python run_sentiment.py
    python run_sentiment.py --batch-size 32
"""

import argparse
import logging

from app.sentiment.finbert_analyzer import FinBERTSentimentAnalyzer
from app.sentiment.pipeline import run_sentiment_analysis

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
