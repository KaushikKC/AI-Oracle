from typing import TYPE_CHECKING, List, Optional, Tuple
from datetime import datetime

from sqlalchemy.orm import Session

from app.ingestion.parsers.structured_parser import StructuredParser
from app.ingestion.parsers.text_parser import TextParser
from app.llm.client import LLMClient, get_llm_client
from app.models.event import Event
from app.models.ingestion import IngestionResponse
from app.storage import event_repository

if TYPE_CHECKING:
    from app.memory.vector_store import EventVectorStore


class IngestionService:
    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        vector_store: Optional["EventVectorStore"] = None,
    ) -> None:
        self._llm_client = llm_client or get_llm_client()
        self._structured_parser = StructuredParser()
        self._text_parser = TextParser(self._llm_client)
        # Optional: when provided, events are dual-written to ChromaDB after SQLite.
        # None means ingestion-only mode (Phase 1 behaviour, used by existing tests).
        self._vector_store = vector_store

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

        # Phase 2: dual-write to ChromaDB vector store (non-critical path).
        # Failures here are reported in errors but do not affect accepted count
        # because SQLite remains the source of truth.
        if stored and self._vector_store is not None:
            try:
                self._vector_store.add_bulk(stored)
            except Exception as exc:
                store_errors.append(f"Vector store insert failed: {exc}")

        return IngestionResponse(
            accepted=len(stored),
            rejected=len(store_errors),
            events=stored,
            errors=store_errors,
        )
