from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.ingestion.service import IngestionService
from app.models.ingestion import IngestionResponse, StructuredIngestionRequest, TextIngestionRequest

router = APIRouter(prefix="/ingest", tags=["ingestion"])

_service = IngestionService()


@router.post("/structured", response_model=IngestionResponse)
def ingest_structured(
    request: StructuredIngestionRequest,
    db: Session = Depends(get_db),
) -> IngestionResponse:
    return _service.ingest_structured(db, request.payload, request.source_format)


@router.post("/text", response_model=IngestionResponse)
def ingest_text(
    request: TextIngestionRequest,
    db: Session = Depends(get_db),
) -> IngestionResponse:
    return _service.ingest_text(db, request.text, request.hint_timestamp)
