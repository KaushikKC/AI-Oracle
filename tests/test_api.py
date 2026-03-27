import pytest

from app.ingestion.service import IngestionService
from app.main import app


@pytest.fixture
def client_with_mock_llm(db_session, mock_llm_client):
    from fastapi.testclient import TestClient
    from app.db.database import get_db

    # Override both DB and LLM
    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db

    # Patch the module-level _service in router to use mock LLM
    import app.ingestion.router as ingestion_router_module
    original_service = ingestion_router_module._service
    ingestion_router_module._service = IngestionService(llm_client=mock_llm_client)

    client = TestClient(app)
    yield client

    app.dependency_overrides.clear()
    ingestion_router_module._service = original_service


def test_health_endpoint_returns_ok(client_with_mock_llm):
    response = client_with_mock_llm.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_post_ingest_structured_json_returns_200(client_with_mock_llm):
    payload = {
        "source_format": "json",
        "payload": [
            {
                "timestamp": "2024-05-01T10:00:00",
                "category": "career",
                "sentiment": "0.7",
                "importance_score": "0.8",
                "description": "Got a raise.",
            }
        ],
    }
    response = client_with_mock_llm.post("/ingest/structured", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["accepted"] == 1


def test_post_ingest_structured_csv_returns_200(client_with_mock_llm):
    csv_text = (
        "timestamp,category,sentiment,importance_score,description\n"
        "2024-06-01T09:00:00,health,0.3,0.5,Morning run completed.\n"
    )
    payload = {"source_format": "csv", "payload": csv_text}
    response = client_with_mock_llm.post("/ingest/structured", json=payload)
    assert response.status_code == 200
    assert response.json()["accepted"] == 1


def test_post_ingest_text_returns_200(client_with_mock_llm):
    payload = {"text": "Today I got promoted and it felt amazing."}
    response = client_with_mock_llm.post("/ingest/text", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "accepted" in data
    assert "events" in data


def test_post_ingest_structured_with_empty_payload_returns_200_zero_accepted(client_with_mock_llm):
    payload = {"source_format": "json", "payload": []}
    response = client_with_mock_llm.post("/ingest/structured", json=payload)
    assert response.status_code == 200
    assert response.json()["accepted"] == 0


def test_ingest_response_shape_matches_schema(client_with_mock_llm):
    payload = {"source_format": "json", "payload": []}
    response = client_with_mock_llm.post("/ingest/structured", json=payload)
    data = response.json()
    assert set(data.keys()) == {"accepted", "rejected", "events", "errors"}


def test_post_ingest_structured_missing_format_returns_422(client_with_mock_llm):
    payload = {"payload": []}
    response = client_with_mock_llm.post("/ingest/structured", json=payload)
    assert response.status_code == 422
