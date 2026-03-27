from fastapi import FastAPI

from app.db.database import init_db
from app.ingestion.router import router as ingestion_router

app = FastAPI(
    title="UserLife – Temporal Simulation Engine",
    description="Phase 1: Data Ingestion & Structuring Pipeline",
    version="0.1.0",
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


app.include_router(ingestion_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
