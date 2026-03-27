from datetime import datetime
from typing import List, Literal, Optional, Union

from pydantic import BaseModel

from app.models.event import Event


class StructuredIngestionRequest(BaseModel):
    payload: Union[List[dict], str]
    source_format: Literal["json", "csv"]


class TextIngestionRequest(BaseModel):
    text: str
    hint_timestamp: Optional[datetime] = None


class IngestionResponse(BaseModel):
    accepted: int
    rejected: int
    events: List[Event]
    errors: List[str]
