"""
Evaluation Dashboard data-access service (REQ-8).

Same design decision as the other services: internal equivalents of the
BRD's REST endpoints (GET /api/v1/evaluation/metrics, GET
/api/v1/feedback/summary), called directly by Streamlit.

Reads its model-quality numbers from evaluation_results_{version}.json,
produced by compute_gold_standard_metrics.py — that script is the single
source of truth for F1/entity/confusion-matrix numbers, so this service
never recomputes them, only loads and presents them.
"""

import json
import os
from pathlib import Path
from datetime import datetime, timezone

from app.db import get_session
from app.models import Alert, Article, ArticleEntity, SentimentResult, UserFeedback

# (JSON key, display label, lower_is_better) — fixed order matches the
# BRD's Model Metrics Comparison Table exactly. lower_is_better matters for
# delta coloring: for most metrics a higher v2 is an improvement (green),
# but for abstention_rate and time_to_signal, a LOWER v2 is the improvement
# — a naive "positive delta = green" would color a real improvement red.
METRIC_ROWS = [
    ("macro_f1", "Macro F1-Score", False),
    ("positive_f1", "Positive Class F1", False),
    ("negative_f1", "Negative Class F1", False),
    ("neutral_f1", "Neutral Class F1", False),
    ("entity_precision", "Entity Precision", False),
    ("entity_recall", "Entity Recall", False),
    ("abstention_rate", "Abstention Rate", True),
    ("signal_precision", "Signal Precision", False),
    ("mean_relevance_rating", "Mean Relevance Rating", False),
    ("time_to_signal_minutes", "Time to Signal (minutes)", True),
]


def load_results(version_label: str) -> dict | None:
    """Stands in for: GET /api/v1/evaluation/metrics?version="""
    path = f"evaluation_results_{version_label}.json"
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def list_available_result_versions() -> list[str]:
    versions: list[str] = []
    for path in Path(".").glob("evaluation_results_*.json"):
        suffix = path.stem.replace("evaluation_results_", "", 1)
        if suffix:
            versions.append(suffix)
    return sorted(set(versions))


def get_user_testing_results() -> dict:
    """
    Stands in for: GET /api/v1/feedback/summary

    IMPORTANT LIMITATION, worth stating in your report: user_feedback and
    alerts aren't tied to a model_version in the current schema — feedback
    is just "feedback on this alert", not "feedback on v1's alert" vs "v2's
    alert". So these three numbers are a single current snapshot, not
    separately trackable per version. They're shown once and reused in
    both v1/v2 comparison-table columns (with delta shown as N/A) rather
    than fabricating a version split the data doesn't actually support.
    """
    with get_session() as session:
        feedback_rows = session.query(UserFeedback).all()
        mean_relevance = (
            sum(f.relevance_score for f in feedback_rows) / len(feedback_rows)
            if feedback_rows else None
        )
        relevant_count = sum(1 for f in feedback_rows if f.is_relevant)
        signal_precision = (relevant_count / len(feedback_rows)) if feedback_rows else None

        # Time to signal: for each alert, average (alert.created_at - published_at)
        # in minutes across articles that contributed to its underlying signal window.
        alerts = session.query(Alert).all()
        deltas_minutes = []
        for alert in alerts:
            contributing = (
                session.query(Article.published_at)
                .join(ArticleEntity, ArticleEntity.article_id == Article.article_id)
                .join(SentimentResult, SentimentResult.article_id == Article.article_id)
                .filter(ArticleEntity.entity_id == alert.entity_id)
                .filter(Article.published_at.isnot(None))
                .all()
            )
            for (published_at,) in contributing:
                pub = published_at if published_at.tzinfo else published_at.replace(tzinfo=timezone.utc)
                created = alert.created_at if alert.created_at.tzinfo else alert.created_at.replace(tzinfo=timezone.utc)
                delta = (created - pub).total_seconds() / 60.0
                if delta >= 0:  # guard against clock skew producing negative "time travel"
                    deltas_minutes.append(delta)

        time_to_signal = sum(deltas_minutes) / len(deltas_minutes) if deltas_minutes else None

    return {
        "mean_relevance_rating": mean_relevance,
        "signal_precision": signal_precision,
        "time_to_signal_minutes": time_to_signal,
        "n_feedback": len(feedback_rows),
    }


def build_comparison_table(v1: dict | None, v2: dict | None, user_testing: dict) -> list[dict]:
    """Stands in for: assembling the Model Metrics Comparison Table rows."""
    merged_v1 = {**(v1 or {}), **user_testing}
    merged_v2 = {**(v2 or {}), **user_testing} if v2 else None

    rows = []
    for key, label, lower_is_better in METRIC_ROWS:
        v1_val = merged_v1.get(key)
        v2_val = merged_v2.get(key) if merged_v2 else None
        is_user_testing_metric = key in ("signal_precision", "mean_relevance_rating", "time_to_signal_minutes")

        if v1_val is None or v2_val is None:
            delta = None
        elif is_user_testing_metric:
            delta = None  # not meaningfully comparable per-version — see docstring above
        else:
            delta = v2_val - v1_val

        is_improvement = None
        if delta is not None and delta != 0:
            is_improvement = (delta < 0) if lower_is_better else (delta > 0)

        rows.append({
            "metric": label, "v1_result": v1_val, "v2_result": v2_val,
            "delta": delta, "is_improvement": is_improvement,
        })
    return rows


def get_iteration_summary() -> str:
    """Reads iteration_notes.md if present, else a helpful placeholder."""
    if os.path.exists("iteration_notes.md"):
        with open("iteration_notes.md") as f:
            return f.read()
    return (
        "*No iteration notes yet.* Once you run a v2 evaluation, create a file "
        "called `iteration_notes.md` in your project root describing what changed "
        "between v1 and v2 and why — it will display here automatically."
    )
