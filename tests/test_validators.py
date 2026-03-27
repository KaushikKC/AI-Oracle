from datetime import datetime, timezone

from app.ingestion.validators import validate_and_clamp


def base_raw(**overrides) -> dict:
    data = {
        "timestamp": "2024-01-01T10:00:00",
        "category": "career",
        "sentiment": 0.5,
        "importance_score": 0.5,
        "description": "Test event.",
    }
    data.update(overrides)
    return data


def test_clamp_sentiment_above_max():
    result = validate_and_clamp(base_raw(sentiment=1.5))
    assert result["sentiment"] == 1.0


def test_clamp_sentiment_below_min():
    result = validate_and_clamp(base_raw(sentiment=-2.0))
    assert result["sentiment"] == -1.0


def test_clamp_importance_above_max():
    result = validate_and_clamp(base_raw(importance_score=5.0))
    assert result["importance_score"] == 1.0


def test_clamp_importance_below_min():
    result = validate_and_clamp(base_raw(importance_score=-0.5))
    assert result["importance_score"] == 0.0


def test_unknown_category_coerces_to_other():
    result = validate_and_clamp(base_raw(category="UNKNOWN"))
    assert result["category"] == "other"


def test_valid_category_preserved():
    result = validate_and_clamp(base_raw(category="health"))
    assert result["category"] == "health"


def test_naive_timestamp_string_is_made_utc_aware():
    result = validate_and_clamp(base_raw(timestamp="2024-03-15T09:00:00"))
    ts = result["timestamp"]
    assert isinstance(ts, datetime)
    assert ts.tzinfo is not None


def test_naive_datetime_object_is_made_utc_aware():
    naive = datetime(2024, 3, 15, 9, 0, 0)
    result = validate_and_clamp(base_raw(timestamp=naive))
    ts = result["timestamp"]
    assert ts.tzinfo is not None


def test_missing_timestamp_falls_back_to_now():
    result = validate_and_clamp(base_raw(timestamp=None))
    assert isinstance(result["timestamp"], datetime)


def test_invalid_sentiment_string_falls_back_to_zero():
    result = validate_and_clamp(base_raw(sentiment="not-a-number"))
    assert result["sentiment"] == 0.0


def test_invalid_importance_string_falls_back_to_half():
    result = validate_and_clamp(base_raw(importance_score="bad"))
    assert result["importance_score"] == 0.5
