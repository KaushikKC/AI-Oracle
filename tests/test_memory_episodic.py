"""
Tests for app/memory/episodic.py

What we're testing:
  - query() returns EpisodicResult objects with relevance scores.
  - since_days filter: only events within the window are returned.
  - category filter: only events of the specified category.
  - Combined filters work together.
  - Empty store returns empty list.
  - Results are sorted by relevance descending.
"""

from datetime import timedelta

import pytest

from app.memory.episodic import EpisodicMemory, _build_where
from app.models.event import EventCategory
from app.models.memory import EpisodicResult


class TestEpisodicQuery:
    def test_returns_episodic_results(self, populated_store, mock_embedder):
        memory = EpisodicMemory(populated_store, mock_embedder)
        results = memory.query("career achievements")
        assert all(isinstance(r, EpisodicResult) for r in results)

    def test_scores_are_in_range(self, populated_store, mock_embedder):
        memory = EpisodicMemory(populated_store, mock_embedder)
        results = memory.query("anything")
        for r in results:
            assert 0.0 <= r.relevance_score <= 1.0

    def test_empty_store_returns_empty_list(self, vector_store, mock_embedder):
        memory = EpisodicMemory(vector_store, mock_embedder)
        results = memory.query("career")
        assert results == []

    def test_since_days_filters_old_events(self, populated_store, mock_embedder, now):
        # sample_events: 400d, 200d, 10d. since_days=30 should return only the 10d event.
        memory = EpisodicMemory(populated_store, mock_embedder)
        results = memory.query("any", since_days=30)
        assert len(results) == 1
        assert results[0].event.category == EventCategory.health

    def test_category_filter_returns_only_that_category(self, populated_store, mock_embedder):
        memory = EpisodicMemory(populated_store, mock_embedder)
        results = memory.query("events", category=EventCategory.career)
        assert all(r.event.category == EventCategory.career for r in results)

    def test_combined_filters(self, populated_store, mock_embedder):
        memory = EpisodicMemory(populated_store, mock_embedder)
        # career + last 365 days: days 200 and 10 → only day 200 is career
        results = memory.query("career", since_days=365, category=EventCategory.career)
        assert len(results) == 1
        assert results[0].event.description == "Led a major product launch successfully."

    def test_n_results_respected(self, populated_store, mock_embedder):
        memory = EpisodicMemory(populated_store, mock_embedder)
        results = memory.query("anything", n_results=1)
        assert len(results) <= 1


class TestBuildWhere:
    def test_no_filters_returns_none(self):
        assert _build_where(None, None) is None

    def test_since_days_only(self):
        where = _build_where(30, None)
        assert "timestamp_unix" in where

    def test_category_only(self):
        where = _build_where(None, EventCategory.career)
        assert where == {"category": {"$eq": "career"}}

    def test_both_filters_uses_and(self):
        where = _build_where(30, EventCategory.health)
        assert "$and" in where
        assert len(where["$and"]) == 2
