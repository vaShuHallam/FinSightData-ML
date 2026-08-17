from app.alerts.relevance_learning import compute_adjustment, apply_adjustment


def test_compute_adjustment_ignores_insufficient_feedback():
    result = compute_adjustment([5], entity_id=42)

    assert result.entity_id == 42
    assert result.feedback_count == 1
    assert result.average_relevance is None
    assert result.threshold_adjustment == 0.0


def test_compute_adjustment_lowers_threshold_for_high_relevance():
    result = compute_adjustment([5, 5], entity_id=7)

    assert result.feedback_count == 2
    assert result.average_relevance == 5.0
    assert result.threshold_adjustment == -0.15


def test_compute_adjustment_raises_threshold_for_low_relevance():
    result = compute_adjustment([1, 1], entity_id=7)

    assert result.average_relevance == 1.0
    assert result.threshold_adjustment == 0.15


def test_compute_adjustment_is_neutral_at_three_star_average():
    result = compute_adjustment([3, 3, 3], entity_id=7)

    assert result.average_relevance == 3.0
    assert result.threshold_adjustment == 0.0


def test_apply_adjustment_clamps_to_lower_bound():
    assert apply_adjustment(0.1, -0.2, min_threshold=0.05, max_threshold=0.95) == 0.05


def test_apply_adjustment_clamps_to_upper_bound():
    assert apply_adjustment(0.9, 0.2, min_threshold=0.05, max_threshold=0.95) == 0.95


def test_apply_adjustment_applies_adjustment_inside_bounds():
    assert apply_adjustment(0.6, -0.1, min_threshold=0.05, max_threshold=0.95) == 0.5
