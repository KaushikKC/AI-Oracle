"""
ProfileBuilder — builds and maintains UserProfile from the event history.

Two modes:

  build(db)
    Full rebuild. Scans all events in SQLite, builds a fresh ProfileState
    from scratch, computes the profile, saves a new snapshot.
    Use this: first time, or when you want a guaranteed-clean recompute.

  update(db, new_events=None)
    Incremental update. Loads the ProfileState from the last snapshot,
    applies only the new events (events with id > last_event_id), recomputes
    the profile, saves a new snapshot.
    Falls back to full build if no snapshot exists yet.
    Use this: after ingesting new events — O(new_events) not O(all_events).

Why this is O(new_events) for incremental:
  The ProfileState stores running accumulators (Welford's mean/M2, per-domain
  sums, risk sums, etc.) alongside each snapshot. Updating these accumulators
  requires only one pass over the new events — no historical events are read.
"""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.event import Event
from app.models.profile import ProfileSnapshot
from app.profile.calculator import profile_from_state
from app.profile.state import build_state_from_events, update_state
from app.profile import repository as profile_repo
from app.storage import event_repository


class ProfileBuilder:
    def build(self, db: Session) -> ProfileSnapshot:
        """Full rebuild from all events. Always creates a new snapshot version."""
        events = event_repository.get_all_events(db)
        state = build_state_from_events(events)
        profile = profile_from_state(state)
        return profile_repo.save_snapshot(db, profile, state)

    def update(
        self,
        db: Session,
        new_events: Optional[List[Event]] = None,
    ) -> ProfileSnapshot:
        """
        Incremental update.

        Args:
            db:         SQLAlchemy session.
            new_events: If provided, apply exactly these events.
                        If None, auto-detect by fetching events with
                        id > last_event_id from the latest snapshot.

        Returns:
            The new ProfileSnapshot. If there are no new events at all,
            returns the existing latest snapshot without creating a new version.
        """
        state = profile_repo.get_latest_state(db)

        if state is None:
            # No snapshot exists yet — fall back to full build
            return self.build(db)

        if new_events is None:
            new_events = event_repository.get_events_after(db, state.last_event_id)

        if not new_events:
            # Nothing new — return the current snapshot unchanged
            return profile_repo.get_latest_snapshot(db)

        state = update_state(state, new_events)
        profile = profile_from_state(state)
        return profile_repo.save_snapshot(db, profile, state)
