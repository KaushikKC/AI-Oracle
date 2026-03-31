from typing import List

from fastapi import APIRouter, Depends, HTTPException

from app.db.database import get_db
from app.models.profile import ProfileSnapshot
from app.profile.builder import ProfileBuilder
from app.profile import repository as profile_repo
from sqlalchemy.orm import Session


router = APIRouter(prefix="/profile", tags=["profile"])

_builder = ProfileBuilder()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/build", response_model=ProfileSnapshot)
def build_profile(db: Session = Depends(get_db)) -> ProfileSnapshot:
    """
    Full rebuild: scan all events in SQLite and compute a fresh UserProfile.
    Creates a new versioned snapshot. Use this for the first build or a clean recompute.
    """
    try:
        return _builder.build(db)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/update", response_model=ProfileSnapshot)
def update_profile(db: Session = Depends(get_db)) -> ProfileSnapshot:
    """
    Incremental update: apply only events added since the last snapshot.
    O(new_events), not O(all_events). Falls back to full build if no snapshot exists.
    """
    try:
        return _builder.update(db)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/latest", response_model=ProfileSnapshot)
def get_latest_profile(db: Session = Depends(get_db)) -> ProfileSnapshot:
    """Return the most recent UserProfile snapshot."""
    snapshot = profile_repo.get_latest_snapshot(db)
    if snapshot is None:
        raise HTTPException(
            status_code=404,
            detail="No profile built yet. Call POST /profile/build first.",
        )
    return snapshot


@router.get("/history", response_model=List[ProfileSnapshot])
def get_profile_history(db: Session = Depends(get_db)) -> List[ProfileSnapshot]:
    """Return all profile snapshots in chronological order (oldest first)."""
    return profile_repo.get_all_snapshots(db)


@router.get("/{version}", response_model=ProfileSnapshot)
def get_profile_by_version(
    version: int, db: Session = Depends(get_db)
) -> ProfileSnapshot:
    """Return a specific profile snapshot by version number."""
    snapshot = profile_repo.get_snapshot_by_version(db, version)
    if snapshot is None:
        raise HTTPException(status_code=404, detail=f"Profile version {version} not found.")
    return snapshot
