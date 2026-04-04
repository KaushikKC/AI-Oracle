"""
Tests for Phase 4 — Simulation Engine.

Coverage:
  - LifeState construction + from_profile derivation
  - Action registry
  - TransitionFunction: deltas, confidence, assumptions
  - BranchingEngine: always produces exactly 3 structured scenarios
  - Constraint enforcement: scores clamped to [0, 10]
  - Profile modulation: risk tolerance and priorities affect output
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.models.profile import UserProfile
from app.models.simulation import (
    LifeState,
    ScenarioType,
    SimulationResult,
    TimeHorizon,
)
from app.simulation.actions import ACTION_REGISTRY, get_action, select_action_for_domain
from app.simulation.engine import BranchingEngine
from app.simulation.transition import compute_delta, compute_confidence, transition
from app.models.simulation import ActionEffect


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_profile(
    risk_tolerance: float = 0.5,
    consistency: float = 0.7,
    priorities: dict | None = None,
    avg_sentiment: dict | None = None,
) -> UserProfile:
    default_priorities = {
        "career": 0.25, "health": 0.20, "finances": 0.20,
        "relationships": 0.15, "skills": 0.15, "other": 0.05,
    }
    default_sentiment = {
        "career": 0.4, "health": 0.2, "finances": 0.0,
        "relationships": 0.3, "skills": 0.5, "other": 0.0,
    }
    return UserProfile(
        risk_tolerance=risk_tolerance,
        consistency=consistency,
        priorities=priorities or default_priorities,
        avg_sentiment_by_domain=avg_sentiment or default_sentiment,
        activity_density={d: 2.0 for d in ["career", "health", "finances", "relationships", "skills", "other"]},
        event_count=50,
        computed_at=datetime.now(timezone.utc),
    )


def make_life_state(
    career_level: float = 6.0,
    health_score: float = 5.0,
    financial_runway: float = 5.0,
    relationship_depth: float = 6.0,
    skill_level: float = 5.5,
) -> LifeState:
    return LifeState(
        career_level=career_level,
        health_score=health_score,
        financial_runway=financial_runway,
        relationship_depth=relationship_depth,
        skill_level=skill_level,
    )


# ── LifeState tests ───────────────────────────────────────────────────────────

class TestLifeState:
    def test_basic_construction(self):
        state = make_life_state()
        assert state.career_level == 6.0
        assert state.health_score == 5.0

    def test_scores_clamped_on_construction(self):
        with pytest.raises(Exception):
            LifeState(
                career_level=11.0,  # out of range
                health_score=5.0,
                financial_runway=5.0,
                relationship_depth=5.0,
                skill_level=5.0,
            )

    def test_get_domain(self):
        state = make_life_state(career_level=7.5)
        assert state.get_domain("career_level") == 7.5

    def test_with_domain_clamps_to_bounds(self):
        state = make_life_state()
        updated = state.with_domain("career_level", 15.0)
        assert updated.career_level == 10.0

        updated_low = state.with_domain("health_score", -5.0)
        assert updated_low.health_score == 0.0

    def test_with_domain_does_not_mutate_original(self):
        state = make_life_state(career_level=5.0)
        _ = state.with_domain("career_level", 8.0)
        assert state.career_level == 5.0

    def test_from_profile_maps_sentiments_to_scores(self):
        profile = make_profile(avg_sentiment={"career": 0.6, "health": -0.2, "finances": 0.0,
                                               "relationships": 0.4, "skills": 0.8, "other": 0.0})
        state = LifeState.from_profile(profile)
        # sentiment 0.6 → (0.6+1)/2 * 10 = 8.0
        assert abs(state.career_level - 8.0) < 0.05
        # sentiment -0.2 → (0.8)/2 * 10 = 4.0
        assert abs(state.health_score - 4.0) < 0.05
        # sentiment 0.0 → 5.0
        assert abs(state.financial_runway - 5.0) < 0.05

    def test_from_profile_scores_within_bounds(self):
        profile = make_profile(avg_sentiment={"career": 1.0, "health": -1.0, "finances": 0.0,
                                               "relationships": 0.0, "skills": 0.0, "other": 0.0})
        state = LifeState.from_profile(profile)
        assert 0.0 <= state.career_level <= 10.0
        assert 0.0 <= state.health_score <= 10.0


# ── Action registry tests ─────────────────────────────────────────────────────

class TestActionRegistry:
    def test_all_actions_have_effects(self):
        for action_id, action in ACTION_REGISTRY.items():
            assert len(action.effects) >= 1, f"{action_id} has no effects"

    def test_all_effect_domains_valid(self):
        from app.models.simulation import LIFE_DOMAINS
        for action_id, action in ACTION_REGISTRY.items():
            for effect in action.effects:
                assert effect.domain in LIFE_DOMAINS, (
                    f"{action_id}: unknown domain {effect.domain!r}"
                )

    def test_get_action_returns_correct_action(self):
        action = get_action("take_new_job")
        assert action.id == "take_new_job"
        assert action.label == "Take a new job"

    def test_get_action_raises_on_unknown(self):
        with pytest.raises(KeyError):
            get_action("nonexistent_action")

    def test_select_action_for_domain_returns_action(self):
        action = select_action_for_domain("health_score")
        assert any(e.domain == "health_score" for e in action.effects)

    def test_action_variance_nonnegative(self):
        for action_id, action in ACTION_REGISTRY.items():
            for effect in action.effects:
                assert effect.variance >= 0, f"{action_id} has negative variance"


# ── TransitionFunction tests ──────────────────────────────────────────────────

class TestTransitionFunction:
    def test_optimistic_greater_than_baseline(self):
        """For positive base deltas, optimistic > baseline (given risk_tolerance > 0)."""
        effect = ActionEffect(domain="career_level", delta_base=1.0, variance=0.5)
        opt = compute_delta(effect, ScenarioType.optimistic, risk_tolerance=0.6,
                            priority_weight=1/6, horizon_scale=1.0)
        base = compute_delta(effect, ScenarioType.baseline, risk_tolerance=0.6,
                             priority_weight=1/6, horizon_scale=1.0)
        assert opt > base

    def test_conservative_less_than_baseline(self):
        """Conservative delta is smaller than baseline for positive variance."""
        effect = ActionEffect(domain="career_level", delta_base=1.0, variance=0.5)
        cons = compute_delta(effect, ScenarioType.conservative, risk_tolerance=0.5,
                             priority_weight=1/6, horizon_scale=1.0)
        base = compute_delta(effect, ScenarioType.baseline, risk_tolerance=0.5,
                             priority_weight=1/6, horizon_scale=1.0)
        assert cons < base

    def test_horizon_scale_increases_delta(self):
        """Longer horizon → larger delta."""
        effect = ActionEffect(domain="career_level", delta_base=1.0, variance=0.3)
        d_6mo = compute_delta(effect, ScenarioType.baseline, 0.5, 1/6, horizon_scale=1.0)
        d_3yr = compute_delta(effect, ScenarioType.baseline, 0.5, 1/6, horizon_scale=2.8)
        assert d_3yr > d_6mo

    def test_high_priority_amplifies_delta(self):
        """High-priority domain → larger effective delta."""
        effect = ActionEffect(domain="career_level", delta_base=1.0, variance=0.3)
        low = compute_delta(effect, ScenarioType.baseline, 0.5, priority_weight=0.05, horizon_scale=1.0)
        high = compute_delta(effect, ScenarioType.baseline, 0.5, priority_weight=0.5, horizon_scale=1.0)
        assert high > low

    def test_transition_returns_three_outputs(self):
        state = make_life_state()
        profile = make_profile()
        action = get_action("start_exercise_routine")
        projections, confidence, assumptions = transition(
            state, action, profile, ScenarioType.baseline, TimeHorizon.one_year
        )
        assert isinstance(projections, list)
        assert len(projections) == len(action.effects)
        assert 0.0 <= confidence <= 1.0
        assert isinstance(assumptions, list)
        assert len(assumptions) >= 1

    def test_projected_scores_within_bounds(self):
        """All projected scores must be in [0, 10]."""
        state = make_life_state()
        profile = make_profile()
        for action in ACTION_REGISTRY.values():
            for stype in ScenarioType:
                projections, _, _ = transition(
                    state, action, profile, stype, TimeHorizon.one_year
                )
                for dp in projections:
                    assert 0.0 <= dp.projected_score <= 10.0, (
                        f"{action.id}/{stype}: {dp.domain}={dp.projected_score}"
                    )

    def test_delta_equals_projected_minus_current(self):
        state = make_life_state()
        profile = make_profile()
        action = get_action("take_new_job")
        projections, _, _ = transition(state, action, profile, ScenarioType.baseline, TimeHorizon.one_year)
        for dp in projections:
            assert abs(dp.delta - (dp.projected_score - dp.current_score)) < 1e-9

    def test_high_risk_tolerance_widens_variance_in_optimistic(self):
        """High-risk user gets larger upside than low-risk user in optimistic scenario."""
        state = make_life_state()
        action = get_action("take_new_job")
        high_risk = make_profile(risk_tolerance=0.9)
        low_risk = make_profile(risk_tolerance=0.1)

        proj_high, _, _ = transition(state, action, high_risk, ScenarioType.optimistic, TimeHorizon.one_year)
        proj_low,  _, _ = transition(state, action, low_risk,  ScenarioType.optimistic, TimeHorizon.one_year)

        career_high = next(p for p in proj_high if p.domain == "career_level")
        career_low  = next(p for p in proj_low  if p.domain == "career_level")
        assert career_high.projected_score >= career_low.projected_score

    def test_low_risk_tolerance_dampens_conservative_downside(self):
        """Low-risk user faces larger downside in conservative scenario."""
        state = make_life_state()
        action = get_action("take_new_job")
        high_risk = make_profile(risk_tolerance=0.9)
        low_risk  = make_profile(risk_tolerance=0.1)

        proj_high, _, _ = transition(state, action, high_risk, ScenarioType.conservative, TimeHorizon.one_year)
        proj_low,  _, _ = transition(state, action, low_risk,  ScenarioType.conservative, TimeHorizon.one_year)

        career_high = next(p for p in proj_high if p.domain == "career_level")
        career_low  = next(p for p in proj_low  if p.domain == "career_level")
        # Low-risk → larger variance subtracted → lower conservative projection
        assert career_low.projected_score <= career_high.projected_score

    def test_assumptions_contain_trade_off_for_negative_effects(self):
        """Actions with negative effects should generate trade-off assumptions."""
        state = make_life_state()
        profile = make_profile()
        action = get_action("take_new_job")  # has negative relationship delta
        _, _, assumptions = transition(state, action, profile, ScenarioType.baseline, TimeHorizon.one_year)
        trade_off_present = any("trade-off" in a.lower() or "decline" in a.lower() for a in assumptions)
        assert trade_off_present

    def test_confidence_lower_for_longer_horizon(self):
        """3-year confidence should be lower than 6-month confidence."""
        state = make_life_state()
        profile = make_profile()
        action = get_action("start_exercise_routine")
        _, conf_6mo, _ = transition(state, action, profile, ScenarioType.baseline, TimeHorizon.six_months)
        _, conf_3yr, _ = transition(state, action, profile, ScenarioType.baseline, TimeHorizon.three_years)
        assert conf_3yr < conf_6mo


# ── BranchingEngine tests ─────────────────────────────────────────────────────

class TestBranchingEngine:
    def test_generate_returns_exactly_three_scenarios(self):
        engine = BranchingEngine()
        state = make_life_state()
        profile = make_profile()
        action = get_action("take_new_job")
        result = engine.generate(state, action, profile)
        assert isinstance(result, SimulationResult)
        assert len(result.scenarios) == 3

    def test_scenarios_cover_all_types(self):
        engine = BranchingEngine()
        result = engine.generate(make_life_state(), get_action("take_new_job"), make_profile())
        types = {s.scenario_type for s in result.scenarios}
        assert types == {ScenarioType.optimistic, ScenarioType.baseline, ScenarioType.conservative}

    def test_scenarios_ordered_optimistic_baseline_conservative(self):
        engine = BranchingEngine()
        result = engine.generate(make_life_state(), get_action("take_new_job"), make_profile())
        assert result.scenarios[0].scenario_type == ScenarioType.optimistic
        assert result.scenarios[1].scenario_type == ScenarioType.baseline
        assert result.scenarios[2].scenario_type == ScenarioType.conservative

    def test_all_scenarios_have_projections(self):
        engine = BranchingEngine()
        result = engine.generate(make_life_state(), get_action("start_exercise_routine"), make_profile())
        for scenario in result.scenarios:
            assert len(scenario.domain_projections) >= 1

    def test_all_scenarios_have_confidence_in_range(self):
        engine = BranchingEngine()
        result = engine.generate(make_life_state(), get_action("seek_promotion"), make_profile())
        for scenario in result.scenarios:
            assert 0.0 <= scenario.confidence <= 1.0

    def test_all_scenarios_have_nonempty_assumptions(self):
        engine = BranchingEngine()
        result = engine.generate(make_life_state(), get_action("invest_in_skills"), make_profile())
        for scenario in result.scenarios:
            assert len(scenario.assumptions) >= 1

    def test_all_scenarios_have_time_horizon(self):
        engine = BranchingEngine()
        result = engine.generate(make_life_state(), get_action("take_new_job"), make_profile(),
                                  time_horizon=TimeHorizon.three_years)
        for scenario in result.scenarios:
            assert scenario.time_horizon == TimeHorizon.three_years

    def test_result_contains_original_state(self):
        engine = BranchingEngine()
        state = make_life_state(career_level=7.0)
        result = engine.generate(state, get_action("take_new_job"), make_profile())
        assert result.life_state.career_level == 7.0

    def test_result_contains_action(self):
        engine = BranchingEngine()
        action = get_action("start_exercise_routine")
        result = engine.generate(make_life_state(), action, make_profile())
        assert result.action.id == "start_exercise_routine"

    def test_optimistic_scores_geq_baseline(self):
        """For positively-affected domains, optimistic ≥ baseline."""
        engine = BranchingEngine()
        state = make_life_state()
        action = get_action("start_exercise_routine")
        result = engine.generate(state, action, make_profile(risk_tolerance=0.6))

        opt  = {p.domain: p.projected_score for p in result.scenarios[0].domain_projections}
        base = {p.domain: p.projected_score for p in result.scenarios[1].domain_projections}

        for dp in action.effects:
            if dp.delta_base > 0:
                assert opt[dp.domain] >= base[dp.domain], (
                    f"{dp.domain}: optimistic={opt[dp.domain]} < baseline={base[dp.domain]}"
                )

    def test_generate_from_profile_returns_three_scenarios(self):
        engine = BranchingEngine()
        result = engine.generate_from_profile(make_life_state(), make_profile())
        assert len(result.scenarios) == 3

    def test_generate_from_profile_selects_top_priority_action(self):
        """Engine should pick an action that targets the user's top domain."""
        engine = BranchingEngine()
        profile = make_profile(priorities={
            "career": 0.50, "health": 0.10, "finances": 0.10,
            "relationships": 0.10, "skills": 0.10, "other": 0.10,
        })
        result = engine.generate_from_profile(make_life_state(), profile)
        # Action chosen should have a career effect
        action_domains = {e.domain for e in result.action.effects}
        assert "career_level" in action_domains

    def test_all_projected_scores_within_bounds(self):
        """End-to-end: no projected score can exceed [0, 10]."""
        engine = BranchingEngine()
        for action in ACTION_REGISTRY.values():
            result = engine.generate(make_life_state(), action, make_profile())
            for scenario in result.scenarios:
                for dp in scenario.domain_projections:
                    assert 0.0 <= dp.projected_score <= 10.0

    def test_default_time_horizon_is_one_year(self):
        engine = BranchingEngine()
        result = engine.generate(make_life_state(), get_action("take_new_job"), make_profile())
        for scenario in result.scenarios:
            assert scenario.time_horizon == TimeHorizon.one_year

    def test_near_max_state_scores_do_not_exceed_10(self):
        """Even from a near-perfect state, optimistic projections stay ≤ 10."""
        engine = BranchingEngine()
        state = make_life_state(career_level=9.8, health_score=9.8, financial_runway=9.8,
                                relationship_depth=9.8, skill_level=9.8)
        result = engine.generate(state, get_action("take_new_job"), make_profile(risk_tolerance=0.95))
        for scenario in result.scenarios:
            for dp in scenario.domain_projections:
                assert dp.projected_score <= 10.0

    def test_near_zero_state_scores_do_not_go_below_0(self):
        """Even from a near-zero state, conservative projections stay ≥ 0."""
        engine = BranchingEngine()
        state = make_life_state(career_level=0.1, health_score=0.1, financial_runway=0.1,
                                relationship_depth=0.1, skill_level=0.1)
        result = engine.generate(state, get_action("reduce_work_hours"),
                                  make_profile(risk_tolerance=0.1))
        for scenario in result.scenarios:
            for dp in scenario.domain_projections:
                assert dp.projected_score >= 0.0
