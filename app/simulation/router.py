"""
Simulation REST endpoints.

GET  /simulate/actions  — list all registered actions (for form dropdown)
POST /simulate/run      — run the branching engine, return 3 scenario branches
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.simulation import LifeState, SimulationResult, TimeHorizon
from app.profile import repository as profile_repo
from app.profile.builder import ProfileBuilder
from app.simulation.actions import ACTION_REGISTRY
from app.simulation.engine import BranchingEngine

router = APIRouter(prefix="/simulate", tags=["simulation"])

_builder = ProfileBuilder()
_engine = BranchingEngine()


# ── Schemas ───────────────────────────────────────────────────────────────────

class ActionInfo(BaseModel):
    id: str
    label: str
    description: str
    typical_duration_months: int
    primary_domains: List[str]  # domains with positive delta_base, sorted by impact


class SimulateRequest(BaseModel):
    action_id: str
    time_horizon: TimeHorizon = TimeHorizon.one_year
    life_state: Optional[LifeState] = None  # if None, derived from latest profile


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/actions", response_model=List[ActionInfo])
def list_actions() -> List[ActionInfo]:
    """Return all available actions for the form dropdown."""
    result = []
    for action in ACTION_REGISTRY.values():
        positive = sorted(
            [e for e in action.effects if e.delta_base > 0],
            key=lambda e: e.delta_base,
            reverse=True,
        )
        result.append(ActionInfo(
            id=action.id,
            label=action.label,
            description=action.description,
            typical_duration_months=action.typical_duration_months,
            primary_domains=[e.domain for e in positive],
        ))
    return result


@router.post("/run", response_model=SimulationResult)
def run_simulation(
    request: SimulateRequest,
    db: Session = Depends(get_db),
) -> SimulationResult:
    """
    Run the simulation engine.

    1. Loads (or builds) the latest UserProfile from SQLite.
    2. Derives LifeState from the profile unless one is provided in the request.
    3. Runs BranchingEngine with the specified action and time horizon.
    4. Returns SimulationResult with exactly 3 scenario branches.
    """
    # Resolve profile
    snapshot = profile_repo.get_latest_snapshot(db)
    if snapshot is None:
        # Auto-build on first run so the client doesn't need a separate step
        try:
            snapshot = _builder.build(db)
        except Exception as exc:
            raise HTTPException(
                status_code=422,
                detail=f"No events found. Seed events first. ({exc})",
            )

    if snapshot is None:
        raise HTTPException(status_code=404, detail="No profile available. Seed events first.")

    # Resolve action
    if request.action_id not in ACTION_REGISTRY:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown action: {request.action_id!r}. "
                   f"Available: {sorted(ACTION_REGISTRY)}",
        )
    action = ACTION_REGISTRY[request.action_id]

    # Resolve life state
    life_state = request.life_state or LifeState.from_profile(snapshot.profile)

    return _engine.generate(
        state=life_state,
        action=action,
        profile=snapshot.profile,
        time_horizon=request.time_horizon,
    )
