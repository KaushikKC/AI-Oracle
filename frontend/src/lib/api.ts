import type {
  ActionInfo,
  LifeEvent,
  ProfileSnapshot,
  SimulateRequest,
  SimulationResult,
} from "./types"

// Uses Next.js rewrites: /api/* → http://localhost:8000/*
const BASE = "/api"

async function json<T>(input: RequestInfo, init?: RequestInit): Promise<T> {
  const res = await fetch(input, init)
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(`${res.status} ${res.url}: ${text}`)
  }
  return res.json() as Promise<T>
}

// ── Events ────────────────────────────────────────────────────────────────────

export function getEvents(limit = 200): Promise<LifeEvent[]> {
  return json<LifeEvent[]>(`${BASE}/events?limit=${limit}`)
}

export function seedEvents(n = 50): Promise<LifeEvent[]> {
  return json<LifeEvent[]>(`${BASE}/events/seed?n=${n}`, { method: "POST" })
}

// ── Profile ───────────────────────────────────────────────────────────────────

export function getProfile(): Promise<ProfileSnapshot | null> {
  return json<ProfileSnapshot>(`${BASE}/profile/latest`).catch((err) => {
    // 404 = no profile yet — that's fine
    if (String(err).includes("404")) return null
    throw err
  })
}

export function buildProfile(): Promise<ProfileSnapshot> {
  return json<ProfileSnapshot>(`${BASE}/profile/build`, { method: "POST" })
}

// ── Simulation ────────────────────────────────────────────────────────────────

export function getActions(): Promise<ActionInfo[]> {
  return json<ActionInfo[]>(`${BASE}/simulate/actions`)
}

export function runSimulation(req: SimulateRequest): Promise<SimulationResult> {
  return json<SimulationResult>(`${BASE}/simulate/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  })
}
