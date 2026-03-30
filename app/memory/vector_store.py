"""
ChromaDB vector store wrapper for Phase 2 Memory System.

Architecture decisions:
- ChromaDB is the semantic index; SQLite remains the relational source of truth.
  Events are dual-written after SQLite assigns their IDs, so chroma IDs always
  match SQLite event IDs.
- Distance metric: cosine (hnsw:space="cosine"). Cosine distance ∈ [0, 2];
  we convert to relevance ∈ [0, 1] via: relevance = 1 - distance / 2.
- Two query modes:
    semantic_query() — embedding similarity search (for episodic memory)
    temporal_get()   — metadata filter with no embedding (for temporal memory)
  Keeping these separate is intentional: temporal queries are purely structural
  and don't need a dummy "zero vector" trick.
- Metadata stored per event:
    event_id, timestamp_iso, timestamp_unix (for range filtering),
    category, sentiment, importance_score, source_raw.
  ChromaDB metadata values must be str/int/float/bool (no None), so source_raw
  is stored as "" and converted back to None on read.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import chromadb

from app.config import settings
from app.memory.embedder import Embedder, get_embedder
from app.models.event import Event, EventCategory


_COLLECTION_NAME = "events"


# ── Helpers ─────────────────────────────────────────────────────────────────

def _event_to_text(event: Event) -> str:
    """Text to embed: description is always present; append source_raw if it adds context."""
    text = event.description
    if event.source_raw:
        text = text + " " + event.source_raw
    return text


def _metadata_from_event(event: Event) -> Dict[str, Any]:
    return {
        "event_id": event.id,
        "timestamp_iso": event.timestamp.isoformat(),
        "timestamp_unix": event.timestamp.timestamp(),
        "category": event.category.value,
        "sentiment": event.sentiment,
        "importance_score": event.importance_score,
        "source_raw": event.source_raw or "",
    }


def _event_from_row(document: str, meta: Dict[str, Any]) -> Event:
    return Event(
        id=meta["event_id"],
        timestamp=datetime.fromisoformat(meta["timestamp_iso"]),
        category=EventCategory(meta["category"]),
        sentiment=meta["sentiment"],
        importance_score=meta["importance_score"],
        description=document,
        source_raw=meta["source_raw"] or None,
    )


# ── Store ────────────────────────────────────────────────────────────────────

class EventVectorStore:
    def __init__(
        self,
        client: chromadb.ClientAPI | None = None,
        embedder: Embedder | None = None,
    ) -> None:
        self._client = client or chromadb.PersistentClient(path=settings.chroma_path)
        # cosine distance so relevance = 1 - dist/2 maps cleanly to [0, 1]
        self._collection = self._client.get_or_create_collection(
            _COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        self._embedder = embedder or get_embedder()

    # ── Write ────────────────────────────────────────────────────────────────

    def add_event(self, event: Event) -> None:
        """Embed and upsert a single event. Uses upsert so re-ingestion is idempotent."""
        text = _event_to_text(event)
        embedding = self._embedder.embed(text)
        self._collection.upsert(
            ids=[str(event.id)],
            embeddings=[embedding],
            documents=[event.description],
            metadatas=[_metadata_from_event(event)],
        )

    def add_bulk(self, events: List[Event]) -> None:
        for event in events:
            self.add_event(event)

    # ── Read ─────────────────────────────────────────────────────────────────

    def semantic_query(
        self,
        query_embedding: List[float],
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[Event, float]]:
        """
        Returns (event, relevance_score) pairs sorted by relevance descending.
        relevance_score ∈ [0, 1]; higher = more semantically similar to the query.
        """
        count = self._collection.count()
        if count == 0:
            return []
        n = min(n_results, count)
        kwargs: Dict[str, Any] = {
            "query_embeddings": [query_embedding],
            "n_results": n,
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where
        result = self._collection.query(**kwargs)

        pairs: List[Tuple[Event, float]] = []
        for doc, meta, dist in zip(
            result["documents"][0],
            result["metadatas"][0],
            result["distances"][0],
        ):
            event = _event_from_row(doc, meta)
            relevance = max(0.0, 1.0 - dist / 2.0)
            pairs.append((event, round(relevance, 4)))
        return pairs

    def temporal_get(
        self,
        since_unix: float,
        until_unix: float | None = None,
        category: str | None = None,
    ) -> List[Event]:
        """
        Fetch all events within [since_unix, until_unix], optionally filtered by category.
        No embedding involved — this is a pure metadata filter via collection.get().
        Results are returned sorted by timestamp ascending.
        """
        conditions: List[Dict[str, Any]] = [
            {"timestamp_unix": {"$gte": since_unix}},
        ]
        if until_unix is not None:
            conditions.append({"timestamp_unix": {"$lte": until_unix}})
        if category is not None:
            conditions.append({"category": {"$eq": category}})

        where: Dict[str, Any] = (
            {"$and": conditions} if len(conditions) > 1 else conditions[0]
        )

        result = self._collection.get(
            where=where,
            include=["documents", "metadatas"],
        )

        events = [
            _event_from_row(doc, meta)
            for doc, meta in zip(result["documents"], result["metadatas"])
        ]
        return sorted(events, key=lambda e: e.timestamp)

    @property
    def count(self) -> int:
        return self._collection.count()
