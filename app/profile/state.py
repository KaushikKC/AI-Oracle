"""
ProfileState — running accumulators for incremental profile computation.

Why running state instead of re-scanning all events on each update?
  If a user has 10,000 events, recomputing from scratch on each new event
  is O(10,000). With running accumulators, each update is O(new_events_only).

Welford's online algorithm for variance:
  Standard variance requires two passes: one for mean, one for deviations.
  Welford's does it in one pass with numerical stability.
  Reference: Welford (1962), "Note on a method for calculating corrected sums
  of squares and products."

  update rule:
    count += 1
    delta  = value − old_mean
    mean  += delta / count
    delta2 = value − new_mean
    M2    += delta × delta2

  population variance = M2 / count
  std_dev             = sqrt(M2 / count)

last_event_id:
  The SQLite id of the last event processed. Used as a cursor:
    new_events = SELECT * FROM events WHERE id > last_event_id
  This ensures incremental updates never re-process the same event twice.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Dict, Optional


ALL_DOMAINS = ["career", "health", "finances", "relationships", "skills", "other"]
RISK_DOMAINS = {"career", "finances"}
RISK_IMPORTANCE_THRESHOLD = 0.5


@dataclass
class ProfileState:
    total_events: int = 0
    last_event_id: int = 0          # cursor for incremental updates

    # Welford running stats over ALL sentiments (for consistency)
    welford_count: int = 0
    welford_mean: float = 0.0
    welford_m2: float = 0.0         # sum of squared deviations from running mean

    # Per-domain accumulators
    domain_event_counts: Dict[str, int] = field(
        default_factory=lambda: {d: 0 for d in ALL_DOMAINS}
    )
    domain_sentiment_sums: Dict[str, float] = field(
        default_factory=lambda: {d: 0.0 for d in ALL_DOMAINS}
    )
    domain_importance_sums: Dict[str, float] = field(
        default_factory=lambda: {d: 0.0 for d in ALL_DOMAINS}
    )

    # Risk tolerance: only career/finance events with importance ≥ threshold
    risk_qualifying_count: int = 0
    risk_sentiment_sum: float = 0.0

    # Timestamps for activity_density (unix floats)
    min_timestamp_unix: Optional[float] = None
    max_timestamp_unix: Optional[float] = None

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, s: str) -> ProfileState:
        return cls(**json.loads(s))


# ── Welford helpers ──────────────────────────────────────────────────────────

def welford_update(state: ProfileState, value: float) -> None:
    """Incorporate one new sentiment value into the running Welford stats."""
    state.welford_count += 1
    delta = value - state.welford_mean
    state.welford_mean += delta / state.welford_count
    delta2 = value - state.welford_mean
    state.welford_m2 += delta * delta2


def welford_std_dev(state: ProfileState) -> float:
    """Population standard deviation. Returns 0.0 when fewer than 2 data points."""
    if state.welford_count < 2:
        return 0.0
    return (state.welford_m2 / state.welford_count) ** 0.5


# ── State builders ───────────────────────────────────────────────────────────

def build_state_from_events(events: list) -> ProfileState:
    """Build a fresh ProfileState from a list of Event objects (full rebuild)."""
    state = ProfileState()
    _apply_events(state, events)
    return state


def update_state(state: ProfileState, new_events: list) -> ProfileState:
    """Apply new events to an existing state (incremental update). Returns updated state."""
    _apply_events(state, new_events)
    return state


def _apply_events(state: ProfileState, events: list) -> None:
    """Mutate state by processing a list of events."""
    from app.models.event import Event  # avoid circular import at module level
    for event in events:
        domain = event.category.value
        ts = event.timestamp.timestamp()

        # Global counters
        state.total_events += 1
        state.last_event_id = max(state.last_event_id, event.id or 0)

        # Welford update for consistency
        welford_update(state, event.sentiment)

        # Per-domain
        state.domain_event_counts[domain] = state.domain_event_counts.get(domain, 0) + 1
        state.domain_sentiment_sums[domain] = (
            state.domain_sentiment_sums.get(domain, 0.0) + event.sentiment
        )
        state.domain_importance_sums[domain] = (
            state.domain_importance_sums.get(domain, 0.0) + event.importance_score
        )

        # Risk tolerance: career/finance + high importance
        if domain in RISK_DOMAINS and event.importance_score >= RISK_IMPORTANCE_THRESHOLD:
            state.risk_qualifying_count += 1
            state.risk_sentiment_sum += event.sentiment

        # Timestamp bounds
        if state.min_timestamp_unix is None or ts < state.min_timestamp_unix:
            state.min_timestamp_unix = ts
        if state.max_timestamp_unix is None or ts > state.max_timestamp_unix:
            state.max_timestamp_unix = ts
