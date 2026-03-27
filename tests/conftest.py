from datetime import datetime, timezone
from typing import Generator
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base, get_db
from app.db import orm_models  # noqa: F401 – register ORM models
from app.llm.client import LLMClient
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


# ── FastAPI TestClient ────────────────────────────────────────────────────────

@pytest.fixture
def test_client(db_session: Session) -> TestClient:
    from app.main import app

    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()
