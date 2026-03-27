from datetime import datetime, timezone

import pytest

from app.models.event import Event, EventCategory
from app.storage import event_repository


def make_event(category=EventCategory.career, sentiment=0.5, description="Test event.") -> Event:
    return Event(
        timestamp=datetime(2024, 3, 1, 12, 0, tzinfo=timezone.utc),
        category=category,
        sentiment=sentiment,
        importance_score=0.6,
        description=description,
    )


def test_insert_single_event_persists(db_session):
    event = make_event()
    stored = event_repository.insert_event(db_session, event)
    assert stored.id is not None
    fetched = event_repository.get_event_by_id(db_session, stored.id)
    assert fetched is not None
    assert fetched.description == "Test event."


def test_insert_bulk_events(db_session):
    events = [make_event(description=f"Event {i}") for i in range(5)]
    stored = event_repository.insert_bulk(db_session, events)
    assert len(stored) == 5
    all_events = event_repository.get_events(db_session)
    assert len(all_events) == 5


def test_get_by_category_filters_correctly(db_session):
    event_repository.insert_bulk(db_session, [
        make_event(category=EventCategory.career),
        make_event(category=EventCategory.health),
        make_event(category=EventCategory.career),
    ])
    career_events = event_repository.get_events(db_session, category=EventCategory.career)
    assert len(career_events) == 2
    assert all(e.category == EventCategory.career for e in career_events)


def test_get_events_sorted_by_timestamp(db_session):
    events = [
        Event(
            timestamp=datetime(2024, 1, d, 12, 0, tzinfo=timezone.utc),
            category=EventCategory.skills,
            sentiment=0.0,
            importance_score=0.5,
            description=f"Day {d}",
        )
        for d in [15, 5, 25, 10]
    ]
    event_repository.insert_bulk(db_session, events)
    fetched = event_repository.get_events(db_session)
    timestamps = [e.timestamp.day for e in fetched]
    assert timestamps == sorted(timestamps)


def test_get_event_by_id_returns_none_for_missing(db_session):
    result = event_repository.get_event_by_id(db_session, 9999)
    assert result is None


def test_insert_event_sets_all_fields(db_session):
    event = Event(
        timestamp=datetime(2024, 6, 1, 8, 0, tzinfo=timezone.utc),
        category=EventCategory.finances,
        sentiment=-0.4,
        importance_score=0.8,
        description="Lost money on a bad investment.",
        source_raw="original journal text",
    )
    stored = event_repository.insert_event(db_session, event)
    assert stored.sentiment == -0.4
    assert stored.importance_score == 0.8
    assert stored.source_raw == "original journal text"
