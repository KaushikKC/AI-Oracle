# UserLife — Temporal Life Simulation Engine

> **"Turn your life history into structured foresight — ingest events, build a behavioral profile, and simulate where your choices lead across career, health, finances, relationships, and skills."**

---

## What Is This?

UserLife is a personal life simulation engine. It ingests structured or unstructured data about your life events, builds a behavioral profile from your patterns, then runs a branching simulation engine that projects what happens to five life domains under three scenarios — optimistic, baseline, and conservative — across a chosen time horizon.

No journaling app. No AI therapist. No dashboard of vanity metrics. This is a **structured reasoning tool**: given who you are and where you are, what do your choices actually produce?

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Frontend  ·  Next.js 14  ·  localhost:3000                     │
│  D3 Timeline · Radar Chart · Scenario Comparison · Query Form   │
└────────────────────────┬────────────────────────────────────────┘
                         │  /api/* → rewrite
┌────────────────────────▼────────────────────────────────────────┐
│  Backend  ·  FastAPI  ·  localhost:8000                         │
│                                                                  │
│  /ingest/*     Phase 1 — Event Ingestion (text + structured)    │
│  /memory/*     Phase 2 — Memory System (episodic/semantic/time) │
│  /profile/*    Phase 3 — Behavioral Profile Snapshots           │
│  /events/*     Phase 5 — Event Listing + Seed                   │
│  /simulate/*   Phase 4+5 — Branching Simulation Engine          │
└──────────┬──────────────────────────┬───────────────────────────┘
           │                          │
  ┌────────▼────────┐      ┌──────────▼──────────┐
  │  SQLite          │      │  ChromaDB            │
  │  events          │      │  Vector embeddings   │
  │  profile_snap.   │      │  (semantic search)   │
  └─────────────────┘      └─────────────────────┘
           │
  ┌────────▼────────────────────────┐
  │  LLM  (switchable)              │
  │  Ollama  →  llama3              │
  │  OpenAI  →  gpt-4o-mini         │
  │  Embed  →  nomic / text-embed   │
  └─────────────────────────────────┘
```

---

## Phase Overview

| Phase | What it does |
|---|---|
| **1 — Ingestion** | Accept life events as JSON, CSV, or raw prose. LLM parses prose into structured events with category, sentiment, and importance score. |
| **2 — Memory** | Three-layer memory: episodic (semantic similarity search via ChromaDB), semantic (LLM pattern extraction), temporal (time-window queries). |
| **3 — Profile** | Build a `UserProfile` from event history using Welford's online algorithm for incremental updates — risk tolerance, consistency, domain priorities, sentiment per domain, activity density. |
| **4 — Simulation** | Pure deterministic engine: `f(LifeState, Action, UserProfile) → 3 Scenarios`. No LLM. Profile constraints modulate variance. Each scenario has domain projections, a confidence score, and explicit assumptions. |
| **5 — Interface** | Next.js frontend with D3 swimlane timeline, simulation form, side-by-side scenario comparison, and Recharts radar chart. |

---

## Quickstart

### Prerequisites

- Python 3.11+
- Node.js 20+
- [Ollama](https://ollama.ai) running locally (or an OpenAI API key)

### 1. Clone and set up the backend

```bash
git clone https://github.com/KaushikKC/Foretrace.git
cd Foretrace

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

```env
# LLM provider: "ollama" or "openai"
LLM_PROVIDER=ollama
EMBED_PROVIDER=ollama

# Ollama (local)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3
OLLAMA_EMBED_MODEL=nomic-embed-text

# OpenAI (if LLM_PROVIDER=openai)
OPENAI_API_KEY=sk-...

# Database
DATABASE_URL=sqlite:///./userlife.db
```

Pull Ollama models (if using Ollama):

```bash
ollama pull llama3
ollama pull nomic-embed-text
```

### 3. Start the backend

```bash
uvicorn app.main:app --reload --port 8000
```

API docs available at `http://localhost:8000/docs`.

### 4. Set up and start the frontend

```bash
cd frontend
npm install
npm run dev          # http://localhost:3000
```

### 5. Test the full flow

1. Open `http://localhost:3000`
2. Click **"Seed 50 Events"** — populates the database with 50 realistic test events
3. Click **"Build Profile"** — computes your behavioral profile from event history
4. Select an action (e.g. "Take a new job") and a time horizon
5. Click **"Run Simulation"** — produces 3 scenario branches with domain projections

---

## Running Tests

```bash
# All tests (243 total)
pytest

# With coverage
pytest --cov=app --cov-report=term-missing

# Specific phase
pytest tests/test_simulation.py -v       # Phase 4: simulation engine
pytest tests/test_profile_calculator.py  # Phase 3: profile computation
pytest tests/test_memory_retriever.py    # Phase 2: memory system
```

---

## API Reference

### Events

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/events` | List events. Params: `category`, `limit`, `offset` |
| `POST` | `/events/seed` | Insert n test events. Param: `n` (default 50) |

### Ingestion

| Method | Endpoint | Body | Description |
|---|---|---|---|
| `POST` | `/ingest/structured` | `{payload, source_format}` | Ingest JSON or CSV event data |
| `POST` | `/ingest/text` | `{text, hint_timestamp?}` | LLM parses prose → structured events |

**Structured ingestion example:**
```json
POST /ingest/structured
{
  "source_format": "json",
  "payload": [
    {
      "timestamp": "2025-11-15T09:00:00Z",
      "category": "career",
      "sentiment": 0.8,
      "importance_score": 0.9,
      "description": "Received a promotion to senior engineer"
    }
  ]
}
```

**Text ingestion example:**
```json
POST /ingest/text
{
  "text": "Last Tuesday I had a rough performance review. My manager said my communication has been poor lately which really stressed me out. I've been putting in 60-hour weeks too.",
  "hint_timestamp": "2025-12-01T00:00:00Z"
}
```

### Memory

| Method | Endpoint | Body | Description |
|---|---|---|---|
| `POST` | `/memory/query` | `{query, n_results, include_semantic}` | Query episodic + semantic + temporal memory |

**Example:**
```json
POST /memory/query
{
  "query": "career decisions in the last 6 months",
  "n_results": 10,
  "include_semantic": true
}
```

Returns:
```json
{
  "query": "career decisions in the last 6 months",
  "episodic": [
    {
      "event": { "id": 12, "category": "career", "sentiment": 0.8, ... },
      "relevance_score": 0.91
    }
  ],
  "semantic": [
    {
      "pattern": "User consistently takes high-stakes career risks with positive outcomes",
      "supporting_event_ids": [12, 7, 3],
      "confidence": 0.84
    }
  ],
  "temporal": {
    "window_days": 180,
    "start": "2025-06-04T00:00:00Z",
    "end": "2025-12-04T00:00:00Z",
    "events": [...]
  }
}
```

### Profile

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/profile/build` | Full rebuild from all events (creates new snapshot version) |
| `POST` | `/profile/update` | Incremental update — processes only new events since last snapshot |
| `GET` | `/profile/latest` | Return the most recent `ProfileSnapshot` |
| `GET` | `/profile/history` | All snapshots in chronological order |
| `GET` | `/profile/{version}` | Snapshot by version number |

**ProfileSnapshot response:**
```json
{
  "id": 3,
  "version": 3,
  "created_at": "2025-12-15T10:22:00Z",
  "profile": {
    "risk_tolerance": 0.72,
    "consistency": 0.65,
    "priorities": {
      "career": 0.31, "health": 0.22, "finances": 0.18,
      "relationships": 0.14, "skills": 0.12, "other": 0.03
    },
    "avg_sentiment_by_domain": {
      "career": 0.41, "health": 0.12, "finances": -0.08,
      "relationships": 0.34, "skills": 0.55, "other": 0.00
    },
    "activity_density": {
      "career": 3.2, "health": 2.1, "finances": 1.8,
      "relationships": 1.4, "skills": 2.6, "other": 0.3
    },
    "event_count": 50,
    "computed_at": "2025-12-15T10:22:00Z"
  }
}
```

**Profile variables explained:**

| Variable | Range | Meaning |
|---|---|---|
| `risk_tolerance` | 0–1 | Mean normalized sentiment on high-importance (≥ 0.5) career/finance events. 0 = risk-averse, 1 = risk-seeking |
| `consistency` | 0–1 | `1 − population_std_dev(all sentiments)`. 1 = perfectly consistent emotional tone |
| `priorities` | dict, sums to 1 | Relative share of `sum(importance_score)` per domain |
| `avg_sentiment_by_domain` | −1 to +1 | Mean sentiment per domain |
| `activity_density` | events/30d | Event count per domain ÷ (time_span_days / 30) |

### Simulation

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/simulate/actions` | List all 8 registered actions with effect summaries |
| `POST` | `/simulate/run` | Run the branching engine; returns 3 scenario branches |

**Simulate request:**
```json
POST /simulate/run
{
  "action_id": "take_new_job",
  "time_horizon": "1yr"
}
```

Supported `time_horizon` values: `"6mo"` · `"1yr"` · `"3yr"`

**SimulationResult response:**
```json
{
  "generated_at": "2025-12-15T10:30:00Z",
  "life_state": {
    "career_level": 7.05,
    "health_score": 5.6,
    "financial_runway": 5.0,
    "relationship_depth": 6.5,
    "skill_level": 7.5
  },
  "action": { "id": "take_new_job", "label": "Take a new job", ... },
  "scenarios": [
    {
      "scenario_type": "optimistic",
      "time_horizon": "1yr",
      "confidence": 0.67,
      "domain_projections": [
        { "domain": "career_level", "current_score": 7.05, "projected_score": 9.34, "delta": 2.29 },
        { "domain": "financial_runway", "current_score": 5.0, "projected_score": 7.08, "delta": 2.08 },
        { "domain": "relationship_depth", "current_score": 6.5, "projected_score": 5.45, "delta": -1.05 }
      ],
      "assumptions": [
        "User sustains high motivation and follows through on the action without major setbacks.",
        "Risk tolerance is high (0.72); variance swings are amplified.",
        "Trade-off accepted: relationship_depth expected to decline (−0.5 base); monitored and recoverable."
      ]
    },
    { "scenario_type": "baseline", ... },
    { "scenario_type": "conservative", ... }
  ]
}
```

---

## Available Actions

| Action ID | Label | Primary Domains |
|---|---|---|
| `take_new_job` | Take a new job | career, finances, skills |
| `start_exercise_routine` | Start exercise routine | health, career |
| `reduce_social_commitments` | Reduce social commitments | skills, health, career |
| `seek_promotion` | Seek a promotion | career, finances, skills |
| `invest_in_skills` | Invest in skills | skills, career |
| `build_relationships` | Build relationships | relationships, career |
| `reduce_work_hours` | Reduce work hours | health, relationships |
| `start_side_project` | Start a side project | skills, career, finances |

---

## Data Model

### Event

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | int | auto | Primary key |
| `timestamp` | datetime | required | When this event occurred |
| `category` | enum | career/health/finances/relationships/skills/other | Life domain |
| `sentiment` | float | −1.0 to +1.0 | Emotional tone (negative to positive) |
| `importance_score` | float | 0.0 to 1.0 | How significant this event felt |
| `description` | str | min 1 char | Human-readable description |
| `source_raw` | str? | optional | Original raw input text |

### LifeState

| Field | Type | Range | Description |
|---|---|---|---|
| `career_level` | float | 0–10 | Job seniority and career trajectory |
| `health_score` | float | 0–10 | Physical and mental health |
| `financial_runway` | float | 0–10 | Financial security and comfort |
| `relationship_depth` | float | 0–10 | Quality of social/personal connections |
| `skill_level` | float | 0–10 | Competence and expertise |

`LifeState` is automatically derived from your `UserProfile` via:
```
score = (avg_sentiment[domain] + 1) / 2 × 10
```

---

## Simulation Engine Design

### TransitionFunction

```
f(state, action, profile, scenario_type, time_horizon) → projections
```

For each domain effect in the action:

```
priority_amp  = 1.0 + (priority_weight − 1/6) × 3.0   [clamped 0.5–2.0]
base          = delta_base × priority_amp

optimistic:    delta = base + variance × risk_tolerance
baseline:      delta = base
conservative:  delta = base − variance × (1 − risk_tolerance)

final_delta   = delta × horizon_scale    [1.0 / 1.6 / 2.8]
projected     = clamp(current + final_delta, 0, 10)
```

**What each profile variable does in the simulation:**

| Profile variable | Effect on simulation |
|---|---|
| `risk_tolerance` | Scales variance — high tolerance amplifies upside (optimistic) and reduces downside penalty (conservative) |
| `priorities` | Amplifies base delta for high-priority domains — you invest more effort where you care most |
| `consistency` | Informs the confidence score — stable behavioral patterns → more predictable outcomes |

### Confidence Score Heuristic

```
base      = 0.60 (optimistic) | 0.75 (baseline) | 0.70 (conservative)
+0.08     if consistency > 0.7
−0.05     if consistency < 0.3
+0.07     if action's primary domain is in your top-3 priorities
−0.05     if action's primary domain is outside your top-3
−0.00/0.05/0.15  for 6mo/1yr/3yr horizon decay
→ clipped to [0.10, 0.95]
```

> **Note:** Confidence is a heuristic, not a calibrated probability. A 75% confidence score does not mean the baseline scenario will materialize 75% of the time. It represents relative trustworthiness given available behavioral data.

---

## Frontend Components

### EventTimeline

D3 swimlane chart with one lane per category. Each event is rendered as a circle:
- **Radius** — scales with `importance_score` (3.5px minimum, 9px maximum)
- **Fill opacity** — scales with `|sentiment|` (vivid = strong feeling, faded = neutral)
- **Stroke color** — green (sentiment > +0.2), red (< −0.2), gray (neutral)
- **Hover** — tooltip with description, date, exact sentiment, and importance

### ScenarioComparison

Three cards side by side, one per scenario type. Each card contains:
- Confidence bar with color-coded percentage
- Per-domain projection bars: ghost bar = current score, solid bar = projected
- Delta value with ± sign and directional arrow
- Collapsible assumptions list

### DomainRadarChart

Recharts `RadarChart` with four overlapping polygons: current state (dashed ghost) + optimistic, baseline, and conservative projections. Companion numeric table shows exact scores per domain per scenario.

---

## Project Structure

```
UserLife/
├── app/
│   ├── main.py                   # FastAPI app, CORS, router registration
│   ├── config.py                 # Pydantic settings from .env
│   ├── db/
│   │   ├── database.py           # SQLAlchemy engine + session factory
│   │   └── orm_models.py         # EventORM, ProfileSnapshotORM
│   ├── models/
│   │   ├── event.py              # Event, EventCategory
│   │   ├── ingestion.py          # IngestionRequest/Response
│   │   ├── memory.py             # EpisodicResult, SemanticPattern, MemoryResult
│   │   ├── profile.py            # UserProfile, ProfileSnapshot
│   │   └── simulation.py         # LifeState, Action, Scenario, SimulationResult
│   ├── ingestion/
│   │   ├── router.py             # POST /ingest/structured, /ingest/text
│   │   ├── service.py            # Ingestion orchestration
│   │   ├── validators.py         # validate_and_clamp()
│   │   └── parsers/
│   │       ├── base.py           # Parser interface
│   │       ├── structured_parser.py  # JSON + CSV parsing
│   │       └── text_parser.py    # LLM-based prose parsing
│   ├── memory/
│   │   ├── router.py             # POST /memory/query
│   │   ├── retriever.py          # Orchestrates episodic + semantic + temporal
│   │   ├── episodic.py           # Semantic similarity via ChromaDB
│   │   ├── semantic.py           # LLM pattern extraction
│   │   ├── temporal.py           # Time-window event queries
│   │   ├── embedder.py           # Embedding generation (Ollama or OpenAI)
│   │   └── vector_store.py       # ChromaDB wrapper
│   ├── profile/
│   │   ├── router.py             # POST /profile/build|update, GET /profile/*
│   │   ├── builder.py            # Full build + incremental update
│   │   ├── calculator.py         # Pure computation functions
│   │   ├── state.py              # ProfileState, Welford accumulators
│   │   └── repository.py         # Snapshot persistence
│   ├── storage/
│   │   ├── event_repository.py   # Event CRUD
│   │   └── router.py             # GET /events, POST /events/seed
│   ├── simulation/
│   │   ├── router.py             # GET /simulate/actions, POST /simulate/run
│   │   ├── engine.py             # BranchingEngine
│   │   ├── transition.py         # TransitionFunction, confidence, assumptions
│   │   └── actions.py            # Action registry (8 actions)
│   └── llm/
│       ├── client.py             # LLM client interface
│       ├── ollama_client.py      # Ollama implementation
│       ├── openai_client.py      # OpenAI implementation
│       └── prompts.py            # Prompt templates
├── tests/
│   ├── conftest.py               # Shared fixtures (DB, client, mock LLM)
│   ├── test_simulation.py        # 40 tests — engine, transition, actions
│   ├── test_profile_*.py         # Profile computation tests
│   ├── test_memory_*.py          # Memory system tests
│   ├── test_ingestion_*.py       # Ingestion pipeline tests
│   └── test_*.py                 # Model, validator, API tests
├── frontend/
│   ├── next.config.mjs           # API rewrite: /api/* → localhost:8000/*
│   ├── tailwind.config.ts
│   └── src/
│       ├── app/
│       │   ├── layout.tsx
│       │   ├── page.tsx          # Main page — all state + layout
│       │   └── globals.css       # Tailwind + D3 axis styles
│       ├── components/
│       │   ├── EventTimeline.tsx     # D3 swimlane timeline
│       │   ├── SimulationForm.tsx    # Action + horizon form
│       │   ├── ScenarioComparison.tsx # 3-column scenario diff
│       │   └── DomainRadarChart.tsx  # Recharts radar + table
│       └── lib/
│           ├── types.ts          # TypeScript mirrors of Pydantic models
│           └── api.ts            # Typed fetch client
├── pyproject.toml
└── README.md
```

---

## Technical Decisions

**Why Welford's algorithm for profile computation?**
Standard variance requires two passes over all data. With potentially thousands of events, recomputing from scratch on every ingestion is O(n). Welford's algorithm computes running mean and variance in a single pass with O(1) per new event. Combined with the event ID cursor, incremental profile updates process only new events, never the full history.

**Why SQLite as source of truth, ChromaDB as secondary index?**
SQLite stores the authoritative event record. ChromaDB stores vector embeddings for semantic search. If ChromaDB data is lost or corrupted, all events can be re-embedded from SQLite. The two stores are never kept in strict sync — SQLite always wins.

**Why no LLM in the simulation engine?**
LLMs are non-deterministic and slow. The simulation is called on every user interaction. Using heuristic computation with profile-derived parameters gives identical results across runs, sub-millisecond response times, and fully auditable reasoning. The trade-off: the projection model is a calibrated heuristic, not a learned predictor.

**Why three scenario types instead of a probability distribution?**
Probability distributions require a generative model trained on outcome data — which doesn't exist for personal life decisions. Three structured scenarios (optimistic/baseline/conservative) force explicit assumption enumeration and give users concrete comparisons without false precision.

---

## Known Limitations

- **Simulation logic is heuristic, not empirically calibrated.** Confidence scores reflect relative trustworthiness, not statistical probability.
- **Single-user, no authentication.** All data belongs to one global user. Multi-user requires an auth layer and user-scoped queries.
- **SQLite has a single-writer lock.** Under concurrent writes the last writer wins; not suitable for multi-user production without PostgreSQL.
- **Time window parsing in memory queries** only handles 5 patterns ("last N days", "last week/month/quarter/year"). Complex date expressions are ignored.
- **Embedding is not batched.** Ingesting 100 events makes 100 individual embedding API calls.

---

## License

MIT
