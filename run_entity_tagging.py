"""
CLI entry point to run one entity-tagging cycle.

Tags every article that doesn't yet have article_entities rows, using the
rule-based matcher against entities already in the database.

Usage:
    python run_entity_tagging.py
"""

import logging

from app.entity_tagging.pipeline import run_entity_tagging

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

if __name__ == "__main__":
    summary = run_entity_tagging()

    print(f"\nArticles checked:   {summary['articles_checked']}")
    print(f"Articles tagged:    {summary['articles_tagged']}")
    print(f"Mentions created:   {summary['mentions_created']}")
    print(f"Status:             {summary['status']}")
