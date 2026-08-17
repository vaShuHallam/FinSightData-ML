"""
Evaluation Dashboard data-access service.

Same design decision as the other services: internal equivalents of the
BRD's REST endpoints. These functions are called directly by Streamlit
"""

import json
import os
from datetime import datetime, timezone

from app.db import get_session
from app.models import Alert, Article, ArticleEntity, SentimentResult, UserFeedback


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

#! LOAD EVALUATION RESULTS
def load_results(version_label: str) -> dict | None:
    """Stands in for: GET /api/v1/evaluation/metrics?version="""
    path = f"evaluation_results_{version_label}.json"
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)

# !USER TESTING RESULTS
def get_user_testing_results() -> dict:
    """
   Gets feedback-related evaluation metrics from the database.
    """
    with get_session() as session:
        feedback_rows = session.query(UserFeedback).all()
        # Calculate the average star/relevance rating
        mean_relevance = (
            sum(f.relevance_score for f in feedback_rows) / len(feedback_rows)
            if feedback_rows else None
        )
        # Count how many feedback records were marked relevant
        relevant_count = sum(1 for f in feedback_rows if f.is_relevant)
        signal_precision = (relevant_count / len(feedback_rows)) if feedback_rows else None

        #! TIME TO SIGNAL
        # Time to signal: for each alert, average (alert.created_at - published_at) in minutes across articles that contributed to its underlying signal window.
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
                # Make sure the publication datetime has UTC timezone.
                pub = published_at if published_at.tzinfo else published_at.replace(tzinfo=timezone.utc)
                 # Calculate the difference between:alert created time and article published time
                created = alert.created_at if alert.created_at.tzinfo else alert.created_at.replace(tzinfo=timezone.utc)
                delta = (created - pub).total_seconds() / 60.0
                
                # Only accept positive time differences.
                if delta >= 0:  # guard against clock skew producing negative "time travel"
                    deltas_minutes.append(delta)
          # Calculate the average time to signal.
        time_to_signal = sum(deltas_minutes) / len(deltas_minutes) if deltas_minutes else None

    return {
        "mean_relevance_rating": mean_relevance,
        "signal_precision": signal_precision,
        "time_to_signal_minutes": time_to_signal,
        "n_feedback": len(feedback_rows),
    }

#! BUILD V1 vs V2 COMPARISON TABLE
def build_comparison_table(v1: dict | None, v2: dict | None, user_testing: dict) -> list[dict]:
    """Stands in for: assembling the Model Metrics Comparison Table rows."""
    merged_v1 = {**(v1 or {}), **user_testing}
    merged_v2 = {**(v2 or {}), **user_testing} if v2 else None

    rows = []
     #! Go through every metric defined in METRIC_ROWS.
    for key, label, lower_is_better in METRIC_ROWS:
        v1_val = merged_v1.get(key)
        v2_val = merged_v2.get(key) if merged_v2 else None
        is_user_testing_metric = key in ("signal_precision", "mean_relevance_rating", "time_to_signal_minutes")
         # CALCULATE DELTA
        if v1_val is None or v2_val is None:
            delta = None
        elif is_user_testing_metric:
            delta = None  # not meaningfully comparable per-version — see docstring above
        else:
            delta = v2_val - v1_val
         # DETERMINE WHETHER V2 IMPROVED
        is_improvement = None
        if delta is not None and delta != 0:
            is_improvement = (delta < 0) if lower_is_better else (delta > 0)

        rows.append({
            "metric": label, "v1_result": v1_val, "v2_result": v2_val,
            "delta": delta, "is_improvement": is_improvement,
        })
    return rows

#! ITERATION SUMMARY
def get_iteration_summary() -> str:
    """  Check whether the notes file exists.."""
    if os.path.exists("iteration_notes.md"):
        with open("iteration_notes.md") as f:
            return f.read()
    return (
        "*No iteration notes yet.* Once you run a v2 evaluation, create a file "
        "called `iteration_notes.md` in your project root describing what changed "
        "between v1 and v2 and why — it will display here automatically."
    )
