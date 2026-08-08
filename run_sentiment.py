"""
CLI entry point to run one sentiment-analysis cycle.

Analyzes every article that doesn't yet have sentiment rows. By default this
uses backend=auto, which attempts FinBERT first and falls back to a built-in
lexicon analyzer for local/offline runs.

Usage:
    python run_sentiment.py
    python run_sentiment.py --batch-size 32
    python run_sentiment.py --backend finbert
"""

import argparse
import logging

from app import config
from app.sentiment.finbert_analyzer import FinBERTSentimentAnalyzer
from app.sentiment.lexicon_analyzer import LexiconSentimentAnalyzer
from app.sentiment.pipeline import run_sentiment_analysis

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def _build_analyzer(backend: str):
    backend = backend.lower()
    if backend == "lexicon":
        return LexiconSentimentAnalyzer()
    if backend == "finbert":
        return FinBERTSentimentAnalyzer()
    try:
        return FinBERTSentimentAnalyzer()
    except Exception as exc:
        logging.warning(
            "FinBERT could not be loaded (%s). Falling back to lexicon analyzer for local/offline runs.",
            exc,
        )
        return LexiconSentimentAnalyzer()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run one FinSight AI sentiment-analysis cycle.")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument(
        "--backend",
        choices=["auto", "finbert", "lexicon"],
        default=config.SENTIMENT_BACKEND if config.SENTIMENT_BACKEND in {"auto", "finbert", "lexicon"} else "auto",
        help="Analyzer backend: auto (default), finbert, or lexicon.",
    )
    args = parser.parse_args()

    analyzer = _build_analyzer(args.backend)
    summary = run_sentiment_analysis(analyzer, batch_size=args.batch_size)

    print(f"\nArticles checked:  {summary['articles_checked']}")
    print(f"Articles analyzed: {summary['articles_analyzed']}")
    print(f"Entity snippets:   {summary['entity_snippets_analyzed']}")
    print(f"Abstained:         {summary['abstained']}")
    print(f"Status:            {summary['status']}")
