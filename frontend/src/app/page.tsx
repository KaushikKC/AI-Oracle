"use client"

import { useState } from "react"
import useSWR from "swr"
import {
  buildProfile,
  getActions,
  getEvents,
  getProfile,
  runSimulation,
  seedEvents,
} from "@/lib/api"
import type { SimulateRequest, SimulationResult } from "@/lib/types"
import { EventTimeline } from "@/components/EventTimeline"
import { SimulationForm } from "@/components/SimulationForm"
import { ScenarioComparison } from "@/components/ScenarioComparison"
import { DomainRadarChart } from "@/components/DomainRadarChart"

const DOMAIN_LABELS: Record<string, string> = {
  career: "Career", health: "Health", finances: "Finance",
  relationships: "Relations", skills: "Skills", other: "Other",
}

const DOMAIN_COLORS: Record<string, string> = {
  career: "#6366f1", health: "#10b981", finances: "#f59e0b",
  relationships: "#ec4899", skills: "#8b5cf6", other: "#6b7280",
}

export default function Home() {
  const { data: events, mutate: refetchEvents, isLoading: eventsLoading } =
    useSWR("events", () => getEvents(200))

  const { data: profileSnap, mutate: refetchProfile } =
    useSWR("profile", getProfile)

  const { data: actions } =
    useSWR("actions", getActions)

  const [result, setResult]       = useState<SimulationResult | null>(null)
  const [simLoading, setSimLoading] = useState(false)
  const [seeding, setSeeding]     = useState(false)
  const [building, setBuilding]   = useState(false)

  async function handleSeed() {
    setSeeding(true)
    try {
      await seedEvents(50)
      await refetchEvents()
    } finally {
      setSeeding(false)
    }
  }

  async function handleBuildProfile() {
    setBuilding(true)
    try {
      await buildProfile()
      await refetchProfile()
    } finally {
      setBuilding(false)
    }
  }

  async function handleSimulate(req: SimulateRequest) {
    setSimLoading(true)
    try {
      const r = await runSimulation(req)
      setResult(r)
      // Profile may have been auto-built by the backend
      await refetchProfile()
    } finally {
      setSimLoading(false)
    }
  }

  const profile = profileSnap?.profile

  return (
    <main className="min-h-screen px-4 py-8 max-w-7xl mx-auto">
      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-slate-100 tracking-tight">
            UserLife
          </h1>
          <p className="text-sm text-slate-400 mt-0.5">
            Temporal Life Simulation Engine
          </p>
        </div>

        <div className="flex gap-2">
          <button
            onClick={handleSeed}
            disabled={seeding}
            className="rounded-lg border border-slate-600 bg-slate-800 px-4 py-2 text-sm font-medium text-slate-300 hover:border-slate-400 hover:text-slate-100 disabled:opacity-50 transition-colors"
          >
            {seeding ? "Seeding…" : "Seed 50 Events"}
          </button>
          <button
            onClick={handleBuildProfile}
            disabled={building || !events?.length}
            className="rounded-lg border border-indigo-700 bg-indigo-900/40 px-4 py-2 text-sm font-medium text-indigo-300 hover:bg-indigo-900 disabled:opacity-50 transition-colors"
          >
            {building ? "Building…" : "Build Profile"}
          </button>
        </div>
      </div>

      {/* ── Timeline ────────────────────────────────────────────────────── */}
      <section className="mb-8 rounded-xl border border-slate-700 bg-slate-900 p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
            Event Timeline
          </h2>
          {events && (
            <span className="text-xs text-slate-500">
              {events.length} event{events.length !== 1 ? "s" : ""}
            </span>
          )}
        </div>
        {eventsLoading ? (
          <div className="flex items-center justify-center h-36 text-sm text-slate-500">
            Loading events…
          </div>
        ) : (
          <EventTimeline events={events ?? []} />
        )}
      </section>

      {/* ── Profile + Simulation Form ────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">

        {/* Profile summary */}
        <section className="rounded-xl border border-slate-700 bg-slate-900 p-5">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400 mb-4">
            Current Profile
          </h2>
          {!profile ? (
            <div className="text-sm text-slate-500">
              No profile yet. Click "Build Profile" after seeding events.
            </div>
          ) : (
            <div className="space-y-4">
              {/* Risk & consistency */}
              <div className="grid grid-cols-2 gap-3">
                {[
                  { label: "Risk Tolerance", value: profile.risk_tolerance },
                  { label: "Consistency",    value: profile.consistency },
                ].map(({ label, value }) => (
                  <div key={label} className="rounded-lg border border-slate-700 bg-slate-800 p-3">
                    <p className="text-xs text-slate-400 mb-1">{label}</p>
                    <p className="text-xl font-bold text-slate-100">
                      {Math.round(value * 100)}
                      <span className="text-sm font-normal text-slate-400">%</span>
                    </p>
                    <div className="mt-1.5 h-1 rounded-full bg-slate-700">
                      <div
                        className="h-full rounded-full bg-indigo-500"
                        style={{ width: `${value * 100}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>

              {/* Priorities */}
              <div>
                <p className="text-xs text-slate-400 mb-2">Domain Priorities</p>
                <div className="space-y-1.5">
                  {Object.entries(profile.priorities)
                    .filter(([k]) => k !== "other")
                    .sort(([, a], [, b]) => b - a)
                    .map(([domain, weight]) => (
                      <div key={domain} className="flex items-center gap-2">
                        <span
                          className="w-20 text-xs font-medium shrink-0"
                          style={{ color: DOMAIN_COLORS[domain] ?? "#64748b" }}
                        >
                          {DOMAIN_LABELS[domain] ?? domain}
                        </span>
                        <div className="relative flex-1 h-1.5 rounded-full bg-slate-700">
                          <div
                            className="absolute left-0 top-0 h-full rounded-full"
                            style={{
                              width: `${weight * 100}%`,
                              background: DOMAIN_COLORS[domain] ?? "#64748b",
                            }}
                          />
                        </div>
                        <span className="text-xs text-slate-400 tabular-nums w-8 text-right">
                          {Math.round(weight * 100)}%
                        </span>
                      </div>
                    ))}
                </div>
              </div>

              <p className="text-xs text-slate-500">
                {profile.event_count} events · v{profileSnap?.version}
              </p>
            </div>
          )}
        </section>

        {/* Simulation form */}
        <section className="rounded-xl border border-slate-700 bg-slate-900 p-5">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400 mb-4">
            Run Simulation
          </h2>
          {!actions?.length ? (
            <div className="text-sm text-slate-500">Loading actions…</div>
          ) : (
            <SimulationForm
              actions={actions}
              onSubmit={handleSimulate}
              loading={simLoading}
            />
          )}
        </section>
      </div>

      {/* ── Results ─────────────────────────────────────────────────────── */}
      {result && (
        <div className="space-y-6">
          {/* Section header */}
          <div className="flex items-center gap-3">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
              Simulation Results
            </h2>
            <span className="text-xs text-slate-500">
              "{result.action.label}" · {result.scenarios[0]?.time_horizon}
            </span>
            <span className="ml-auto text-xs text-slate-600">
              {new Date(result.generated_at).toLocaleTimeString()}
            </span>
          </div>

          {/* 3 scenario cards */}
          <ScenarioComparison scenarios={result.scenarios} />

          {/* Radar + diff table */}
          <section className="rounded-xl border border-slate-700 bg-slate-900 p-5">
            <DomainRadarChart result={result} />
          </section>
        </div>
      )}
    </main>
  )
}
