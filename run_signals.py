"""
CLI entry point to run one signal-aggregation cycle.

Usage:
    python run_signals.py
    python run_signals.py --window-hours 12
"""

import argparse
import logging

from Dashboard.signals.pipeline import run_signal_aggregation

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run one FinSight AI signal-aggregation cycle.")
    parser.add_argument("--window-hours", type=int, default=None)
    args = parser.parse_args()

    summary = run_signal_aggregation(window_hours=args.window_hours)

    print(f"\nEntities checked: {summary['entities_checked']}")
    print(f"Signals created:  {summary['signals_created']}")
    print(f"Status:           {summary['status']}")