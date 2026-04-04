// Mirrors the Pydantic models from the FastAPI backend exactly.

export type EventCategory =
  | "career"
  | "health"
  | "finances"
  | "relationships"
  | "skills"
  | "other"

export interface LifeEvent {
  id: number | null
  timestamp: string
  category: EventCategory
  sentiment: number       // −1 to +1
  importance_score: number // 0 to 1
  description: string
  source_raw: string | null
}

export interface UserProfile {
  risk_tolerance: number
  consistency: number
  priorities: Record<string, number>
  avg_sentiment_by_domain: Record<string, number>
  activity_density: Record<string, number>
  event_count: number
  computed_at: string
}

export interface ProfileSnapshot {
  id: number | null
  version: number
  profile: UserProfile
  created_at: string
}

export interface LifeState {
  career_level: number
  health_score: number
  financial_runway: number
  relationship_depth: number
  skill_level: number
  as_of: string
}

export type TimeHorizon = "6mo" | "1yr" | "3yr"
export type ScenarioType = "optimistic" | "baseline" | "conservative"

export interface ActionInfo {
  id: string
  label: string
  description: string
  typical_duration_months: number
  primary_domains: string[]
}

export interface DomainProjection {
  domain: string
  current_score: number
  projected_score: number
  delta: number
}

export interface Scenario {
  scenario_type: ScenarioType
  time_horizon: TimeHorizon
  action: ActionFull
  domain_projections: DomainProjection[]
  confidence: number
  assumptions: string[]
}

// Full action shape returned inside SimulationResult
export interface ActionFull {
  id: string
  label: string
  description: string
  typical_duration_months: number
  effects: Array<{
    domain: string
    delta_base: number
    variance: number
  }>
}

export interface SimulationResult {
  generated_at: string
  life_state: LifeState
  action: ActionFull
  scenarios: Scenario[]   // always exactly 3
}

export interface SimulateRequest {
  action_id: string
  time_horizon: TimeHorizon
}
