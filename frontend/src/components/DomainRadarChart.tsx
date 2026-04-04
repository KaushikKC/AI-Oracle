"use client"

import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  ResponsiveContainer,
  Legend,
  Tooltip,
} from "recharts"
import type { SimulationResult } from "@/lib/types"

interface Props {
  result: SimulationResult
}

const LIFE_DOMAINS = [
  "career_level",
  "health_score",
  "financial_runway",
  "relationship_depth",
  "skill_level",
] as const

const DOMAIN_LABELS: Record<string, string> = {
  career_level:       "Career",
  health_score:       "Health",
  financial_runway:   "Finance",
  relationship_depth: "Relations",
  skill_level:        "Skills",
}

const SCENARIO_COLORS = {
  optimistic:   "#10b981",
  baseline:     "#6366f1",
  conservative: "#f59e0b",
}

interface RadarRow {
  subject: string
  optimistic: number
  baseline: number
  conservative: number
  current: number
}

function buildRadarData(result: SimulationResult): RadarRow[] {
  const ls = result.life_state

  // Build a lookup: scenario_type → domain → projected_score
  const lookup: Record<string, Record<string, number>> = {}
  for (const scenario of result.scenarios) {
    lookup[scenario.scenario_type] = {}
    for (const dp of scenario.domain_projections) {
      lookup[scenario.scenario_type][dp.domain] = dp.projected_score
    }
  }

  return LIFE_DOMAINS.map((domain) => {
    const currentScore = ls[domain]
    return {
      subject: DOMAIN_LABELS[domain],
      current:      currentScore,
      optimistic:   lookup["optimistic"]?.[domain]   ?? currentScore,
      baseline:     lookup["baseline"]?.[domain]     ?? currentScore,
      conservative: lookup["conservative"]?.[domain] ?? currentScore,
    }
  })
}

export function DomainRadarChart({ result }: Props) {
  const data = buildRadarData(result)

  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3">
        Domain Score Projections
      </p>

      <div className="flex gap-6 flex-col lg:flex-row">
        {/* Radar */}
        <div className="flex-1 min-h-[280px]">
          <ResponsiveContainer width="100%" height={280}>
            <RadarChart data={data} margin={{ top: 10, right: 20, bottom: 10, left: 20 }}>
              <PolarGrid stroke="#2a3347" />
              <PolarAngleAxis
                dataKey="subject"
                tick={{ fill: "#94a3b8", fontSize: 12, fontWeight: 500 }}
              />

              {/* Current state (ghost) */}
              <Radar
                name="Current"
                dataKey="current"
                stroke="#475569"
                fill="#475569"
                fillOpacity={0.10}
                strokeWidth={1}
                strokeDasharray="4 2"
              />

              <Radar
                name="Optimistic"
                dataKey="optimistic"
                stroke={SCENARIO_COLORS.optimistic}
                fill={SCENARIO_COLORS.optimistic}
                fillOpacity={0.12}
                strokeWidth={2}
              />
              <Radar
                name="Baseline"
                dataKey="baseline"
                stroke={SCENARIO_COLORS.baseline}
                fill={SCENARIO_COLORS.baseline}
                fillOpacity={0.12}
                strokeWidth={2}
              />
              <Radar
                name="Conservative"
                dataKey="conservative"
                stroke={SCENARIO_COLORS.conservative}
                fill={SCENARIO_COLORS.conservative}
                fillOpacity={0.12}
                strokeWidth={2}
              />

              <Legend
                wrapperStyle={{ fontSize: 12, color: "#94a3b8" }}
              />
              <Tooltip
                contentStyle={{
                  background: "#1e2636",
                  border: "1px solid #2a3347",
                  borderRadius: 8,
                  color: "#e2e8f0",
                  fontSize: 12,
                }}
                formatter={(value: number) => value.toFixed(2)}
              />
            </RadarChart>
          </ResponsiveContainer>
        </div>

        {/* Numeric diff table */}
        <div className="lg:w-64">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-slate-500 border-b border-slate-700">
                <th className="text-left pb-2 font-medium">Domain</th>
                <th className="text-right pb-2 font-medium">Now</th>
                <th className="text-right pb-2 font-medium" style={{ color: SCENARIO_COLORS.optimistic }}>Opt</th>
                <th className="text-right pb-2 font-medium" style={{ color: SCENARIO_COLORS.baseline }}>Base</th>
                <th className="text-right pb-2 font-medium" style={{ color: SCENARIO_COLORS.conservative }}>Cons</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {data.map((row) => (
                <tr key={row.subject}>
                  <td className="py-1.5 text-slate-300 font-medium">{row.subject}</td>
                  <td className="py-1.5 text-right text-slate-400">{row.current.toFixed(1)}</td>
                  <td className="py-1.5 text-right" style={{ color: SCENARIO_COLORS.optimistic }}>
                    {row.optimistic.toFixed(1)}
                  </td>
                  <td className="py-1.5 text-right" style={{ color: SCENARIO_COLORS.baseline }}>
                    {row.baseline.toFixed(1)}
                  </td>
                  <td className="py-1.5 text-right" style={{ color: SCENARIO_COLORS.conservative }}>
                    {row.conservative.toFixed(1)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
