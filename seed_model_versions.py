"""
Seed the model_versions table with the v1 (baseline) configuration.

model_versions is the table the Evaluation Dashboard reads from for its
v1-vs-v2 comparison view. When a row first gets created here, the three
score columns — macro_f1_score, entity_precision, entity_recall — start
out empty. They only get filled in once you've run the evaluation
harness against the gold-standard set, so don't expect numbers to show
up in the dashboard until that's happened.

Usage:
    python seed_model_versions.py
"""

from datetime import datetime, timezone

from Dashboard.config import SENTIMENT_CONFIDENCE_THRESHOLD
from Dashboard.db import get_session
from Dashboard.models import ModelVersion


def seed() -> None:
    with get_session() as session:
        existing = session.query(ModelVersion).filter_by(version_label="v1").first()
        if existing:
            print("v1 already exists — skipping.")
            return

        session.add(
            ModelVersion(
                version_label="v1",
                model_name="ProsusAI/finbert",
                confidence_threshold=SENTIMENT_CONFIDENCE_THRESHOLD,
                deployed_at=datetime.now(timezone.utc),
            )
        )
    print(f"Seeded model_versions: v1 (ProsusAI/finbert, "
          f"confidence_threshold={SENTIMENT_CONFIDENCE_THRESHOLD})")


if __name__ == "__main__":
    seed()
