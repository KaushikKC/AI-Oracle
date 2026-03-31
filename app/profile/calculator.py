"""
Pure computation functions — each derives one UserProfile variable from ProfileState.

Why separate from the state?
  State manages accumulation (mutable, stateful).
  Calculator manages derivation (pure functions, no side effects, easy to unit-test).
  You can verify "given this exact state, what should risk_tolerance be?" without
  any database, event parsing, or builder logic involved.

All functions are deterministic: same state → same output.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Dict

from app.profile.state import ALL_DOMAINS, ProfileState, welford_std_dev

if TYPE_CHECKING:
    from app.models.profile import UserProfile


# ── Individual variable computations ────────────────────────────────────────

def compute_risk_tolerance(state: ProfileState) -> float:
    """
    How willing is this person to take high-stakes risks in career/finances?

    Formula:
      qualifying = career/finance events with importance_score ≥ 0.5
      avg_sentiment = risk_sentiment_sum / risk_qualifying_count
      risk_tolerance = (avg_sentiment + 1) / 2   [maps −1..1 → 0..1]

    Intuition: someone who logs high-importance career events with positive
    sentiment is taking risks and feeling good about them → risk-seeking.
    Someone who logs them with negative sentiment → risk-averse.
    Default 0.5 = neutral / not enough data.
    """
    if state.risk_qualifying_count == 0:
        return 0.5
    avg_sentiment = state.risk_sentiment_sum / state.risk_qualifying_count
    return round((avg_sentiment + 1.0) / 2.0, 4)


def compute_consistency(state: ProfileState) -> float:
    """
    How consistent is this person's emotional tone across all events?

    Formula:
      std_dev = population_std_dev(all sentiments)   [via Welford's algorithm]
      consistency = 1 − std_dev   (clipped to [0, 1])

    Intuition: sentiment std_dev for values in [−1, 1] ranges from 0 (all same)
    to ~1.0 (maximally spread). Subtracting from 1 inverts the scale so that
    high consistency = high score.
    """
    std_dev = welford_std_dev(state)
    return round(max(0.0, min(1.0, 1.0 - std_dev)), 4)


def compute_priorities(state: ProfileState) -> Dict[str, float]:
    """
    Relative importance assigned to each life domain.

    Formula:
      raw[domain] = sum(importance_score) for all events in that domain
      priorities[domain] = raw[domain] / sum(raw.values())

    Intuition: importance_score reflects how much the user flagged each event
    as significant. Normalizing gives relative share of "life weight" per domain.
    Default: equal weights when no events exist.
    All six domains always present in the output.
    """
    total = sum(state.domain_importance_sums.values())
    if total == 0.0:
        equal = round(1.0 / len(ALL_DOMAINS), 4)
        return {d: equal for d in ALL_DOMAINS}
    return {
        d: round(state.domain_importance_sums.get(d, 0.0) / total, 4)
        for d in ALL_DOMAINS
    }


def compute_avg_sentiment_by_domain(state: ProfileState) -> Dict[str, float]:
    """
    Mean emotional tone per domain.

    Formula:
      avg[domain] = domain_sentiment_sums[domain] / domain_event_counts[domain]

    Intuition: positive = net positive experiences in that domain.
    0.0 for domains with no events (neutral / no data).
    """
    result: Dict[str, float] = {}
    for d in ALL_DOMAINS:
        count = state.domain_event_counts.get(d, 0)
        if count == 0:
            result[d] = 0.0
        else:
            result[d] = round(state.domain_sentiment_sums.get(d, 0.0) / count, 4)
    return result


def compute_activity_density(state: ProfileState) -> Dict[str, float]:
    """
    How actively does this person engage with each domain?

    Formula:
      time_span_days = (max_timestamp − min_timestamp) in days
      periods = max(1, time_span_days / 30)
      density[domain] = domain_event_count / periods

    Unit: events per 30-day period. Minimum denominator of 1 (a single 30-day
    window) prevents division by zero when all events happen the same day.
    0.0 for domains with no events.
    """
    if state.min_timestamp_unix is None or state.max_timestamp_unix is None:
        return {d: 0.0 for d in ALL_DOMAINS}

    time_span_days = (state.max_timestamp_unix - state.min_timestamp_unix) / 86400.0
    periods = max(1.0, time_span_days / 30.0)

    return {
        d: round(state.domain_event_counts.get(d, 0) / periods, 4)
        for d in ALL_DOMAINS
    }


# ── Assembler ─────────────────────────────────────────────────────────────────

def profile_from_state(state: ProfileState) -> "UserProfile":
    """
    Assemble a full UserProfile from a ProfileState.
    This is the only place where all five computed variables come together.
    """
    from app.models.profile import UserProfile
    return UserProfile(
        risk_tolerance=compute_risk_tolerance(state),
        consistency=compute_consistency(state),
        priorities=compute_priorities(state),
        avg_sentiment_by_domain=compute_avg_sentiment_by_domain(state),
        activity_density=compute_activity_density(state),
        event_count=state.total_events,
        computed_at=datetime.now(timezone.utc),
    )
