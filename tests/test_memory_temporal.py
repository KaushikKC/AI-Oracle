"""
Tests for app/memory/temporal.py

What we're testing:
  - query_window() returns a TemporalWindow with correct start/end boundaries.
  - Events outside the window are excluded.
  - Events inside the window appear sorted by timestamp ascending.
  - Category filter works.
  - reference_time parameter makes the window deterministic (no real clock dependency).
  - Empty window returns a valid TemporalWindow with empty events list.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.memory.temporal import TemporalMemory
from app.models.event import EventCategory
from app.models.memory import TemporalWindow


class TestQueryWindow:
    def test_returns_temporal_window(self, populated_store, now):
        memory = TemporalMemory(populated_store)
        result = memory.query_window(window_days=365, reference_time=now)
        assert isinstance(result, TemporalWindow)
        assert result.window_days == 365

    def test_start_end_match_window_days(self, populated_store, now):
        memory = TemporalMemory(populated_store)
        result = memory.query_window(window_days=90, reference_time=now)
        expected_start = now - timedelta(days=90)
        assert abs((result.start - expected_start).total_seconds()) < 1
        assert abs((result.end - now).total_seconds()) < 1

    def test_events_within_window_included(self, populated_store, now):
        memory = TemporalMemory(populated_store)
        # last 365 days: includes day 200 and day 10 (not day 400)
        result = memory.query_window(window_days=365, reference_time=now)
        assert len(result.events) == 2

    def test_events_outside_window_excluded(self, populated_store, now):
        memory = TemporalMemory(populated_store)
        # last 30 days: only the event 10 days ago
        result = memory.query_window(window_days=30, reference_time=now)
        assert len(result.events) == 1

    def test_events_sorted_ascending(self, populated_store, now):
        memory = TemporalMemory(populated_store)
        result = memory.query_window(window_days=1000, reference_time=now)
        timestamps = [e.timestamp for e in result.events]
        assert timestamps == sorted(timestamps)

    def test_category_filter(self, populated_store, now):
        memory = TemporalMemory(populated_store)
        result = memory.query_window(
            window_days=1000,
            category=EventCategory.career,
            reference_time=now,
        )
        assert all(e.category == EventCategory.career for e in result.events)
        assert len(result.events) == 2

    def test_empty_window_returns_empty_events(self, populated_store, now):
        memory = TemporalMemory(populated_store)
        # window of 1 day starting 500 days ago (no events there)
        far_past = now - timedelta(days=500)
        result = memory.query_window(window_days=1, reference_time=far_past + timedelta(days=1))
        assert result.events == []

    def test_reference_time_makes_window_deterministic(self, populated_store, now):
        memory = TemporalMemory(populated_store)
        # Use a fixed reference time → same result every call
        r1 = memory.query_window(window_days=30, reference_time=now)
        r2 = memory.query_window(window_days=30, reference_time=now)
        assert len(r1.events) == len(r2.events)
