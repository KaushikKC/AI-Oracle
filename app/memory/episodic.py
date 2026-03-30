"""
Episodic Memory — raw event retrieval by semantic similarity.

What "episodic" means here (borrowed from cognitive science):
  Episodic memory stores specific events tied to time and context.
  "What happened when I applied for that promotion?" → returns the actual events.

How it works:
  1. Embed the query text.
  2. Run a cosine similarity search in ChromaDB.
  3. Optionally filter by time window (since_days) and/or category.
  4. Return ranked EpisodicResult list (relevance descending, timestamp descending on ties).

Why this is separate from the vector store:
  The vector store is a low-level I/O layer (chromadb operations).
  EpisodicMemory owns the query logic: how to build the where clause,
  how to sort results, what the public API looks like for callers.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from app.memory.embedder import Embedder
from app.memory.vector_store import EventVectorStore
from app.models.event import EventCategory
from app.models.memory import EpisodicResult


class EpisodicMemory:
    def __init__(self, store: EventVectorStore, embedder: Embedder) -> None:
        self._store = store
        self._embedder = embedder

    def query(
        self,
        text: str,
        n_results: int = 10,
        since_days: Optional[int] = None,
        category: Optional[EventCategory] = None,
    ) -> List[EpisodicResult]:
        """
        Retrieve events semantically similar to `text`.

        Args:
            text:        Natural-language query (e.g. "career decisions").
            n_results:   Max number of events to return.
            since_days:  Only include events from the last N days. None = no filter.
            category:    Only include events of this category. None = all categories.

        Returns:
            List of EpisodicResult sorted by relevance_score descending.
        """
        embedding = self._embedder.embed(text)
        where = _build_where(since_days, category)
        pairs = self._store.semantic_query(embedding, n_results=n_results, where=where)

        results = [
            EpisodicResult(event=ev, relevance_score=score)
            for ev, score in pairs
        ]
        results.sort(key=lambda r: (-r.relevance_score, -r.event.timestamp.timestamp()))
        return results


def _build_where(
    since_days: Optional[int],
    category: Optional[EventCategory],
) -> Optional[Dict]:
    """Build a ChromaDB where clause from optional filters."""
    conditions = []
    if since_days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)
        conditions.append({"timestamp_unix": {"$gte": cutoff.timestamp()}})
    if category is not None:
        conditions.append({"category": {"$eq": category.value}})

    if not conditions:
        return None
    if len(conditions) == 1:
        return conditions[0]
    return {"$and": conditions}
