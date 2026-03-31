"""
UserProfile — structured variables computed from a user's event history.

Every field is designed to be explainable:
  - risk_tolerance: what events produced this number?
  - consistency:    what's the sentiment variance?
  - priorities:     which domains had the most important events?
  - etc.

ProfileSnapshot wraps UserProfile with versioning metadata for SQLite storage.
"""

from datetime import datetime
from typing import Dict, Optional

from pydantic import BaseModel, Field


class UserProfile(BaseModel):
    # ── Computed variables ────────────────────────────────────────────────────

    # How willing is this person to take high-stakes risks in career/finances?
    # Source: mean normalized sentiment on high-importance (≥0.5) career/finance events.
    # 0.0 = strongly risk-averse  |  0.5 = neutral/unknown  |  1.0 = strongly risk-seeking
    risk_tolerance: float = Field(..., ge=0.0, le=1.0)

    # How consistent is this person's emotional tone across all events?
    # Source: 1 − population_std_dev(all sentiments).
    # 1.0 = perfectly consistent  |  0.0 = maximum variance
    consistency: float = Field(..., ge=0.0, le=1.0)

    # Relative importance assigned to each life domain.
    # Source: sum(importance_score) per domain, normalized to sum to 1.0.
    # All six domains always present; domains with no events get 0.0.
    priorities: Dict[str, float]

    # Average emotional tone per domain.
    # Source: mean(sentiment) per domain. 0.0 for domains with no events.
    avg_sentiment_by_domain: Dict[str, float]

    # How actively does this person engage with each domain?
    # Source: event count per domain ÷ (time_span_days / 30).
    # Unit: events per 30 days. 0.0 for domains with no events.
    activity_density: Dict[str, float]

    # ── Metadata ──────────────────────────────────────────────────────────────
    event_count: int
    computed_at: datetime


class ProfileSnapshot(BaseModel):
    """A versioned, point-in-time snapshot of a UserProfile stored in SQLite."""
    id: Optional[int] = None
    version: int
    profile: UserProfile
    created_at: datetime
