from app.calculations.confidence import ConfidenceInput, calculate_confidence, confidence_category


def test_complete_recent_sample_has_high_confidence() -> None:
    result = calculate_confidence(
        ConfidenceInput(
            fights_count=10,
            rounds_count=25,
            days_since_last_fight=60,
            weight_class_relevance=1,
            data_completeness=1,
            statistical_consistency=1,
            opponent_sample_quality=1,
        )
    )

    assert result.score == 1
    assert result.category == "high"
    assert result.limitations == ()


def test_sparse_inactive_incomplete_sample_reports_limitations() -> None:
    result = calculate_confidence(
        ConfidenceInput(
            fights_count=1,
            rounds_count=2,
            days_since_last_fight=1000,
            weight_class_relevance=0.4,
            data_completeness=0.6,
            statistical_consistency=0.5,
            opponent_sample_quality=0.2,
            missing_field_ratio=0.5,
        )
    )

    assert result.category == "insufficient"
    assert "small fight sample" in result.limitations
    assert "long inactivity" in result.limitations
    assert "incomplete statistics" in result.limitations
    assert "limited weight-class relevance" in result.limitations


def test_confidence_categories_match_documented_thresholds() -> None:
    assert confidence_category(0.8) == "high"
    assert confidence_category(0.6) == "moderate"
    assert confidence_category(0.4) == "low"
    assert confidence_category(0.39) == "insufficient"
