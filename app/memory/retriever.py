"""
MemoryRetriever — the main entry point for Phase 2.

This is the only class the simulation engine (Phase 3) will call directly.
It orchestrates all three memory types into a single MemoryResult.

Query flow for e.g. "career decisions in the last year":
  1. _parse_time_window("career decisions in the last year") → 365
  2. EpisodicMemory.query(text, since_days=365)  →  top-N events by similarity
  3. SemanticMemory.extract_patterns(those events) → behavioral patterns
  4. TemporalMemory.query_window(365)             → all events in last 365 days, ordered
  5. Return MemoryResult combining all three.

Time window parsing (regex-based, intentionally simple):
  "last N days"    → N
  "last week"      → 7
  "last month"     → 30
  "last quarter"   → 90
  "last year"      → 365
  No match         → None (no time filter on episodic; no temporal window returned)

Why not parse with LLM?
  Regex is deterministic, free, and covers all the cases Phase 3 needs.
  Introducing an LLM call here would add latency and a failure mode for what
  is fundamentally a structural operation.

Design note on include_semantic:
  Pattern extraction adds a full LLM round-trip. The caller can disable it
  (include_semantic=False) for fast retrieval-only queries where patterns
  aren't needed (e.g., streaming context to the simulation engine).
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

from app.memory.embedder import Embedder, get_embedder
from app.memory.episodic import EpisodicMemory
from app.memory.semantic import SemanticMemory
from app.memory.temporal import TemporalMemory
from app.memory.vector_store import EventVectorStore
from app.models.memory import MemoryResult


# ── Time window parsing ──────────────────────────────────────────────────────

_TIME_PATTERNS: List[Tuple[str, object]] = [
    (r"\blast\s+(\d+)\s+days?\b",  lambda m: int(m.group(1))),
    (r"\blast\s+week\b",           lambda _: 7),
    (r"\blast\s+month\b",          lambda _: 30),
    (r"\blast\s+quarter\b",        lambda _: 90),
    (r"\blast\s+year\b",           lambda _: 365),
]


def parse_time_window(text: str) -> Optional[int]:
    """
    Extract a time window (days) from a natural-language query.
    Returns None if no recognizable time phrase is found.
    """
    lower = text.lower()
    for pattern, extractor in _TIME_PATTERNS:
        m = re.search(pattern, lower)
        if m:
            return extractor(m)
    return None


# ── Retriever ────────────────────────────────────────────────────────────────

class MemoryRetriever:
    """
    Context-aware memory query engine.

    Returns grounded facts (events + patterns + temporal sequence) that the
    simulation engine can use as behavioral context — not a conversational answer.
    """

    def __init__(
        self,
        store: Optional[EventVectorStore] = None,
        embedder: Optional[Embedder] = None,
        llm_client=None,
    ) -> None:
        _embedder = embedder or get_embedder()
        _store = store or EventVectorStore(embedder=_embedder)
        self._episodic = EpisodicMemory(_store, _embedder)
        self._semantic = SemanticMemory(llm_client)
        self._temporal = TemporalMemory(_store)

    def query(
        self,
        text: str,
        n_results: int = 10,
        include_semantic: bool = True,
    ) -> MemoryResult:
        """
        Run a full memory query.

        Args:
            text:             Natural-language query, e.g. "career decisions in the last year".
            n_results:        How many episodic events to retrieve.
            include_semantic: Whether to run LLM pattern extraction (adds latency).

        Returns:
            MemoryResult with:
              - episodic:  top-N events ranked by semantic relevance
              - semantic:  extracted behavioral patterns ([] if include_semantic=False)
              - temporal:  time-ordered events for the detected window (None if no time phrase)
        """
        since_days = parse_time_window(text)

        # 1. Episodic: semantic similarity + optional time filter
        episodic = self._episodic.query(
            text=text,
            n_results=n_results,
            since_days=since_days,
        )

        # 2. Semantic: LLM pattern extraction over the retrieved events
        semantic = []
        if include_semantic and episodic:
            semantic = self._semantic.extract_patterns([r.event for r in episodic])

        # 3. Temporal: chronological sequence for the detected window
        temporal = None
        if since_days is not None:
            temporal = self._temporal.query_window(window_days=since_days)

        return MemoryResult(
            query=text,
            episodic=episodic,
            semantic=semantic,
            temporal=temporal,
        )
