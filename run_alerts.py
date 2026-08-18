"""
CLI entry point to run one alert-generation cycle.

Usage:
    python run_alerts.py
"""

import logging

from Dashboard.alerts.pipeline import run_alert_generation

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

if __name__ == "__main__":
    summary = run_alert_generation()

    print(f"\nWatchlist entries checked: {summary['watchlist_checked']}")
    print(f"Alerts created:            {summary['alerts_created']}")
    print(f"Status:                    {summary['status']}")