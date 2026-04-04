"""
BranchingEngine — generates exactly 3 scenario branches from a LifeState + UserProfile.

Usage:
    engine = BranchingEngine()
    result = engine.generate(state, action, profile, time_horizon)
    # result.scenarios == [optimistic_scenario, baseline_scenario, conservative_scenario]

Alternatively, let the engine auto-select an action:
    result = engine.generate_from_profile(state, profile, time_horizon)
    # engine picks the action most aligned with the user's top priority domain.

Both paths always produce SimulationResult with exactly 3 scenarios.
No LLM calls — all logic is deterministic and heuristic.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.models.profile import UserProfile
from app.models.simulation import (
    Action,
    Scenario,
    ScenarioType,
    SimulationResult,
    TimeHorizon,
    LifeState,
    DOMAIN_TO_PROFILE_KEY,
)
from app.simulation.actions import ACTION_REGISTRY, select_action_for_domain
from app.simulation.transition import transition

_SCENARIO_ORDER = [ScenarioType.optimistic, ScenarioType.baseline, ScenarioType.conservative]


class BranchingEngine:
    def generate(
        self,
        state: LifeState,
        action: Action,
        profile: UserProfile,
        time_horizon: TimeHorizon = TimeHorizon.one_year,
    ) -> SimulationResult:
        """
        Generate 3 scenario branches (optimistic / baseline / conservative)
        for a specific action choice.

        Args:
            state:        Current LifeState snapshot.
            action:       The discrete action being evaluated.
            profile:      UserProfile computed from event history.
            time_horizon: Projection window (6mo / 1yr / 3yr).

        Returns:
            SimulationResult with exactly 3 Scenario objects.
        """
        scenarios = []
        for scenario_type in _SCENARIO_ORDER:
            projections, confidence, assumptions = transition(
                state=state,
                action=action,
                profile=profile,
                scenario_type=scenario_type,
                time_horizon=time_horizon,
            )
            scenarios.append(Scenario(
                scenario_type=scenario_type,
                time_horizon=time_horizon,
                action=action,
                domain_projections=projections,
                confidence=confidence,
                assumptions=assumptions,
            ))

        return SimulationResult(
            generated_at=datetime.now(timezone.utc),
            life_state=state,
            action=action,
            scenarios=scenarios,
        )

    def generate_from_profile(
        self,
        state: LifeState,
        profile: UserProfile,
        time_horizon: TimeHorizon = TimeHorizon.one_year,
    ) -> SimulationResult:
        """
        Auto-select the most relevant action based on the user's top priority domain,
        then generate 3 scenario branches.

        Selection logic:
          1. Find the top-priority domain in profile.priorities.
          2. Map it to the corresponding LifeState field name.
          3. Find the action with the largest positive base delta for that domain.
        """
        action = self._select_action(profile)
        return self.generate(state, action, profile, time_horizon)

    def _select_action(self, profile: UserProfile) -> Action:
        """
        Pick the action most aligned with the user's highest-priority domain.
        Falls back to 'invest_in_skills' if no clear match.
        """
        # Reverse DOMAIN_TO_PROFILE_KEY to map profile key → LifeState domain
        profile_key_to_domain = {v: k for k, v in DOMAIN_TO_PROFILE_KEY.items()}

        # Sort profile priorities descending; skip 'other' (no LifeState field)
        ranked = sorted(
            [(k, v) for k, v in profile.priorities.items() if k != "other"],
            key=lambda kv: kv[1],
            reverse=True,
        )

        for profile_key, _ in ranked:
            life_domain = profile_key_to_domain.get(profile_key)
            if life_domain:
                return select_action_for_domain(life_domain)

        return ACTION_REGISTRY["invest_in_skills"]
