"""
Action registry — discrete life choices with structured effect vectors.

Each Action specifies per-domain deltas and variance.
delta_base: expected score change under normal conditions.
variance:   maximum upside swing; downside is modulated by risk_tolerance in
            the TransitionFunction.

Domain names map to LifeState fields:
  career_level | health_score | financial_runway | relationship_depth | skill_level
"""

from __future__ import annotations

from typing import Dict

from app.models.simulation import Action, ActionEffect

ACTION_REGISTRY: Dict[str, Action] = {
    "take_new_job": Action(
        id="take_new_job",
        label="Take a new job",
        description="Accept a job offer at a different company",
        effects=[
            ActionEffect(domain="career_level",     delta_base=1.5,  variance=1.0),
            ActionEffect(domain="financial_runway",  delta_base=1.0,  variance=0.8),
            ActionEffect(domain="skill_level",       delta_base=0.5,  variance=0.4),
            ActionEffect(domain="relationship_depth", delta_base=-0.5, variance=0.3),
            ActionEffect(domain="health_score",      delta_base=-0.3, variance=0.2),
        ],
        typical_duration_months=6,
    ),
    "start_exercise_routine": Action(
        id="start_exercise_routine",
        label="Start exercise routine",
        description="Commit to a regular physical exercise schedule",
        effects=[
            ActionEffect(domain="health_score",      delta_base=2.0,  variance=0.5),
            ActionEffect(domain="career_level",      delta_base=0.3,  variance=0.2),
            ActionEffect(domain="relationship_depth", delta_base=0.2, variance=0.2),
            ActionEffect(domain="financial_runway",  delta_base=-0.2, variance=0.1),
        ],
        typical_duration_months=3,
    ),
    "reduce_social_commitments": Action(
        id="reduce_social_commitments",
        label="Reduce social commitments",
        description="Cut back on social obligations to reclaim time and energy",
        effects=[
            ActionEffect(domain="skill_level",       delta_base=0.8,  variance=0.4),
            ActionEffect(domain="health_score",      delta_base=0.5,  variance=0.3),
            ActionEffect(domain="career_level",      delta_base=0.4,  variance=0.3),
            ActionEffect(domain="relationship_depth", delta_base=-1.0, variance=0.5),
        ],
        typical_duration_months=6,
    ),
    "seek_promotion": Action(
        id="seek_promotion",
        label="Seek a promotion",
        description="Actively pursue a step up in your current organization",
        effects=[
            ActionEffect(domain="career_level",     delta_base=1.2,  variance=0.8),
            ActionEffect(domain="financial_runway",  delta_base=0.8,  variance=0.5),
            ActionEffect(domain="skill_level",       delta_base=0.5,  variance=0.3),
            ActionEffect(domain="health_score",      delta_base=-0.4, variance=0.2),
            ActionEffect(domain="relationship_depth", delta_base=-0.3, variance=0.2),
        ],
        typical_duration_months=12,
    ),
    "invest_in_skills": Action(
        id="invest_in_skills",
        label="Invest in skills",
        description="Dedicate time to learning new skills or deepening existing ones",
        effects=[
            ActionEffect(domain="skill_level",       delta_base=2.0,  variance=0.6),
            ActionEffect(domain="career_level",      delta_base=0.7,  variance=0.5),
            ActionEffect(domain="financial_runway",  delta_base=-0.5, variance=0.2),
            ActionEffect(domain="health_score",      delta_base=-0.2, variance=0.1),
        ],
        typical_duration_months=6,
    ),
    "build_relationships": Action(
        id="build_relationships",
        label="Build relationships",
        description="Invest deliberately in social and professional connections",
        effects=[
            ActionEffect(domain="relationship_depth", delta_base=2.0,  variance=0.5),
            ActionEffect(domain="career_level",      delta_base=0.5,  variance=0.4),
            ActionEffect(domain="financial_runway",  delta_base=0.3,  variance=0.3),
            ActionEffect(domain="skill_level",       delta_base=0.2,  variance=0.2),
            ActionEffect(domain="health_score",      delta_base=-0.2, variance=0.1),
        ],
        typical_duration_months=6,
    ),
    "reduce_work_hours": Action(
        id="reduce_work_hours",
        label="Reduce work hours",
        description="Cut back working hours to restore balance",
        effects=[
            ActionEffect(domain="health_score",      delta_base=1.5,  variance=0.4),
            ActionEffect(domain="relationship_depth", delta_base=1.0, variance=0.4),
            ActionEffect(domain="career_level",      delta_base=-0.8, variance=0.4),
            ActionEffect(domain="financial_runway",  delta_base=-0.5, variance=0.3),
        ],
        typical_duration_months=3,
    ),
    "start_side_project": Action(
        id="start_side_project",
        label="Start a side project",
        description="Launch a project outside of your main job",
        effects=[
            ActionEffect(domain="skill_level",       delta_base=1.2,  variance=0.6),
            ActionEffect(domain="career_level",      delta_base=0.6,  variance=0.5),
            ActionEffect(domain="financial_runway",  delta_base=0.5,  variance=1.0),
            ActionEffect(domain="health_score",      delta_base=-0.6, variance=0.3),
            ActionEffect(domain="relationship_depth", delta_base=-0.4, variance=0.2),
        ],
        typical_duration_months=12,
    ),
}


def get_action(action_id: str) -> Action:
    if action_id not in ACTION_REGISTRY:
        raise KeyError(f"Unknown action: {action_id!r}. Available: {list(ACTION_REGISTRY)}")
    return ACTION_REGISTRY[action_id]


def select_action_for_domain(domain: str) -> Action:
    """
    Return the action with the largest positive base delta for the given domain.
    Used by the engine to pick a fitting action when given a priority domain.
    """
    best: Action | None = None
    best_delta = float("-inf")
    for action in ACTION_REGISTRY.values():
        for effect in action.effects:
            if effect.domain == domain and effect.delta_base > best_delta:
                best_delta = effect.delta_base
                best = action
    if best is None:
        return ACTION_REGISTRY["invest_in_skills"]
    return best
