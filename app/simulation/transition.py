"""
TransitionFunction — f(state, action, profile, scenario_type, time_horizon) → projections.

Design principles:
  - Pure function: no I/O, no side effects.
  - Deterministic: same inputs → same outputs.
  - Profile-aware:
      risk_tolerance  scales the variance component (high tolerance → larger swings).
      priorities      scales the base delta (user invests more in high-priority domains).
      consistency     informs confidence (stable patterns → more predictable outcomes).

Scenario multipliers:
  optimistic:   applies base delta + full upside variance (scaled by risk_tolerance).
  baseline:     applies base delta only, no variance adjustment.
  conservative: applies base delta − partial downside (scaled by 1 − risk_tolerance).

Time-horizon scaling:
  6mo  → 1.0×
  1yr  → 1.6×
  3yr  → 2.8×  (compounding effect, but confidence decays accordingly)

Confidence heuristic (0..1):
  Starts at a base determined by scenario type.
  +bonus if user is consistent (consistency > 0.7).
  −penalty if action misaligns with top priorities.
  −decay  for longer time horizons.
  Clipped to [0.1, 0.95].
"""

from __future__ import annotations

from typing import List

from app.models.profile import UserProfile
from app.models.simulation import (
    Action,
    ActionEffect,
    DomainProjection,
    LifeState,
    ScenarioType,
    TimeHorizon,
)

# ── Time-horizon scale factors ──────────────────────────────────────────────

_HORIZON_SCALE: dict[TimeHorizon, float] = {
    TimeHorizon.six_months: 1.0,
    TimeHorizon.one_year:   1.6,
    TimeHorizon.three_years: 2.8,
}

# ── Confidence base per scenario type ───────────────────────────────────────

_CONFIDENCE_BASE: dict[ScenarioType, float] = {
    ScenarioType.optimistic:   0.60,
    ScenarioType.baseline:     0.75,
    ScenarioType.conservative: 0.70,
}

_HORIZON_CONFIDENCE_DECAY: dict[TimeHorizon, float] = {
    TimeHorizon.six_months:  0.00,
    TimeHorizon.one_year:    0.05,
    TimeHorizon.three_years: 0.15,
}


def compute_delta(
    effect: ActionEffect,
    scenario_type: ScenarioType,
    risk_tolerance: float,
    priority_weight: float,
    horizon_scale: float,
) -> float:
    """
    Compute the effective delta for one ActionEffect.

    priority_weight:  profile.priorities[domain_profile_key], in [0, 1].
                      Scales the base delta — higher priority → more effort → bigger outcome.
    risk_tolerance:   scales the variance component.
    horizon_scale:    multiplier for the time horizon.
    """
    # Priority amplification: neutral at 0.167 (equal share of 6 domains),
    # scales up to 2× at max priority weight.
    priority_amp = 1.0 + (priority_weight - (1.0 / 6.0)) * 3.0
    priority_amp = max(0.5, min(2.0, priority_amp))

    base = effect.delta_base * priority_amp

    if scenario_type == ScenarioType.optimistic:
        variance_add = effect.variance * risk_tolerance
        delta = base + variance_add
    elif scenario_type == ScenarioType.conservative:
        variance_sub = effect.variance * (1.0 - risk_tolerance)
        delta = base - variance_sub
    else:  # baseline
        delta = base

    return round(delta * horizon_scale, 3)


def compute_confidence(
    action: Action,
    profile: UserProfile,
    scenario_type: ScenarioType,
    time_horizon: TimeHorizon,
) -> float:
    """Heuristic confidence score for a projection."""
    confidence = _CONFIDENCE_BASE[scenario_type]

    # Consistency bonus: stable emotional patterns → more predictable outcomes
    if profile.consistency > 0.7:
        confidence += 0.08
    elif profile.consistency < 0.3:
        confidence -= 0.05

    # Priority alignment: if the action's primary domain matches a top-3 priority,
    # the user is more likely to follow through → higher confidence.
    top_priorities = sorted(profile.priorities, key=profile.priorities.get, reverse=True)[:3]
    from app.models.simulation import DOMAIN_TO_PROFILE_KEY
    primary_effect = max(action.effects, key=lambda e: abs(e.delta_base))
    profile_key = DOMAIN_TO_PROFILE_KEY.get(primary_effect.domain, "")
    if profile_key in top_priorities:
        confidence += 0.07
    else:
        confidence -= 0.05

    # Time horizon decay
    confidence -= _HORIZON_CONFIDENCE_DECAY[time_horizon]

    return round(max(0.1, min(0.95, confidence)), 3)


def build_assumptions(
    action: Action,
    profile: UserProfile,
    scenario_type: ScenarioType,
    time_horizon: TimeHorizon,
) -> List[str]:
    """
    Generate explicit, structured assumptions for this projection.
    All assumptions are deterministic — based only on input values.
    """
    from app.models.simulation import DOMAIN_TO_PROFILE_KEY

    assumptions: List[str] = []

    # Scenario-level assumption
    if scenario_type == ScenarioType.optimistic:
        assumptions.append(
            "User sustains high motivation and follows through on the action without major setbacks."
        )
    elif scenario_type == ScenarioType.conservative:
        assumptions.append(
            "User faces friction during execution; outcomes regress toward the mean."
        )
    else:
        assumptions.append(
            "User executes the action at typical pace with no significant external shocks."
        )

    # Risk tolerance
    if profile.risk_tolerance < 0.35:
        assumptions.append(
            f"Risk tolerance is low ({profile.risk_tolerance:.2f}); upside variance is dampened."
        )
    elif profile.risk_tolerance > 0.7:
        assumptions.append(
            f"Risk tolerance is high ({profile.risk_tolerance:.2f}); variance swings are amplified."
        )

    # Time horizon
    if time_horizon == TimeHorizon.three_years:
        assumptions.append(
            "3-year projection assumes no major life disruptions (relocation, health crisis, market crash)."
        )
    elif time_horizon == TimeHorizon.six_months:
        assumptions.append(
            "6-month projection captures early-stage effects; long-term compounding not modelled."
        )

    # Per-effect assumptions for large negative deltas
    for effect in action.effects:
        if effect.delta_base <= -0.5:
            profile_key = DOMAIN_TO_PROFILE_KEY.get(effect.domain, effect.domain)
            assumptions.append(
                f"Trade-off accepted: {effect.domain} expected to decline "
                f"({effect.delta_base:+.1f} base); monitored and recoverable."
            )

    # Priority alignment
    primary = max(action.effects, key=lambda e: abs(e.delta_base))
    profile_key = DOMAIN_TO_PROFILE_KEY.get(primary.domain, "")
    priority_val = profile.priorities.get(profile_key, 0.0)
    if priority_val < 0.10:
        assumptions.append(
            f"Primary affected domain ({primary.domain}) is not a stated priority "
            f"({priority_val:.0%}); follow-through risk is higher."
        )

    # Consistency
    if profile.consistency < 0.4:
        assumptions.append(
            "Behavioral consistency is low; actual outcomes may diverge significantly from projections."
        )

    return assumptions


# ── Public API ────────────────────────────────────────────────────────────────

def transition(
    state: LifeState,
    action: Action,
    profile: UserProfile,
    scenario_type: ScenarioType,
    time_horizon: TimeHorizon,
) -> tuple[List[DomainProjection], float, List[str]]:
    """
    Core transition function.

    Returns:
        (domain_projections, confidence, assumptions)
    """
    from app.models.simulation import DOMAIN_TO_PROFILE_KEY

    horizon_scale = _HORIZON_SCALE[time_horizon]
    projections: List[DomainProjection] = []

    for effect in action.effects:
        domain = effect.domain
        current = state.get_domain(domain)
        profile_key = DOMAIN_TO_PROFILE_KEY.get(domain, domain)
        priority_weight = profile.priorities.get(profile_key, 1.0 / 6.0)

        delta = compute_delta(
            effect=effect,
            scenario_type=scenario_type,
            risk_tolerance=profile.risk_tolerance,
            priority_weight=priority_weight,
            horizon_scale=horizon_scale,
        )

        projected = round(max(0.0, min(10.0, current + delta)), 2)
        actual_delta = round(projected - current, 2)

        projections.append(DomainProjection(
            domain=domain,
            current_score=current,
            projected_score=projected,
            delta=actual_delta,
        ))

    confidence = compute_confidence(action, profile, scenario_type, time_horizon)
    assumptions = build_assumptions(action, profile, scenario_type, time_horizon)

    return projections, confidence, assumptions
