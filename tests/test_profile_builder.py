"""
Tests for app/profile/builder.py

Key test: "Ingest 20 events → produce a stable, structured UserProfile with explainable values."

Tests cover:
  - Full build from 0 events (defaults)
  - Full build from 20 known events → verify explainable values
  - Incremental update: build + update = same result as single full build
  - Incremental update with no new events returns existing snapshot
  - Incremental update falls back to full build when no snapshot exists
"""

from datetime import datetime, timezone, timedelta
from typing import List

import pytest

from app.models.event import Event, EventCategory
from app.models.profile import ProfileSnapshot
from app.profile.builder import ProfileBuilder
from app.profile.state import ALL_DOMAINS


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_event(
    event_id: int,
    category: EventCategory,
    sentiment: float,
    importance: float,
    days_ago: int = 0,
) -> Event:
    return Event(
        id=event_id,
        timestamp=datetime.now(timezone.utc) - timedelta(days=days_ago),
        category=category,
        sentiment=sentiment,
        importance_score=importance,
        description=f"Event {event_id}",
    )


def make_20_events() -> List[Event]:
    """
    20 events with known properties for the spec's testable output:
      - 8 career events: all positive sentiment (0.7–0.9), high importance → risk_tolerance high
      - 4 health events: mixed sentiment
      - 4 finance events: negative sentiment, high importance → pulls risk_tolerance down
      - 2 relationships + 2 skills: low importance
    """
    events = []
    # Career: positive, high importance (ids 1-8)
    for i in range(1, 9):
        events.append(_make_event(i, EventCategory.career, 0.8, 0.9, days_ago=300 - i * 10))

    # Health: mixed (ids 9-12)
    events.append(_make_event(9,  EventCategory.health, 0.5, 0.6, days_ago=200))
    events.append(_make_event(10, EventCategory.health, -0.3, 0.4, days_ago=180))
    events.append(_make_event(11, EventCategory.health, 0.2, 0.5, days_ago=160))
    events.append(_make_event(12, EventCategory.health, -0.1, 0.3, days_ago=140))

    # Finance: negative, high importance (ids 13-16)
    for i, s in enumerate([-0.7, -0.8, -0.6, -0.5], start=13):
        events.append(_make_event(i, EventCategory.finances, s, 0.85, days_ago=100 - i))

    # Relationships: low importance (ids 17-18)
    events.append(_make_event(17, EventCategory.relationships, 0.6, 0.2, days_ago=50))
    events.append(_make_event(18, EventCategory.relationships, 0.4, 0.3, days_ago=40))

    # Skills: low importance (ids 19-20)
    events.append(_make_event(19, EventCategory.skills, 0.9, 0.2, days_ago=20))
    events.append(_make_event(20, EventCategory.skills, 0.7, 0.3, days_ago=10))

    return events


# ── Full build ────────────────────────────────────────────────────────────────

class TestFullBuild:
    def test_build_with_no_events_returns_defaults(self, db_session):
        builder = ProfileBuilder()
        snapshot = builder.build(db_session)
        assert isinstance(snapshot, ProfileSnapshot)
        assert snapshot.version == 1
        assert snapshot.profile.event_count == 0
        assert snapshot.profile.risk_tolerance == 0.5  # default when no qualifying events
        assert set(snapshot.profile.priorities.keys()) == set(ALL_DOMAINS)

    def test_build_20_events_produces_valid_profile(self, db_session):
        """The spec's testable output: 20 events → stable structured UserProfile."""
        from app.storage import event_repository
        events = make_20_events()
        event_repository.insert_bulk(db_session, events)

        builder = ProfileBuilder()
        snapshot = builder.build(db_session)

        p = snapshot.profile
        assert p.event_count == 20
        assert snapshot.version == 1

        # All fields bounded correctly
        assert 0.0 <= p.risk_tolerance <= 1.0
        assert 0.0 <= p.consistency <= 1.0
        assert set(p.priorities.keys()) == set(ALL_DOMAINS)
        assert abs(sum(p.priorities.values()) - 1.0) < 0.001
        assert set(p.avg_sentiment_by_domain.keys()) == set(ALL_DOMAINS)
        assert set(p.activity_density.keys()) == set(ALL_DOMAINS)

    def test_build_20_events_explainable_risk_tolerance(self, db_session):
        """
        8 career events at +0.8 (risk-seeking) + 4 finance events at -0.65 avg.
        Career/finance combined: 12 events, net positive → risk_tolerance > 0.5.
        But finance is negative → risk_tolerance < 1.0.
        """
        from app.storage import event_repository
        event_repository.insert_bulk(db_session, make_20_events())
        snapshot = ProfileBuilder().build(db_session)
        # Career positive dominates finance negative, but finance pulls down
        assert 0.5 < snapshot.profile.risk_tolerance < 0.9

    def test_build_20_events_career_highest_priority(self, db_session):
        """8 career events at importance=0.9 dominate → career should be highest priority."""
        from app.storage import event_repository
        event_repository.insert_bulk(db_session, make_20_events())
        snapshot = ProfileBuilder().build(db_session)
        priorities = snapshot.profile.priorities
        assert priorities["career"] == max(priorities.values())

    def test_build_20_events_career_positive_sentiment(self, db_session):
        """Career events all have sentiment 0.8 → avg_sentiment_by_domain[career] > 0."""
        from app.storage import event_repository
        event_repository.insert_bulk(db_session, make_20_events())
        snapshot = ProfileBuilder().build(db_session)
        assert snapshot.profile.avg_sentiment_by_domain["career"] > 0.5

    def test_build_20_events_finance_negative_sentiment(self, db_session):
        """Finance events all have negative sentiment → avg_sentiment_by_domain[finances] < 0."""
        from app.storage import event_repository
        event_repository.insert_bulk(db_session, make_20_events())
        snapshot = ProfileBuilder().build(db_session)
        assert snapshot.profile.avg_sentiment_by_domain["finances"] < 0.0

    def test_build_increments_version(self, db_session):
        builder = ProfileBuilder()
        s1 = builder.build(db_session)
        s2 = builder.build(db_session)
        assert s2.version == s1.version + 1


# ── Incremental update ────────────────────────────────────────────────────────

class TestIncrementalUpdate:
    def test_update_falls_back_to_build_when_no_snapshot(self, db_session):
        builder = ProfileBuilder()
        snapshot = builder.update(db_session)
        assert snapshot.version == 1

    def test_update_with_no_new_events_returns_same_snapshot(self, db_session):
        builder = ProfileBuilder()
        s1 = builder.build(db_session)
        s2 = builder.update(db_session)
        assert s1.version == s2.version  # no new events = no new snapshot

    def test_incremental_matches_full_rebuild(self, db_session):
        """
        Build with first 10 events, then update with next 10.
        The final profile should match a full build over all 20.
        """
        from app.storage import event_repository
        all_events = make_20_events()
        first_batch = all_events[:10]
        second_batch = all_events[10:]

        # Insert first 10, full build
        event_repository.insert_bulk(db_session, first_batch)
        builder = ProfileBuilder()
        builder.build(db_session)

        # Insert remaining 10, incremental update
        stored_second = event_repository.insert_bulk(db_session, second_batch)
        incremental = builder.update(db_session, new_events=stored_second)

        # Full rebuild from scratch on same db
        full = builder.build(db_session)

        # Profile values should match (or be very close — same math, same events)
        assert incremental.profile.event_count == full.profile.event_count
        assert abs(incremental.profile.risk_tolerance - full.profile.risk_tolerance) < 0.001
        assert abs(incremental.profile.consistency - full.profile.consistency) < 0.001

    def test_update_with_explicit_events_increments_count(self, db_session):
        from app.storage import event_repository
        events = make_20_events()[:5]
        event_repository.insert_bulk(db_session, events)

        builder = ProfileBuilder()
        s1 = builder.build(db_session)
        assert s1.profile.event_count == 5

        new_events = make_20_events()[5:10]
        stored = event_repository.insert_bulk(db_session, new_events)
        s2 = builder.update(db_session, new_events=stored)

        assert s2.profile.event_count == 10
        assert s2.version == s1.version + 1
