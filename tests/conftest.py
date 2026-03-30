from datetime import datetime, timezone, timedelta
from typing import Generator, List
from unittest.mock import MagicMock

import chromadb
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base, get_db
from app.db import orm_models  # noqa: F401 – register ORM models
from app.llm.client import LLMClient
from app.memory.embedder import Embedder
from app.memory.vector_store import EventVectorStore
from app.models.event import Event, EventCategory


# ── Database fixtures ────────────────────────────────────────────────────────

@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


# ── LLM mock ────────────────────────────────────────────────────────────────

VALID_LLM_RESPONSE = """[
  {
    "timestamp": "2024-06-15T09:00:00",
    "category": "career",
    "sentiment": 0.8,
    "importance_score": 0.9,
    "description": "Received a promotion to senior engineer."
  },
  {
    "timestamp": "2024-06-20T18:00:00",
    "category": "health",
    "sentiment": -0.3,
    "importance_score": 0.4,
    "description": "Started feeling burned out from overwork."
  }
]"""


@pytest.fixture
def mock_llm_client() -> LLMClient:
    client = MagicMock(spec=LLMClient)
    client.complete.return_value = VALID_LLM_RESPONSE
    return client


# ── Sample data fixtures ─────────────────────────────────────────────────────

@pytest.fixture
def sample_event() -> Event:
    return Event(
        timestamp=datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
        category=EventCategory.career,
        sentiment=0.7,
        importance_score=0.8,
        description="Got promoted to senior engineer.",
    )


@pytest.fixture
def sample_structured_json() -> list:
    return [
        {
            "timestamp": "2024-01-01T00:00:00",
            "category": "career",
            "sentiment": "0.5",
            "importance_score": "0.7",
            "description": "Started a new job.",
        },
        {
            "timestamp": "2024-02-14T12:00:00",
            "category": "relationships",
            "sentiment": "0.9",
            "importance_score": "0.6",
            "description": "Celebrated anniversary.",
        },
        {  # invalid: missing description
            "timestamp": "2024-03-01T00:00:00",
            "category": "health",
            "sentiment": "0.1",
            "importance_score": "0.3",
        },
    ]


@pytest.fixture
def sample_csv_string() -> str:
    return (
        "timestamp,category,sentiment,importance_score,description\n"
        "2024-01-10T08:00:00,career,0.6,0.7,Completed a major project.\n"
        "2024-01-20T14:00:00,INVALID_CAT,0.2,0.5,Had a weird day.\n"
        "2024-01-30T20:00:00,health,1.9,0.4,Went for a long run.\n"
    )


@pytest.fixture
def sample_journal_text() -> str:
    return (
        "March 15 2024 — Finally got the promotion I've been working toward for two years. "
        "Feels like all the late nights paid off. Huge relief and excitement.\n\n"
        "March 22 2024 — Doctor said my blood pressure is elevated. Probably stress-related. "
        "Need to cut back on caffeine and sleep more."
    )


# ── Phase 2: Memory fixtures ─────────────────────────────────────────────────

class MockEmbedder(Embedder):
    """
    Deterministic 4-dim embedder for tests.
    All texts get the same vector — that's fine for unit tests that check
    data-flow mechanics, not semantic ranking quality.
    """
    DIM = 4

    def embed(self, text: str) -> List[float]:
        return [0.1, 0.2, 0.3, 0.4]


@pytest.fixture
def mock_embedder() -> MockEmbedder:
    return MockEmbedder()


@pytest.fixture
def chroma_client() -> chromadb.ClientAPI:
    """In-memory ChromaDB client — isolated per test, no disk I/O."""
    return chromadb.EphemeralClient()


@pytest.fixture
def vector_store(chroma_client: chromadb.ClientAPI, mock_embedder: MockEmbedder) -> EventVectorStore:
    """Empty EventVectorStore backed by in-memory ChromaDB."""
    return EventVectorStore(client=chroma_client, embedder=mock_embedder)


@pytest.fixture
def now() -> datetime:
    return datetime.now(timezone.utc)


@pytest.fixture
def sample_events(now: datetime) -> List[Event]:
    """Three events at different times and categories for memory tests."""
    return [
        Event(
            id=1,
            timestamp=now - timedelta(days=400),
            category=EventCategory.career,
            sentiment=0.8,
            importance_score=0.9,
            description="Got promoted to senior engineer.",
        ),
        Event(
            id=2,
            timestamp=now - timedelta(days=200),
            category=EventCategory.career,
            sentiment=0.6,
            importance_score=0.7,
            description="Led a major product launch successfully.",
        ),
        Event(
            id=3,
            timestamp=now - timedelta(days=10),
            category=EventCategory.health,
            sentiment=-0.4,
            importance_score=0.5,
            description="Feeling burned out from overwork.",
        ),
    ]


@pytest.fixture
def populated_store(vector_store: EventVectorStore, sample_events: List[Event]) -> EventVectorStore:
    """EventVectorStore pre-loaded with three sample events."""
    vector_store.add_bulk(sample_events)
    return vector_store


VALID_PATTERN_RESPONSE = (
    '[{"pattern": "Shows consistent career growth", '
    '"supporting_event_ids": [1, 2], "confidence": 0.9}]'
)


@pytest.fixture
def mock_llm_for_patterns() -> LLMClient:
    client = MagicMock(spec=LLMClient)
    client.complete.return_value = VALID_PATTERN_RESPONSE
    return client


# ── FastAPI TestClient ────────────────────────────────────────────────────────

@pytest.fixture
def test_client(db_session: Session) -> TestClient:
    from app.main import app

    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()
