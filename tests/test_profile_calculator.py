"""
Tests for app/profile/calculator.py

Each test verifies one computed variable with known inputs.
This is the "explainability" layer — you can trace exactly why
a profile has the values it does.

Test structure:
  - One class per computed variable
  - Each test builds a minimal ProfileState manually (no events, no DB)
  - Asserts the exact expected output
"""

import math
import pytest

from app.profile.calculator import (
    compute_activity_density,
    compute_avg_sentiment_by_domain,
    compute_consistency,
    compute_priorities,
    compute_risk_tolerance,
    profile_from_state,
)
from app.profile.state import ALL_DOMAINS, ProfileState, welford_update


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_state_with_sentiments(*sentiments: float) -> ProfileState:
    """Build a minimal state with only Welford stats populated."""
    state = ProfileState()
    for s in sentiments:
        welford_update(state, s)
        state.welford_count  # already updated inside welford_update
    state.total_events = len(sentiments)
    return state


# ── risk_tolerance ────────────────────────────────────────────────────────────

class TestRiskTolerance:
    def test_default_when_no_qualifying_events(self):
        state = ProfileState()
        assert compute_risk_tolerance(state) == 0.5

    def test_max_when_all_high_positive_career(self):
        state = ProfileState()
        state.risk_qualifying_count = 5
        state.risk_sentiment_sum = 5.0   # all sentiment = +1.0
        assert compute_risk_tolerance(state) == 1.0

    def test_min_when_all_high_negative_career(self):
        state = ProfileState()
        state.risk_qualifying_count = 5
        state.risk_sentiment_sum = -5.0  # all sentiment = -1.0
        assert compute_risk_tolerance(state) == 0.0

    def test_neutral_when_mixed(self):
        state = ProfileState()
        state.risk_qualifying_count = 2
        state.risk_sentiment_sum = 0.0   # one +1, one -1
        assert compute_risk_tolerance(state) == 0.5

    def test_partial_positive(self):
        state = ProfileState()
        state.risk_qualifying_count = 4
        state.risk_sentiment_sum = 2.0   # avg = 0.5 → normalized = 0.75
        result = compute_risk_tolerance(state)
        assert abs(result - 0.75) < 0.001


# ── consistency ───────────────────────────────────────────────────────────────

class TestConsistency:
    def test_perfect_consistency_when_all_same(self):
        state = ProfileState()
        for _ in range(5):
            welford_update(state, 0.5)
        result = compute_consistency(state)
        assert result == 1.0

    def test_lower_consistency_with_variance(self):
        state = ProfileState()
        for s in [1.0, -1.0, 1.0, -1.0]:
            welford_update(state, s)
        result = compute_consistency(state)
        # std_dev of [1,-1,1,-1] = 1.0, so consistency = 0.0
        assert result == 0.0

    def test_single_event_is_perfectly_consistent(self):
        # 1 data point → std_dev = 0.0 → consistency = 1.0 (no variance observed)
        state = ProfileState()
        welford_update(state, 0.8)
        assert compute_consistency(state) == 1.0

    def test_no_events_returns_one(self):
        state = ProfileState()
        # 0 events: welford_std_dev = 0.0, consistency = 1.0 - 0.0 = 1.0
        assert compute_consistency(state) == 1.0

    def test_moderate_variance(self):
        state = ProfileState()
        for s in [0.0, 0.5, -0.5, 0.0]:
            welford_update(state, s)
        result = compute_consistency(state)
        assert 0.0 < result < 1.0


# ── priorities ────────────────────────────────────────────────────────────────

class TestPriorities:
    def test_equal_weights_when_no_events(self):
        state = ProfileState()
        p = compute_priorities(state)
        assert set(p.keys()) == set(ALL_DOMAINS)
        values = list(p.values())
        assert all(abs(v - values[0]) < 0.001 for v in values)

    def test_all_domains_present(self):
        state = ProfileState()
        state.domain_importance_sums["career"] = 1.0
        p = compute_priorities(state)
        assert set(p.keys()) == set(ALL_DOMAINS)

    def test_sums_to_one(self):
        state = ProfileState()
        state.domain_importance_sums = {
            "career": 3.0, "health": 1.0, "finances": 2.0,
            "relationships": 0.0, "skills": 4.0, "other": 0.0,
        }
        p = compute_priorities(state)
        assert abs(sum(p.values()) - 1.0) < 0.001

    def test_single_domain_gets_full_weight(self):
        state = ProfileState()
        state.domain_importance_sums["career"] = 5.0
        p = compute_priorities(state)
        assert p["career"] == 1.0
        assert p["health"] == 0.0

    def test_proportional_weights(self):
        state = ProfileState()
        state.domain_importance_sums["career"] = 3.0
        state.domain_importance_sums["health"] = 1.0
        p = compute_priorities(state)
        assert abs(p["career"] - 0.75) < 0.001
        assert abs(p["health"] - 0.25) < 0.001


# ── avg_sentiment_by_domain ───────────────────────────────────────────────────

class TestAvgSentimentByDomain:
    def test_zero_for_empty_domains(self):
        state = ProfileState()
        result = compute_avg_sentiment_by_domain(state)
        assert all(v == 0.0 for v in result.values())

    def test_all_domains_present(self):
        state = ProfileState()
        result = compute_avg_sentiment_by_domain(state)
        assert set(result.keys()) == set(ALL_DOMAINS)

    def test_correct_average(self):
        state = ProfileState()
        state.domain_event_counts["career"] = 3
        state.domain_sentiment_sums["career"] = 1.5  # avg = 0.5
        result = compute_avg_sentiment_by_domain(state)
        assert result["career"] == 0.5

    def test_negative_average(self):
        state = ProfileState()
        state.domain_event_counts["health"] = 2
        state.domain_sentiment_sums["health"] = -1.0  # avg = -0.5
        result = compute_avg_sentiment_by_domain(state)
        assert result["health"] == -0.5


# ── activity_density ──────────────────────────────────────────────────────────

class TestActivityDensity:
    def test_zero_when_no_events(self):
        state = ProfileState()
        result = compute_activity_density(state)
        assert all(v == 0.0 for v in result.values())

    def test_all_domains_present(self):
        state = ProfileState()
        result = compute_activity_density(state)
        assert set(result.keys()) == set(ALL_DOMAINS)

    def test_same_day_events_use_one_period(self):
        from datetime import datetime, timezone
        ts = datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp()
        state = ProfileState()
        state.domain_event_counts["career"] = 6
        state.min_timestamp_unix = ts
        state.max_timestamp_unix = ts  # same day → time_span = 0 → periods = 1
        result = compute_activity_density(state)
        assert result["career"] == 6.0  # 6 events / 1 period

    def test_density_over_multiple_periods(self):
        from datetime import datetime, timezone, timedelta
        t0 = datetime(2024, 1, 1, tzinfo=timezone.utc)
        t1 = t0 + timedelta(days=90)  # 3 months → 3 periods
        state = ProfileState()
        state.domain_event_counts["health"] = 6
        state.min_timestamp_unix = t0.timestamp()
        state.max_timestamp_unix = t1.timestamp()
        result = compute_activity_density(state)
        assert abs(result["health"] - 2.0) < 0.1  # 6 events / 3 periods


# ── profile_from_state ────────────────────────────────────────────────────────

class TestProfileFromState:
    def test_assembles_full_profile(self):
        from app.profile.state import build_state_from_events
        from app.models.event import Event, EventCategory
        from datetime import datetime, timezone

        events = [
            Event(
                id=i,
                timestamp=datetime(2024, i % 12 + 1, 1, tzinfo=timezone.utc),
                category=EventCategory.career,
                sentiment=0.5,
                importance_score=0.8,
                description=f"Event {i}",
            )
            for i in range(1, 6)
        ]
        state = build_state_from_events(events)
        profile = profile_from_state(state)

        assert profile.event_count == 5
        assert 0.0 <= profile.risk_tolerance <= 1.0
        assert 0.0 <= profile.consistency <= 1.0
        assert set(profile.priorities.keys()) == set(ALL_DOMAINS)
        assert abs(sum(profile.priorities.values()) - 1.0) < 0.001
