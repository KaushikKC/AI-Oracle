from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class EventCategory(str, Enum):
    career = "career"
    health = "health"
    finances = "finances"
    relationships = "relationships"
    skills = "skills"
    other = "other"


class Event(BaseModel):
    id: Optional[int] = None
    timestamp: datetime
    category: EventCategory
    sentiment: float = Field(..., ge=-1.0, le=1.0)
    importance_score: float = Field(..., ge=0.0, le=1.0)
    description: str = Field(..., min_length=1)
    source_raw: Optional[str] = None

    @field_validator("description")
    @classmethod
    def strip_description(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("description cannot be empty or whitespace")
        return stripped
