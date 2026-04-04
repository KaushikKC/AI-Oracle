from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.database import init_db
from app.ingestion.router import router as ingestion_router
from app.memory.router import router as memory_router
from app.profile.router import router as profile_router
from app.storage.router import router as events_router
from app.simulation.router import router as simulation_router

app = FastAPI(
    title="UserLife – Temporal Simulation Engine",
    description="Phases 1–5: Data Ingestion, Memory, Profile, Simulation & Interface",
    version="0.5.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


app.include_router(ingestion_router)
app.include_router(memory_router)
app.include_router(profile_router)
app.include_router(events_router)
app.include_router(simulation_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
