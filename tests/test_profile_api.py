"""
Tests for app/profile/router.py

Endpoints:
  POST /profile/build   — full rebuild
  POST /profile/update  — incremental update
  GET  /profile/latest  — most recent snapshot
  GET  /profile/history — all snapshots
  GET  /profile/{version} — specific version

Tests use the real DB session (in-memory SQLite) via db_session fixture.
The profile ORM tables are created via init_db() which is called at app startup.
We override the DB dependency the same way Phase 1 tests do.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.database import get_db
from app.db import profile_orm  # noqa: F401 — ensure table is registered


@pytest.fixture
def profile_client(db_session: Session) -> TestClient:
    app.dependency_overrides[get_db] = lambda: db_session
    # Create the profile_snapshots table in the in-memory DB
    from app.db.database import Base
    from sqlalchemy import create_engine
    engine = db_session.get_bind()
    profile_orm.UserProfileSnapshotORM.__table__.create(bind=engine, checkfirst=True)
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def _ingest_events(client: TestClient, n: int = 5) -> None:
    """Helper: ingest N career events via the ingestion API."""
    payload = [
        {
            "timestamp": f"2024-0{(i % 9) + 1}-01T00:00:00",
            "category": "career",
            "sentiment": 0.5,
            "importance_score": 0.8,
            "description": f"Career event {i}",
        }
        for i in range(1, n + 1)
    ]
    client.post("/ingest/structured", json={"payload": payload, "source_format": "json"})


# ── POST /profile/build ───────────────────────────────────────────────────────

class TestBuildEndpoint:
    def test_returns_200(self, profile_client):
        resp = profile_client.post("/profile/build")
        assert resp.status_code == 200

    def test_returns_profile_snapshot_schema(self, profile_client):
        resp = profile_client.post("/profile/build")
        data = resp.json()
        assert "version" in data
        assert "profile" in data
        assert "created_at" in data
        assert data["version"] == 1

    def test_profile_has_all_fields(self, profile_client):
        resp = profile_client.post("/profile/build")
        profile = resp.json()["profile"]
        assert "risk_tolerance" in profile
        assert "consistency" in profile
        assert "priorities" in profile
        assert "avg_sentiment_by_domain" in profile
        assert "activity_density" in profile
        assert "event_count" in profile

    def test_version_increments_on_repeated_build(self, profile_client):
        r1 = profile_client.post("/profile/build")
        r2 = profile_client.post("/profile/build")
        assert r2.json()["version"] == r1.json()["version"] + 1

    def test_event_count_reflects_ingested_events(self, profile_client):
        _ingest_events(profile_client, n=5)
        resp = profile_client.post("/profile/build")
        assert resp.json()["profile"]["event_count"] == 5


# ── POST /profile/update ──────────────────────────────────────────────────────

class TestUpdateEndpoint:
    def test_update_with_no_snapshot_falls_back_to_build(self, profile_client):
        resp = profile_client.post("/profile/update")
        assert resp.status_code == 200
        assert resp.json()["version"] == 1

    def test_update_after_build_creates_new_version(self, profile_client):
        _ingest_events(profile_client, n=3)
        profile_client.post("/profile/build")
        _ingest_events(profile_client, n=3)
        resp = profile_client.post("/profile/update")
        assert resp.json()["version"] == 2

    def test_update_with_no_new_events_returns_same_version(self, profile_client):
        _ingest_events(profile_client, n=3)
        profile_client.post("/profile/build")
        # No new events ingested
        resp = profile_client.post("/profile/update")
        assert resp.json()["version"] == 1


# ── GET /profile/latest ───────────────────────────────────────────────────────

class TestLatestEndpoint:
    def test_returns_404_when_no_profile(self, profile_client):
        resp = profile_client.get("/profile/latest")
        assert resp.status_code == 404

    def test_returns_latest_after_build(self, profile_client):
        profile_client.post("/profile/build")
        resp = profile_client.get("/profile/latest")
        assert resp.status_code == 200
        assert resp.json()["version"] == 1

    def test_returns_most_recent_version(self, profile_client):
        profile_client.post("/profile/build")
        profile_client.post("/profile/build")
        resp = profile_client.get("/profile/latest")
        assert resp.json()["version"] == 2


# ── GET /profile/history ──────────────────────────────────────────────────────

class TestHistoryEndpoint:
    def test_returns_empty_list_when_no_profile(self, profile_client):
        resp = profile_client.get("/profile/history")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_all_snapshots_in_order(self, profile_client):
        profile_client.post("/profile/build")
        profile_client.post("/profile/build")
        profile_client.post("/profile/build")
        history = profile_client.get("/profile/history").json()
        assert len(history) == 3
        assert [s["version"] for s in history] == [1, 2, 3]


# ── GET /profile/{version} ────────────────────────────────────────────────────

class TestVersionEndpoint:
    def test_returns_correct_version(self, profile_client):
        profile_client.post("/profile/build")
        profile_client.post("/profile/build")
        resp = profile_client.get("/profile/1")
        assert resp.status_code == 200
        assert resp.json()["version"] == 1

    def test_returns_404_for_missing_version(self, profile_client):
        resp = profile_client.get("/profile/99")
        assert resp.status_code == 404
