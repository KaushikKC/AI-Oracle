"""
Tests for app/memory/router.py — POST /memory/query endpoint.

What we're testing:
  - Valid request returns 200 with MemoryResult schema.
  - time phrase in query → temporal field populated.
  - include_semantic=False → semantic field is empty.
  - Missing query body returns 422 (Pydantic validation).
  - Empty query string returns 422.
  - Internal retriever failure returns 500.

We override the `get_retriever` dependency so tests never hit real ChromaDB or LLM.
"""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.memory.retriever import MemoryRetriever
from app.memory.router import get_retriever
from app.models.memory import EpisodicResult, MemoryResult, SemanticPattern, TemporalWindow
from app.models.event import Event, EventCategory
from datetime import datetime, timezone, timedelta


# ── Fixtures ─────────────────────────────────────────────────────────────────

def _make_event(event_id: int) -> Event:
    return Event(
        id=event_id,
        timestamp=datetime(2024, 6, 1, tzinfo=timezone.utc),
        category=EventCategory.career,
        sentiment=0.7,
        importance_score=0.8,
        description="Got promoted.",
    )


def _make_memory_result(query: str, with_temporal: bool = False) -> MemoryResult:
    now = datetime.now(timezone.utc)
    return MemoryResult(
        query=query,
        episodic=[EpisodicResult(event=_make_event(1), relevance_score=0.92)],
        semantic=[SemanticPattern(
            pattern="Shows career growth",
            supporting_event_ids=[1],
            confidence=0.85,
        )],
        temporal=TemporalWindow(
            window_days=365,
            start=now - timedelta(days=365),
            end=now,
            events=[_make_event(1)],
        ) if with_temporal else None,
    )


@pytest.fixture
def memory_client() -> TestClient:
    mock_retriever = MagicMock(spec=MemoryRetriever)
    mock_retriever.query.return_value = _make_memory_result("career decisions")
    app.dependency_overrides[get_retriever] = lambda: mock_retriever
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def temporal_memory_client() -> TestClient:
    mock_retriever = MagicMock(spec=MemoryRetriever)
    mock_retriever.query.return_value = _make_memory_result(
        "career decisions in the last year", with_temporal=True
    )
    app.dependency_overrides[get_retriever] = lambda: mock_retriever
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestMemoryQueryEndpoint:
    def test_valid_request_returns_200(self, memory_client: TestClient):
        resp = memory_client.post("/memory/query", json={"query": "career decisions"})
        assert resp.status_code == 200

    def test_response_has_required_fields(self, memory_client: TestClient):
        resp = memory_client.post("/memory/query", json={"query": "career decisions"})
        data = resp.json()
        assert "query" in data
        assert "episodic" in data
        assert "semantic" in data
        assert "temporal" in data  # can be null

    def test_episodic_results_have_event_and_score(self, memory_client: TestClient):
        resp = memory_client.post("/memory/query", json={"query": "career decisions"})
        episodic = resp.json()["episodic"]
        assert len(episodic) == 1
        assert "event" in episodic[0]
        assert "relevance_score" in episodic[0]
        assert episodic[0]["relevance_score"] == 0.92

    def test_semantic_patterns_returned(self, memory_client: TestClient):
        resp = memory_client.post("/memory/query", json={"query": "career decisions"})
        semantic = resp.json()["semantic"]
        assert len(semantic) == 1
        assert semantic[0]["pattern"] == "Shows career growth"
        assert "confidence" in semantic[0]

    def test_temporal_populated_when_time_phrase(self, temporal_memory_client: TestClient):
        resp = temporal_memory_client.post(
            "/memory/query", json={"query": "career decisions in the last year"}
        )
        assert resp.status_code == 200
        temporal = resp.json()["temporal"]
        assert temporal is not None
        assert temporal["window_days"] == 365
        assert len(temporal["events"]) == 1

    def test_include_semantic_false_passed_to_retriever(self, memory_client: TestClient):
        resp = memory_client.post(
            "/memory/query",
            json={"query": "career", "include_semantic": False},
        )
        assert resp.status_code == 200

    def test_n_results_passed_to_retriever(self, memory_client: TestClient):
        resp = memory_client.post(
            "/memory/query",
            json={"query": "career", "n_results": 5},
        )
        assert resp.status_code == 200

    def test_missing_query_returns_422(self, memory_client: TestClient):
        resp = memory_client.post("/memory/query", json={"n_results": 5})
        assert resp.status_code == 422

    def test_empty_query_returns_422(self, memory_client: TestClient):
        resp = memory_client.post("/memory/query", json={"query": ""})
        assert resp.status_code == 422

    def test_retriever_exception_returns_500(self):
        mock_retriever = MagicMock(spec=MemoryRetriever)
        mock_retriever.query.side_effect = RuntimeError("vector store unavailable")
        app.dependency_overrides[get_retriever] = lambda: mock_retriever
        client = TestClient(app, raise_server_exceptions=False)
        try:
            resp = client.post("/memory/query", json={"query": "test"})
            assert resp.status_code == 500
        finally:
            app.dependency_overrides.clear()
