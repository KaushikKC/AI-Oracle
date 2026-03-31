"""
Profile snapshot persistence layer.

Each call to ProfileBuilder.build() or ProfileBuilder.update() produces a new
versioned snapshot. Version numbers are sequential (1, 2, 3…).

Two pieces are stored per snapshot:
  profile_json — the UserProfile (what callers read)
  state_json   — the ProfileState running accumulators (what the builder reads
                 to do incremental updates without re-scanning all events)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from app.db.profile_orm import UserProfileSnapshotORM
from app.models.profile import ProfileSnapshot, UserProfile
from app.profile.state import ProfileState


# ── Write ─────────────────────────────────────────────────────────────────────

def save_snapshot(
    db: Session,
    profile: UserProfile,
    state: ProfileState,
) -> ProfileSnapshot:
    """Persist a new snapshot. Version number is auto-incremented."""
    next_version = _next_version(db)
    now = datetime.now(timezone.utc)
    orm = UserProfileSnapshotORM(
        version=next_version,
        event_count=profile.event_count,
        profile_json=profile.model_dump_json(),
        state_json=state.to_json(),
        created_at=now,
    )
    db.add(orm)
    db.commit()
    db.refresh(orm)
    return _orm_to_snapshot(orm)


# ── Read ──────────────────────────────────────────────────────────────────────

def get_latest_snapshot(db: Session) -> Optional[ProfileSnapshot]:
    """Return the most recently saved snapshot, or None if none exist."""
    orm = (
        db.query(UserProfileSnapshotORM)
        .order_by(UserProfileSnapshotORM.version.desc())
        .first()
    )
    return _orm_to_snapshot(orm) if orm else None


def get_latest_state(db: Session) -> Optional[ProfileState]:
    """Return the ProfileState from the most recent snapshot (for incremental updates)."""
    orm = (
        db.query(UserProfileSnapshotORM)
        .order_by(UserProfileSnapshotORM.version.desc())
        .first()
    )
    return ProfileState.from_json(orm.state_json) if orm else None


def get_all_snapshots(db: Session) -> List[ProfileSnapshot]:
    """Return all snapshots ordered oldest → newest."""
    orms = (
        db.query(UserProfileSnapshotORM)
        .order_by(UserProfileSnapshotORM.version.asc())
        .all()
    )
    return [_orm_to_snapshot(orm) for orm in orms]


def get_snapshot_by_version(db: Session, version: int) -> Optional[ProfileSnapshot]:
    orm = (
        db.query(UserProfileSnapshotORM)
        .filter(UserProfileSnapshotORM.version == version)
        .first()
    )
    return _orm_to_snapshot(orm) if orm else None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _next_version(db: Session) -> int:
    latest = (
        db.query(UserProfileSnapshotORM.version)
        .order_by(UserProfileSnapshotORM.version.desc())
        .first()
    )
    return (latest[0] + 1) if latest else 1


def _orm_to_snapshot(orm: UserProfileSnapshotORM) -> ProfileSnapshot:
    return ProfileSnapshot(
        id=orm.id,
        version=orm.version,
        profile=UserProfile.model_validate(json.loads(orm.profile_json)),
        created_at=orm.created_at,
    )
