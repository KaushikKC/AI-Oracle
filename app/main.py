from fastapi import FastAPI

from app.db.database import init_db
from app.ingestion.router import router as ingestion_router
from app.memory.router import router as memory_router

app = FastAPI(
    title="UserLife – Temporal Simulation Engine",
    description="Phase 1 & 2: Data Ingestion, Structuring & Memory System",
    version="0.2.0",
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


app.include_router(ingestion_router)
app.include_router(memory_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
