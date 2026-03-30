"""
Tests for app/memory/vector_store.py

What we're testing:
  - add_event / add_bulk: events are stored and retrievable.
  - semantic_query: returns (Event, relevance_score) pairs; handles empty collection.
  - temporal_get: returns events in the correct time window, sorted by timestamp.
  - upsert idempotency: re-adding the same event id doesn't create duplicates.

All tests use the in-memory ChromaDB client and MockEmbedder from conftest.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.memory.vector_store import EventVectorStore
from app.models.event import Event, EventCategory


class TestAddAndCount:
    def test_add_event_increases_count(self, vector_store: EventVectorStore, sample_events):
        assert vector_store.count == 0
        vector_store.add_event(sample_events[0])
        assert vector_store.count == 1

    def test_add_bulk_stores_all(self, vector_store: EventVectorStore, sample_events):
        vector_store.add_bulk(sample_events)
        assert vector_store.count == len(sample_events)

    def test_upsert_is_idempotent(self, vector_store: EventVectorStore, sample_events):
        vector_store.add_event(sample_events[0])
        vector_store.add_event(sample_events[0])  # same id → upsert
        assert vector_store.count == 1


class TestSemanticQuery:
    def test_returns_empty_on_empty_collection(self, vector_store: EventVectorStore):
        result = vector_store.semantic_query([0.1, 0.2, 0.3, 0.4])
        assert result == []

    def test_returns_pairs_with_score(self, populated_store: EventVectorStore):
        results = populated_store.semantic_query([0.1, 0.2, 0.3, 0.4])
        assert len(results) > 0
        for event, score in results:
            assert isinstance(event, Event)
            assert 0.0 <= score <= 1.0

    def test_n_results_limits_output(self, populated_store: EventVectorStore):
        results = populated_store.semantic_query([0.1, 0.2, 0.3, 0.4], n_results=2)
        assert len(results) <= 2

    def test_event_fields_are_reconstructed(self, vector_store: EventVectorStore, sample_events):
        original = sample_events[0]
        vector_store.add_event(original)
        results = vector_store.semantic_query([0.1, 0.2, 0.3, 0.4])
        assert len(results) == 1
        retrieved_event = results[0][0]
        assert retrieved_event.id == original.id
        assert retrieved_event.category == original.category
        assert retrieved_event.description == original.description
        assert abs(retrieved_event.sentiment - original.sentiment) < 1e-5

    def test_where_filter_by_category(self, populated_store: EventVectorStore):
        results = populated_store.semantic_query(
            [0.1, 0.2, 0.3, 0.4],
            where={"category": {"$eq": "health"}},
        )
        assert all(ev.category.value == "health" for ev, _ in results)

    def test_source_raw_roundtrip(self, vector_store: EventVectorStore, now):
        event = Event(
            id=99,
            timestamp=now,
            category=EventCategory.career,
            sentiment=0.5,
            importance_score=0.5,
            description="Promoted.",
            source_raw="Journal entry: got promoted today.",
        )
        vector_store.add_event(event)
        results = vector_store.semantic_query([0.1, 0.2, 0.3, 0.4])
        assert results[0][0].source_raw == "Journal entry: got promoted today."

    def test_none_source_raw_roundtrips_as_none(self, vector_store: EventVectorStore, now):
        event = Event(
            id=100,
            timestamp=now,
            category=EventCategory.health,
            sentiment=0.0,
            importance_score=0.3,
            description="Went for a run.",
            source_raw=None,
        )
        vector_store.add_event(event)
        results = vector_store.semantic_query([0.1, 0.2, 0.3, 0.4])
        assert results[0][0].source_raw is None


class TestTemporalGet:
    def test_returns_events_in_window(self, populated_store: EventVectorStore, now):
        # sample_events: 400 days, 200 days, 10 days ago
        # window = last 365 days → should include days 200 and 10, not 400
        since = (now - timedelta(days=365)).timestamp()
        until = now.timestamp()
        events = populated_store.temporal_get(since, until)
        assert len(events) == 2
        assert all(e.timestamp.timestamp() >= since for e in events)

    def test_excludes_events_outside_window(self, populated_store: EventVectorStore, now):
        since = (now - timedelta(days=30)).timestamp()
        until = now.timestamp()
        events = populated_store.temporal_get(since, until)
        assert len(events) == 1
        assert events[0].category == EventCategory.health

    def test_results_are_sorted_ascending(self, populated_store: EventVectorStore, now):
        since = (now - timedelta(days=1000)).timestamp()
        events = populated_store.temporal_get(since)
        timestamps = [e.timestamp for e in events]
        assert timestamps == sorted(timestamps)

    def test_category_filter(self, populated_store: EventVectorStore, now):
        since = (now - timedelta(days=1000)).timestamp()
        events = populated_store.temporal_get(since, category="career")
        assert all(e.category == EventCategory.career for e in events)
        assert len(events) == 2

    def test_empty_window_returns_empty_list(self, populated_store: EventVectorStore, now):
        far_future = (now + timedelta(days=1)).timestamp()
        events = populated_store.temporal_get(far_future)
        assert events == []
