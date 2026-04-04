"use client"

import { useState } from "react"
import type { ActionInfo, SimulateRequest, TimeHorizon } from "@/lib/types"

interface Props {
  actions: ActionInfo[]
  onSubmit: (req: SimulateRequest) => Promise<void>
  loading: boolean
}

const HORIZONS: { value: TimeHorizon; label: string }[] = [
  { value: "6mo", label: "6 months" },
  { value: "1yr", label: "1 year" },
  { value: "3yr", label: "3 years" },
]

const DOMAIN_LABELS: Record<string, string> = {
  career_level:      "Career",
  health_score:      "Health",
  financial_runway:  "Finance",
  relationship_depth: "Relations",
  skill_level:       "Skills",
}

const DOMAIN_COLORS: Record<string, string> = {
  career_level:      "#6366f1",
  health_score:      "#10b981",
  financial_runway:  "#f59e0b",
  relationship_depth: "#ec4899",
  skill_level:       "#8b5cf6",
}

export function SimulationForm({ actions, onSubmit, loading }: Props) {
  const [actionId, setActionId]   = useState(actions[0]?.id ?? "")
  const [horizon, setHorizon]     = useState<TimeHorizon>("1yr")
  const [error, setError]         = useState<string | null>(null)

  const selectedAction = actions.find((a) => a.id === actionId)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    try {
      await onSubmit({ action_id: actionId, time_horizon: horizon })
    } catch (err) {
      setError(String(err))
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      {/* Action selector */}
      <div>
        <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
          Action
        </label>
        <select
          value={actionId}
          onChange={(e) => setActionId(e.target.value)}
          className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2.5 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500"
        >
          {actions.map((a) => (
            <option key={a.id} value={a.id}>
              {a.label}
            </option>
          ))}
        </select>

        {selectedAction && (
          <div className="mt-2 space-y-1">
            <p className="text-xs text-slate-400">{selectedAction.description}</p>
            <div className="flex flex-wrap gap-1.5 mt-1">
              {selectedAction.primary_domains.map((d) => (
                <span
                  key={d}
                  className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium"
                  style={{
                    background: `${DOMAIN_COLORS[d] ?? "#64748b"}22`,
                    color: DOMAIN_COLORS[d] ?? "#64748b",
                    border: `1px solid ${DOMAIN_COLORS[d] ?? "#64748b"}44`,
                  }}
                >
                  {DOMAIN_LABELS[d] ?? d}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Time horizon */}
      <div>
        <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
          Time Horizon
        </label>
        <div className="flex gap-2">
          {HORIZONS.map(({ value, label }) => (
            <button
              key={value}
              type="button"
              onClick={() => setHorizon(value)}
              className={`flex-1 rounded-lg border px-3 py-2 text-sm font-medium transition-colors ${
                horizon === value
                  ? "border-indigo-500 bg-indigo-500/20 text-indigo-300"
                  : "border-slate-700 bg-slate-800 text-slate-400 hover:border-slate-500"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <p className="rounded-lg border border-red-800 bg-red-950 px-3 py-2 text-xs text-red-300">
          {error}
        </p>
      )}

      <button
        type="submit"
        disabled={loading || !actionId}
        className="w-full rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {loading ? (
          <span className="flex items-center justify-center gap-2">
            <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
            </svg>
            Simulating…
          </span>
        ) : (
          "Run Simulation"
        )}
      </button>
    </form>
  )
}
