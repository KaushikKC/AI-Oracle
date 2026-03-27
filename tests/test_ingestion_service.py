import json
from unittest.mock import MagicMock, patch

import pytest

from app.ingestion.service import IngestionService


@pytest.fixture
def service(mock_llm_client) -> IngestionService:
    return IngestionService(llm_client=mock_llm_client)


def test_service_routes_json_to_structured_parser(service, db_session):
    payload = [
        {
            "timestamp": "2024-01-01T00:00:00",
            "category": "career",
            "sentiment": "0.5",
            "importance_score": "0.7",
            "description": "Started a new job.",
        }
    ]
    response = service.ingest_structured(db_session, payload, "json")
    assert response.accepted == 1
    assert response.rejected == 0


def test_service_routes_csv_to_structured_parser(service, db_session):
    csv_text = (
        "timestamp,category,sentiment,importance_score,description\n"
        "2024-01-10T08:00:00,health,0.4,0.5,Went for a run.\n"
    )
    response = service.ingest_structured(db_session, csv_text, "csv")
    assert response.accepted == 1


def test_service_routes_text_to_text_parser(service, db_session, mock_llm_client):
    response = service.ingest_text(db_session, "Had a great day at work.")
    assert mock_llm_client.complete.called
    assert response.accepted == 2  # mock returns 2 events


def test_service_returns_correct_accepted_rejected_counts(service, db_session):
    payload = [
        {
            "timestamp": "2024-01-01T00:00:00",
            "category": "career",
            "sentiment": "0.5",
            "importance_score": "0.7",
            "description": "Valid event.",
        },
        {  # missing description → rejected
            "timestamp": "2024-01-02T00:00:00",
            "category": "health",
            "sentiment": "0.3",
            "importance_score": "0.4",
        },
    ]
    response = service.ingest_structured(db_session, payload, "json")
    assert response.accepted == 1
    assert response.rejected == 1


def test_service_stores_only_valid_events(service, db_session):
    from app.storage import event_repository
    payload = [
        {
            "timestamp": "2024-01-01T00:00:00",
            "category": "skills",
            "sentiment": "0.6",
            "importance_score": "0.5",
            "description": "Learned Python.",
        },
        {"category": "health"},  # invalid
    ]
    service.ingest_structured(db_session, payload, "json")
    stored = event_repository.get_events(db_session)
    assert len(stored) == 1
    assert stored[0].description == "Learned Python."


def test_service_unknown_format_returns_error(service, db_session):
    response = service.ingest_structured(db_session, [], "xml")
    assert response.accepted == 0
    assert any("Unknown format" in e for e in response.errors)
