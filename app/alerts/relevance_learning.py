"""
Relevance-learning threshold adjustment (lightweight version of the
BRD Stage 6 "learn from user feedback" layer, deliberately deferred
earlier in this project — see README "Scope decisions").

Core idea: an entity's history of relevance ratings adjusts how strong a
signal needs to be before it becomes an alert for that entity. Consistently
low ratings ("I don't care about this") raise the effective threshold, so
only a strong signal cuts through. Consistently high ratings lower it,
surfacing that entity's alerts more readily.

Lightweight, not full per-user personalization: the schema has no
session_id on Alert/UserFeedback (alerts are currently a shared/global
pool, not per-user), so this computes ONE relevance affinity per entity
from ALL feedback on it, rather than a genuinely personalized score per
user. Fully correct for a single-shared-user demo; a real multi-user
version would need session_id added to UserFeedback first.

The math, kept separate from any DB session so it's independently
testable without a database at all.
"""

from dataclasses import dataclass

# Below this many ratings, we don't trust the average enough to act on it —
# one fluke 1-star or 5-star shouldn't swing a threshold by itself.
MIN_FEEDBACK_COUNT = 2

# How strongly relevance history can move the threshold. At the extremes
# (all 1-star or all 5-star), the threshold shifts by this much in either
# direction. 0.15 is deliberately conservative — this should nudge, not
# override the user's own chosen threshold.
ADJUSTMENT_STRENGTH = 0.15

RATING_MIDPOINT = 3.0  # a 3-star average is "neutral" — no adjustment
RATING_RANGE = 2.0  # distance from midpoint to either end of the 1-5 scale


@dataclass
class RelevanceAdjustment:
    entity_id: int
    feedback_count: int
    average_relevance: float | None  # None if below MIN_FEEDBACK_COUNT
    threshold_adjustment: float  # add this to the base threshold; 0.0 if no data


def compute_adjustment(relevance_scores: list[int], entity_id: int = 0) -> RelevanceAdjustment:
    """
    Pure function: given the raw relevance_score values (1-5) from every
    piece of feedback on this entity's alerts, returns how much to adjust
    the alert threshold by.

    Low average (people don't care) -> POSITIVE adjustment -> higher
    effective threshold -> only strong signals alert.
    High average (people do care) -> NEGATIVE adjustment -> lower
    effective threshold -> alerts fire more readily.
    """
    count = len(relevance_scores)
    if count < MIN_FEEDBACK_COUNT:
        return RelevanceAdjustment(entity_id, count, None, 0.0)

    average = sum(relevance_scores) / count
    normalized_deviation = (average - RATING_MIDPOINT) / RATING_RANGE  # roughly -1..+1
    adjustment = -normalized_deviation * ADJUSTMENT_STRENGTH
    return RelevanceAdjustment(entity_id, count, round(average, 2), round(adjustment, 4))


def apply_adjustment(base_threshold: float, adjustment: float, min_threshold: float = 0.05,
                     max_threshold: float = 0.95) -> float:
    """Apply the adjustment to a base threshold, clamped to a sane range."""
    return max(min_threshold, min(max_threshold, base_threshold + adjustment))
