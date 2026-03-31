"""
Tests for app/profile/repository.py

What we're testing:
  - save_snapshot persists profile + state to SQLite
  - Version numbers auto-increment (1, 2, 3…)
  - get_latest_snapshot returns the highest version
  - get_latest_state returns the ProfileState for incremental updates
  - get_all_snapshots returns snapshots in version order
  - get_snapshot_by_version returns the right one (or None)
"""

from datetime import datetime, timezone

import pytest

from app.models.profile import ProfileSnapshot, UserProfile
from app.profile import repository as repo
from app.profile.state import ProfileState, ALL_DOMAINS


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_profile(event_count: int = 5) -> UserProfile:
    equal = round(1.0 / len(ALL_DOMAINS), 4)
    return UserProfile(
        risk_tolerance=0.7,
        consistency=0.8,
        priorities={d: equal for d in ALL_DOMAINS},
        avg_sentiment_by_domain={d: 0.3 for d in ALL_DOMAINS},
        activity_density={d: 1.0 for d in ALL_DOMAINS},
        event_count=event_count,
        computed_at=datetime.now(timezone.utc),
    )


def _make_state(event_count: int = 5, last_id: int = 5) -> ProfileState:
    state = ProfileState()
    state.total_events = event_count
    state.last_event_id = last_id
    return state


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestSaveSnapshot:
    def test_saves_and_returns_snapshot(self, db_session):
        snapshot = repo.save_snapshot(db_session, _make_profile(), _make_state())
        assert isinstance(snapshot, ProfileSnapshot)
        assert snapshot.id is not None
        assert snapshot.version == 1

    def test_version_increments(self, db_session):
        repo.save_snapshot(db_session, _make_profile(), _make_state())
        repo.save_snapshot(db_session, _make_profile(), _make_state())
        repo.save_snapshot(db_session, _make_profile(), _make_state())
        all_snaps = repo.get_all_snapshots(db_session)
        assert [s.version for s in all_snaps] == [1, 2, 3]

    def test_profile_values_roundtrip(self, db_session):
        original = _make_profile(event_count=42)
        snapshot = repo.save_snapshot(db_session, original, _make_state())
        assert snapshot.profile.event_count == 42
        assert snapshot.profile.risk_tolerance == 0.7
        assert snapshot.profile.consistency == 0.8


class TestGetLatestSnapshot:
    def test_returns_none_when_empty(self, db_session):
        assert repo.get_latest_snapshot(db_session) is None

    def test_returns_most_recent(self, db_session):
        repo.save_snapshot(db_session, _make_profile(1), _make_state(1, 1))
        repo.save_snapshot(db_session, _make_profile(2), _make_state(2, 2))
        repo.save_snapshot(db_session, _make_profile(3), _make_state(3, 3))
        latest = repo.get_latest_snapshot(db_session)
        assert latest.version == 3
        assert latest.profile.event_count == 3


class TestGetLatestState:
    def test_returns_none_when_empty(self, db_session):
        assert repo.get_latest_state(db_session) is None

    def test_returns_state_with_correct_last_event_id(self, db_session):
        state = _make_state(event_count=10, last_id=42)
        repo.save_snapshot(db_session, _make_profile(), state)
        loaded = repo.get_latest_state(db_session)
        assert loaded.total_events == 10
        assert loaded.last_event_id == 42

    def test_returns_state_from_most_recent_snapshot(self, db_session):
        repo.save_snapshot(db_session, _make_profile(), _make_state(last_id=10))
        repo.save_snapshot(db_session, _make_profile(), _make_state(last_id=20))
        loaded = repo.get_latest_state(db_session)
        assert loaded.last_event_id == 20


class TestGetAllSnapshots:
    def test_empty_returns_empty_list(self, db_session):
        assert repo.get_all_snapshots(db_session) == []

    def test_ordered_by_version_ascending(self, db_session):
        for i in range(5):
            repo.save_snapshot(db_session, _make_profile(i), _make_state())
        snaps = repo.get_all_snapshots(db_session)
        assert [s.version for s in snaps] == [1, 2, 3, 4, 5]


class TestGetSnapshotByVersion:
    def test_returns_correct_snapshot(self, db_session):
        repo.save_snapshot(db_session, _make_profile(10), _make_state())
        repo.save_snapshot(db_session, _make_profile(20), _make_state())
        snap = repo.get_snapshot_by_version(db_session, 1)
        assert snap.version == 1
        assert snap.profile.event_count == 10

    def test_returns_none_for_missing_version(self, db_session):
        assert repo.get_snapshot_by_version(db_session, 99) is None
