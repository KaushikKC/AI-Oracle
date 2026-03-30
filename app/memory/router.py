from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.memory.retriever import MemoryRetriever
from app.models.memory import MemoryResult


router = APIRouter(prefix="/memory", tags=["memory"])


# ── Dependency ───────────────────────────────────────────────────────────────

_retriever: Optional[MemoryRetriever] = None


def get_retriever() -> MemoryRetriever:
    """
    Module-level singleton — creates one MemoryRetriever per process.
    Exposed as a function so tests can override it via app.dependency_overrides.
    """
    global _retriever
    if _retriever is None:
        _retriever = MemoryRetriever()
    return _retriever


# ── Schema ───────────────────────────────────────────────────────────────────

class MemoryQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Natural-language memory query")
    n_results: int = Field(10, ge=1, le=100, description="Max episodic events to return")
    include_semantic: bool = Field(True, description="Run LLM pattern extraction")


# ── Endpoint ─────────────────────────────────────────────────────────────────

@router.post("/query", response_model=MemoryResult)
def memory_query(
    request: MemoryQueryRequest,
    retriever: MemoryRetriever = Depends(get_retriever),
) -> MemoryResult:
    """
    Query the memory system.

    Given a natural-language query (e.g. "career decisions in the last year"),
    returns ranked episodic events, extracted semantic patterns, and a
    time-ordered temporal window (when a time phrase is detected).
    """
    try:
        return retriever.query(
            text=request.query,
            n_results=request.n_results,
            include_semantic=request.include_semantic,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
