"""
Signal aggregation — the math, kept separate from database access so it can
be tested (and reasoned about) independently of SQLAlchemy sessions.

Core idea: each article contributing to an entity's signal gets a weight
based on how credible its source is and how recent it is (both already
computed during preprocessing — see app/ingestion/preprocess.py). A
weighted average of per-article sentiment then becomes the entity's
aggregate signal for the window. This is the step where "one opinion"
becomes "a trend" — the whole reason the pipeline aggregates in windows
rather than alerting on individual articles.

Numeric sentiment per article is (positive_score - negative_score), which
falls naturally in [-1.0, 1.0] — neutral articles contribute close to 0
regardless of which label technically "won", which is the right behavior
for an aggregate trend (a 0.34/0.33/0.33 split shouldn't swing a signal the
same way a 0.95/0.03/0.02 split does).
"""

from dataclasses import dataclass, field

# An article mentioning an entity 4+ times isn't 4x as important as one
# mentioning it once — cap the mention_count's influence on the weight so a
# single verbose article can't dominate a whole window.
MAX_MENTION_WEIGHT = 3


@dataclass
class ArticleContribution:
    """One article's contribution to a single entity's signal for a window."""

    sentiment_label: str
    positive_score: float
    negative_score: float
    recency_weight: float
    source_credibility_score: float
    mention_count: int


@dataclass
class AggregatedSignal:
    aggregate_sentiment_score: float  # -1.0 to 1.0
    article_count: int
    positive_count: int
    negative_count: int
    neutral_count: int
    signal_strength: str


def _weight(contribution: ArticleContribution) -> float:
    mention_factor = min(contribution.mention_count, MAX_MENTION_WEIGHT)
    return contribution.recency_weight * contribution.source_credibility_score * mention_factor


def classify_strength(score: float, strong_threshold: float, moderate_threshold: float) -> str:
    """Map a -1.0..1.0 aggregate score to a signal_strength category."""
    if score >= strong_threshold:
        return "Strong Bullish"
    if score >= moderate_threshold:
        return "Bullish"
    if score <= -strong_threshold:
        return "Strong Bearish"
    if score <= -moderate_threshold:
        return "Bearish"
    return "Neutral"


def aggregate(
    contributions: list[ArticleContribution],
    strong_threshold: float,
    moderate_threshold: float,
) -> AggregatedSignal:
    """
    Combine every article contributing to one entity's window into a single
    AggregatedSignal. Caller guarantees `contributions` is non-empty.
    """
    weighted_sum = 0.0
    weight_total = 0.0
    positive_count = negative_count = neutral_count = 0

    for c in contributions:
        score = c.positive_score - c.negative_score
        w = _weight(c)
        weighted_sum += w * score
        weight_total += w

        if c.sentiment_label == "positive":
            positive_count += 1
        elif c.sentiment_label == "negative":
            negative_count += 1
        else:
            neutral_count += 1

    aggregate_score = (weighted_sum / weight_total) if weight_total > 0 else 0.0
    # Guard against float drift pushing marginally outside [-1, 1]
    aggregate_score = max(-1.0, min(1.0, aggregate_score))

    return AggregatedSignal(
        aggregate_sentiment_score=round(aggregate_score, 4),
        article_count=len(contributions),
        positive_count=positive_count,
        negative_count=negative_count,
        neutral_count=neutral_count,
        signal_strength=classify_strength(aggregate_score, strong_threshold, moderate_threshold),
    )