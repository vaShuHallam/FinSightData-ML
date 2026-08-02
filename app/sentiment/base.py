"""
Base interface for sentiment analyzers.

Same pattern as app/ingestion/base.py and app/entity_tagging/base.py: any
analyzer implementation (FinBERT now, a future fine-tuned version later)
implements this same contract.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class SentimentPrediction:
    """One article's sentiment result, shaped to match sentiment_results columns."""

    sentiment_label: str    # "positive" | "negative" | "neutral"
    positive_score: float
    negative_score: float
    neutral_score: float
    confidence_score: float  # max of the three scores
    is_abstained: bool        # True if confidence_score fell below the threshold


class BaseSentimentAnalyzer(ABC):
    """Common contract for all sentiment-analysis strategies."""

    #: Stored in sentiment_results.model_version — should match a
    #: model_versions.version_label row (see seed_model_versions.py).
    model_version: str = "unknown"

    @abstractmethod
    def analyze_batch(self, texts: list[str]) -> list[SentimentPrediction]:
        """Run sentiment analysis on a batch of texts, in the given order."""
        raise NotImplementedError
