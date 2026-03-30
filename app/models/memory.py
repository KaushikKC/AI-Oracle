from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from app.models.event import Event


class EpisodicResult(BaseModel):
    """A single event retrieved by semantic similarity, with its relevance score."""
    event: Event
    relevance_score: float  # 0.0–1.0; 1.0 = identical to query


class SemanticPattern(BaseModel):
    """A recurring behavioral pattern extracted by LLM from a set of events."""
    pattern: str
    supporting_event_ids: List[int]
    confidence: float  # 0.0–1.0


class TemporalWindow(BaseModel):
    """A time-ordered sequence of events within an explicit time window."""
    window_days: int
    start: datetime
    end: datetime
    events: List[Event]  # ascending by timestamp


class MemoryResult(BaseModel):
    """Combined memory output from all three memory types for a given query."""
    query: str
    episodic: List[EpisodicResult]       # ranked by relevance
    semantic: List[SemanticPattern]       # extracted patterns
    temporal: Optional[TemporalWindow] = None  # present only when a time window was detected
