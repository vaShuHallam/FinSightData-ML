from app.signals.aggregator import ArticleContribution, aggregate, classify_strength


def contribution(
    sentiment_label: str,
    positive: float,
    negative: float,
    recency: float = 1.0,
    credibility: float = 1.0,
    mentions: int = 1,
) -> ArticleContribution:
    return ArticleContribution(
        sentiment_label=sentiment_label,
        positive_score=positive,
        negative_score=negative,
        recency_weight=recency,
        source_credibility_score=credibility,
        mention_count=mentions,
    )


def test_classify_strength_covers_all_signal_bands():
    assert classify_strength(0.8, 0.6, 0.2) == "Strong Bullish"
    assert classify_strength(0.3, 0.6, 0.2) == "Bullish"
    assert classify_strength(0.0, 0.6, 0.2) == "Neutral"
    assert classify_strength(-0.3, 0.6, 0.2) == "Bearish"
    assert classify_strength(-0.8, 0.6, 0.2) == "Strong Bearish"


def test_aggregate_calculates_weighted_sentiment_and_counts_labels():
    result = aggregate(
        [
            contribution("positive", 0.9, 0.1, credibility=1.0),
            contribution("negative", 0.2, 0.8, credibility=0.5),
            contribution("neutral", 0.51, 0.49, credibility=1.0),
        ],
        strong_threshold=0.6,
        moderate_threshold=0.2,
    )

    # Weights are 1.0, 0.5 and 1.0; scores are +0.8, -0.6 and +0.02.
    # Weighted average = (0.8 - 0.3 + 0.02) / 2.5 = 0.208.
    assert result.aggregate_sentiment_score == 0.208
    assert result.article_count == 3
    assert result.positive_count == 1
    assert result.negative_count == 1
    assert result.neutral_count == 1
    assert result.signal_strength == "Bullish"


def test_aggregate_caps_mention_weight_at_three():
    one_mention = contribution("positive", 1.0, 0.0, mentions=1)
    many_mentions = contribution("negative", 0.0, 1.0, mentions=30)

    result = aggregate([one_mention, many_mentions], strong_threshold=0.6, moderate_threshold=0.2)

    # Mention weight is capped at 3, so score = (1*1 + 3*-1) / 4 = -0.5.
    assert result.aggregate_sentiment_score == -0.5
    assert result.signal_strength == "Bearish"


def test_aggregate_returns_neutral_when_all_contributions_have_zero_weight():
    result = aggregate(
        [contribution("positive", 1.0, 0.0, recency=0.0, credibility=1.0)],
        strong_threshold=0.6,
        moderate_threshold=0.2,
    )

    assert result.aggregate_sentiment_score == 0.0
    assert result.signal_strength == "Neutral"
    assert result.article_count == 1
