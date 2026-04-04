"""
Simulation Engine models — Phase 4.

LifeState:        snapshot of current life across 5 domains, each scored 0–10.
Action:           discrete choice with per-domain effect vectors.
Scenario:         one branch of a simulation — projections + confidence + assumptions.
SimulationResult: exactly 3 Scenario objects (optimistic / baseline / conservative).
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Dict, List, Optional

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from app.models.profile import UserProfile


class TimeHorizon(str, Enum):
    six_months = "6mo"
    one_year = "1yr"
    three_years = "3yr"


class ScenarioType(str, Enum):
    optimistic = "optimistic"
    baseline = "baseline"
    conservative = "conservative"


# Domain names that map 1:1 to LifeState fields
LIFE_DOMAINS = [
    "career_level",
    "health_score",
    "financial_runway",
    "relationship_depth",
    "skill_level",
]

# Maps LifeState field names → EventCategory values used in UserProfile
DOMAIN_TO_PROFILE_KEY: Dict[str, str] = {
    "career_level": "career",
    "health_score": "health",
    "financial_runway": "finances",
    "relationship_depth": "relationships",
    "skill_level": "skills",
}


class LifeState(BaseModel):
    """
    Point-in-time snapshot of a user's life across 5 domains.
    Scores are 0.0 (very low) → 10.0 (excellent).
    """
    career_level: float = Field(..., ge=0.0, le=10.0)
    health_score: float = Field(..., ge=0.0, le=10.0)
    financial_runway: float = Field(..., ge=0.0, le=10.0)
    relationship_depth: float = Field(..., ge=0.0, le=10.0)
    skill_level: float = Field(..., ge=0.0, le=10.0)
    as_of: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def get_domain(self, domain: str) -> float:
        return getattr(self, domain)

    def with_domain(self, domain: str, value: float) -> "LifeState":
        return self.model_copy(update={domain: round(max(0.0, min(10.0, value)), 2)})

    @classmethod
    def from_profile(cls, profile: "UserProfile") -> "LifeState":
        """
        Derive a LifeState from UserProfile by mapping domain sentiments
        (−1..1) to scores (0..10).
        """
        s = profile.avg_sentiment_by_domain

        def to_score(profile_key: str) -> float:
            sentiment = s.get(profile_key, 0.0)
            return round(max(0.0, min(10.0, (sentiment + 1.0) / 2.0 * 10.0)), 2)

        return cls(
            career_level=to_score("career"),
            health_score=to_score("health"),
            financial_runway=to_score("finances"),
            relationship_depth=to_score("relationships"),
            skill_level=to_score("skills"),
        )


class ActionEffect(BaseModel):
    """
    Effect of an action on one LifeState domain.

    delta_base: expected change to the domain score (positive or negative).
    variance:   maximum upside deviation from delta_base (always ≥ 0).
                Downside deviation is computed as −variance × (1 − risk_tolerance).
    """
    domain: str           # must be a key in LIFE_DOMAINS
    delta_base: float     # base delta to the domain score
    variance: float = Field(..., ge=0.0)


class Action(BaseModel):
    """A discrete life choice with structured effects on LifeState domains."""
    id: str
    label: str
    description: str
    effects: List[ActionEffect]
    typical_duration_months: int


class DomainProjection(BaseModel):
    """Projected state for one domain after applying an action."""
    domain: str
    current_score: float
    projected_score: float
    delta: float = Field(description="projected_score − current_score")


class Scenario(BaseModel):
    """
    One simulation branch.
    Contains only structured data — no prose.
    """
    scenario_type: ScenarioType
    time_horizon: TimeHorizon
    action: Action
    domain_projections: List[DomainProjection]
    confidence: float = Field(..., ge=0.0, le=1.0)
    assumptions: List[str]


class SimulationResult(BaseModel):
    """
    Output of the simulation engine.
    Always contains exactly 3 scenarios: optimistic, baseline, conservative.
    """
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    life_state: LifeState
    action: Action
    scenarios: List[Scenario] = Field(..., min_length=3, max_length=3)
