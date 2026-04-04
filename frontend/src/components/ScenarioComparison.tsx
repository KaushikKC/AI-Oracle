"use client"

import { useState } from "react"
import type { Scenario, ScenarioType } from "@/lib/types"

interface Props {
  scenarios: Scenario[]  // always 3: optimistic, baseline, conservative
}

const SCENARIO_META: Record<ScenarioType, { label: string; color: string; bg: string; badge: string }> = {
  optimistic:   { label: "Optimistic",   color: "#10b981", bg: "#10b98112", badge: "bg-green-900/60 text-green-300 border-green-700" },
  baseline:     { label: "Baseline",     color: "#6366f1", bg: "#6366f112", badge: "bg-indigo-900/60 text-indigo-300 border-indigo-700" },
  conservative: { label: "Conservative", color: "#f59e0b", bg: "#f59e0b12", badge: "bg-amber-900/60 text-amber-300 border-amber-700" },
}

const DOMAIN_LABELS: Record<string, string> = {
  career_level:       "Career",
  health_score:       "Health",
  financial_runway:   "Finance",
  relationship_depth: "Relations",
  skill_level:        "Skills",
}

const DOMAIN_COLORS: Record<string, string> = {
  career_level:       "#6366f1",
  health_score:       "#10b981",
  financial_runway:   "#f59e0b",
  relationship_depth: "#ec4899",
  skill_level:        "#8b5cf6",
}

function ConfidencePip({ value }: { value: number }) {
  const pct = Math.round(value * 100)
  const color = value >= 0.7 ? "#10b981" : value >= 0.5 ? "#f59e0b" : "#ef4444"
  return (
    <div className="flex items-center gap-2">
      <div className="relative h-1.5 flex-1 rounded-full bg-slate-700">
        <div
          className="absolute left-0 top-0 h-full rounded-full transition-all"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
      <span className="text-xs font-semibold tabular-nums" style={{ color }}>
        {pct}%
      </span>
    </div>
  )
}

function ScenarioCard({ scenario }: { scenario: Scenario }) {
  const [showAssumptions, setShowAssumptions] = useState(false)
  const meta = SCENARIO_META[scenario.scenario_type]

  return (
    <div
      className="flex flex-col rounded-xl border p-4 gap-4"
      style={{ borderColor: `${meta.color}44`, background: meta.bg }}
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <span
          className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold ${meta.badge}`}
        >
          {meta.label}
        </span>
        <span className="text-xs text-slate-400 uppercase tracking-wider">
          {scenario.time_horizon}
        </span>
      </div>

      {/* Confidence */}
      <div>
        <p className="text-xs text-slate-400 mb-1.5">Confidence</p>
        <ConfidencePip value={scenario.confidence} />
      </div>

      {/* Domain projections */}
      <div>
        <p className="text-xs text-slate-400 mb-2">Domain Projections</p>
        <div className="space-y-2">
          {scenario.domain_projections.map((dp) => {
            const color = DOMAIN_COLORS[dp.domain] ?? "#64748b"
            const isPos = dp.delta >= 0
            return (
              <div key={dp.domain} className="flex items-center gap-2">
                <span
                  className="w-16 text-xs font-medium shrink-0"
                  style={{ color }}
                >
                  {DOMAIN_LABELS[dp.domain] ?? dp.domain}
                </span>

                {/* Bar: current (ghost) + projected (filled) */}
                <div className="relative flex-1 h-2 rounded-full bg-slate-700">
                  <div
                    className="absolute left-0 top-0 h-full rounded-full opacity-30"
                    style={{ width: `${dp.current_score * 10}%`, background: color }}
                  />
                  <div
                    className="absolute left-0 top-0 h-full rounded-full"
                    style={{ width: `${dp.projected_score * 10}%`, background: color }}
                  />
                </div>

                {/* Delta badge */}
                <span
                  className={`w-12 text-right text-xs font-semibold tabular-nums ${
                    isPos ? "text-green-400" : "text-red-400"
                  }`}
                >
                  {isPos ? "+" : ""}
                  {dp.delta.toFixed(2)}
                </span>

                {/* Arrow */}
                <span className={`text-xs ${isPos ? "text-green-400" : "text-red-400"}`}>
                  {isPos ? "↑" : "↓"}
                </span>
              </div>
            )
          })}
        </div>
      </div>

      {/* Assumptions (collapsible) */}
      <div>
        <button
          type="button"
          onClick={() => setShowAssumptions((v) => !v)}
          className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200 transition-colors"
        >
          <svg
            className={`h-3 w-3 transition-transform ${showAssumptions ? "rotate-90" : ""}`}
            viewBox="0 0 12 12"
            fill="none"
          >
            <path d="M4 2l4 4-4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
          {scenario.assumptions.length} assumption{scenario.assumptions.length !== 1 ? "s" : ""}
        </button>
        {showAssumptions && (
          <ul className="mt-2 space-y-1.5">
            {scenario.assumptions.map((a, i) => (
              <li key={i} className="flex gap-2 text-xs text-slate-300 leading-snug">
                <span className="mt-0.5 shrink-0 text-slate-500">—</span>
                {a}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

export function ScenarioComparison({ scenarios }: Props) {
  const ordered = ["optimistic", "baseline", "conservative"] as ScenarioType[]
  const sorted  = ordered.map((t) => scenarios.find((s) => s.scenario_type === t)!)

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {sorted.map((s) => (
        <ScenarioCard key={s.scenario_type} scenario={s} />
      ))}
    </div>
  )
}
