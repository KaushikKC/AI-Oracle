"""
Temporal Memory — time-ordered event sequences over explicit time windows.

What "temporal" means here:
  Rather than asking "what events are similar to X?", temporal memory asks
  "what happened in the last N days?" — a structural time-slice, not a semantic search.

How it works:
  Calls EventVectorStore.temporal_get() which uses ChromaDB's metadata filter
  (collection.get with where clause on timestamp_unix) — NO embedding needed.
  Results are returned sorted by timestamp ascending, giving the simulation engine
  a chronological narrative of the selected window.

Why separate from EpisodicMemory:
  Episodic uses embedding similarity + optional time filter.
  Temporal is purely time-structured with no semantic component.
  The simulation engine needs both: "find career events similar to this situation"
  (episodic) AND "reconstruct the last 90 days in order" (temporal).

Time windows used by the simulation engine:
  30 days  — recent context (emotional state, active decisions)
  90 days  — medium-term patterns (quarterly cycles)
  365 days — long-term character traits and life arcs
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from app.memory.vector_store import EventVectorStore
from app.models.event import EventCategory
from app.models.memory import TemporalWindow


class TemporalMemory:
    def __init__(self, store: EventVectorStore) -> None:
        self._store = store

    def query_window(
        self,
        window_days: int,
        category: Optional[EventCategory] = None,
        reference_time: Optional[datetime] = None,
    ) -> TemporalWindow:
        """
        Return all events within the last `window_days` days, sorted by timestamp.

        Args:
            window_days:     Number of days to look back.
            category:        Optional category filter.
            reference_time:  The "now" anchor (default: current UTC time).
                             Useful for deterministic testing and future simulation.
        """
        end = reference_time or datetime.now(timezone.utc)
        start = end - timedelta(days=window_days)

        events = self._store.temporal_get(
            since_unix=start.timestamp(),
            until_unix=end.timestamp(),
            category=category.value if category else None,
        )

        return TemporalWindow(
            window_days=window_days,
            start=start,
            end=end,
            events=events,
        )
