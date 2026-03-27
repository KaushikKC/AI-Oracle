from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.models.event import Event, EventCategory


def base_event(**overrides) -> dict:
    data = {
        "timestamp": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "category": EventCategory.career,
        "sentiment": 0.5,
        "importance_score": 0.5,
        "description": "Something happened.",
    }
    data.update(overrides)
    return data


def test_valid_event_constructs():
    event = Event(**base_event())
    assert event.category == EventCategory.career


def test_event_rejects_sentiment_above_max():
    with pytest.raises(ValidationError):
        Event(**base_event(sentiment=1.5))


def test_event_rejects_sentiment_below_min():
    with pytest.raises(ValidationError):
        Event(**base_event(sentiment=-1.1))


def test_event_rejects_importance_above_max():
    with pytest.raises(ValidationError):
        Event(**base_event(importance_score=1.01))


def test_event_rejects_importance_below_min():
    with pytest.raises(ValidationError):
        Event(**base_event(importance_score=-0.1))


def test_event_requires_non_empty_description():
    with pytest.raises(ValidationError):
        Event(**base_event(description="   "))


def test_event_strips_whitespace_from_description():
    event = Event(**base_event(description="  trimmed  "))
    assert event.description == "trimmed"


def test_event_category_must_be_valid_enum():
    with pytest.raises(ValidationError):
        Event(**base_event(category="UNKNOWN"))


def test_event_optional_id_defaults_to_none():
    event = Event(**base_event())
    assert event.id is None


def test_event_source_raw_is_optional():
    event = Event(**base_event())
    assert event.source_raw is None
