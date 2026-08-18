"""
CLI entry point to run one entity-tagging cycle.

Usage:
    python run_entity_tagging.py                    # rule-based only (default, no dependencies)
    python run_entity_tagging.py --tagger hybrid     # spaCy (companies) + rule-based (everything else)
"""

import argparse
import logging

from Dashboard.entity_tagging.pipeline import build_hybrid_tagger, build_rule_based_tagger, run_entity_tagging

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tagger", choices=["rule_based", "hybrid"], default="rule_based")
    args = parser.parse_args()

    tagger = build_hybrid_tagger() if args.tagger == "hybrid" else build_rule_based_tagger()
    summary = run_entity_tagging(tagger)

    print(f"\nArticles checked:   {summary['articles_checked']}")
    print(f"Articles tagged:    {summary['articles_tagged']}")
    print(f"Mentions created:   {summary['mentions_created']}")
    print(f"Status:             {summary['status']}")