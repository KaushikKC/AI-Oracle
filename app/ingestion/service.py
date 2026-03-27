from typing import List, Optional, Tuple
from datetime import datetime

from sqlalchemy.orm import Session

from app.ingestion.parsers.structured_parser import StructuredParser
from app.ingestion.parsers.text_parser import TextParser
from app.llm.client import LLMClient, get_llm_client
from app.models.event import Event
from app.models.ingestion import IngestionResponse
from app.storage import event_repository


class IngestionService:
    def __init__(self, llm_client: Optional[LLMClient] = None) -> None:
        self._llm_client = llm_client or get_llm_client()
        self._structured_parser = StructuredParser()
        self._text_parser = TextParser(self._llm_client)

    def ingest_structured(
        self,
        db: Session,
        payload: object,
        source_format: str,
    ) -> IngestionResponse:
        if source_format == "json":
            events, errors = self._structured_parser.parse_json(payload)
        elif source_format == "csv":
            events, errors = self._structured_parser.parse_csv(payload)
        else:
            return IngestionResponse(accepted=0, rejected=0, events=[], errors=[f"Unknown format: {source_format}"])

        return self._store_and_respond(db, events, errors)

    def ingest_text(
        self,
        db: Session,
        text: str,
        hint_timestamp: Optional[datetime] = None,
    ) -> IngestionResponse:
        events, errors = self._text_parser.parse_text(text, hint_timestamp)
        return self._store_and_respond(db, events, errors)

    def _store_and_respond(
        self,
        db: Session,
        events: List[Event],
        errors: List[str],
    ) -> IngestionResponse:
        stored: List[Event] = []
        store_errors: List[str] = list(errors)

        if events:
            try:
                stored = event_repository.insert_bulk(db, events)
            except Exception as exc:
                store_errors.append(f"DB insert failed: {exc}")

        return IngestionResponse(
            accepted=len(stored),
            rejected=len(store_errors),
            events=stored,
            errors=store_errors,
        )
