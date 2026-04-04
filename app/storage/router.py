"""
Events REST endpoints.

GET  /events        — paginated list of all stored events (for timeline)
POST /events/seed   — insert n deterministic test events (for dev/demo)
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.event import Event, EventCategory
from app.storage import event_repository

router = APIRouter(prefix="/events", tags=["events"])


@router.get("", response_model=List[Event])
def list_events(
    category: Optional[EventCategory] = None,
    limit: int = 200,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> List[Event]:
    """Return events ordered by timestamp ascending."""
    return event_repository.get_events(db, category=category, limit=limit, offset=offset)


@router.post("/seed", response_model=List[Event])
def seed_events(n: int = 50, db: Session = Depends(get_db)) -> List[Event]:
    """
    Insert n deterministic test events spanning the past 2 years.
    Uses a fixed RNG seed — calling twice inserts duplicates (by design, for testing).
    """
    rng = random.Random(42)
    now = datetime.now(timezone.utc)

    _TEMPLATES: dict[str, list[tuple[str, float, float]]] = {
        "career": [
            ("Got a positive performance review", 0.72, 0.90),
            ("Delivered a major project on time", 0.80, 0.85),
            ("Had a difficult conversation with manager", -0.45, 0.70),
            ("Received a promotion offer", 0.90, 1.00),
            ("Missed a deadline due to scope creep", -0.50, 0.65),
            ("Completed leadership training", 0.60, 0.60),
            ("Joined a new cross-functional team", 0.30, 0.55),
            ("Presented to senior leadership", 0.45, 0.75),
            ("Navigated a difficult re-org", -0.35, 0.70),
            ("Won an internal hackathon", 0.85, 0.60),
        ],
        "health": [
            ("Started going to the gym regularly", 0.70, 0.70),
            ("Caught a bad cold, out for a week", -0.60, 0.60),
            ("Completed a 5k run", 0.80, 0.55),
            ("Had a medical checkup, all clear", 0.50, 0.75),
            ("Struggled with sleep for two weeks", -0.55, 0.65),
            ("Tried meditation for stress relief", 0.40, 0.50),
            ("Injured shoulder at the gym", -0.70, 0.70),
            ("Lost 5kg through consistent diet changes", 0.80, 0.65),
            ("Started therapy sessions", 0.60, 0.80),
            ("Had a week of very high stress at work", -0.50, 0.70),
        ],
        "finances": [
            ("Paid off a credit card", 0.70, 0.80),
            ("Had an unexpected car repair bill", -0.55, 0.70),
            ("Got a salary increase", 0.80, 0.90),
            ("Invested in an index fund", 0.55, 0.65),
            ("Overspent on holiday travel", -0.30, 0.50),
            ("Set up an emergency fund", 0.65, 0.70),
            ("Lost money on a risky investment", -0.70, 0.80),
            ("Negotiated lower rent on renewal", 0.60, 0.70),
            ("Bought a new laptop for side work", -0.20, 0.40),
            ("Received a bonus", 0.75, 0.85),
        ],
        "relationships": [
            ("Had a great dinner with old friends", 0.80, 0.60),
            ("Went through a difficult breakup", -0.90, 0.95),
            ("Met a new close friend at a conference", 0.70, 0.65),
            ("Had a falling out with a colleague", -0.50, 0.65),
            ("Reconnected with a family member", 0.65, 0.75),
            ("Helped a friend through a tough time", 0.70, 0.55),
            ("Attended a wedding of a close friend", 0.80, 0.65),
            ("Moved to a new city away from support network", -0.40, 0.80),
            ("Had a meaningful conversation with a mentor", 0.75, 0.70),
            ("Resolved a long-standing conflict with a sibling", 0.65, 0.75),
        ],
        "skills": [
            ("Completed an online certification course", 0.70, 0.65),
            ("Built a side project from scratch", 0.80, 0.75),
            ("Gave a talk at a local meetup", 0.65, 0.65),
            ("Learned a new programming language", 0.75, 0.55),
            ("Struggled to keep up with new tooling at work", -0.30, 0.55),
            ("Published a technical blog post", 0.55, 0.55),
            ("Completed an intensive workshop", 0.65, 0.65),
            ("Mentored a junior colleague", 0.70, 0.55),
            ("Spent a weekend deep-diving into a hard problem", 0.60, 0.60),
            ("Failed to finish an online course I started", -0.35, 0.45),
        ],
    }

    categories = list(_TEMPLATES.keys())
    events: List[Event] = []

    for _ in range(n):
        days_ago = rng.uniform(0, 730)
        ts = now - timedelta(days=days_ago)
        cat = rng.choice(categories)
        desc, base_s, base_i = rng.choice(_TEMPLATES[cat])

        sentiment = round(
            max(-1.0, min(1.0, base_s + rng.uniform(-0.12, 0.12))), 2
        )
        importance = round(
            max(0.05, min(1.0, base_i + rng.uniform(-0.08, 0.08))), 2
        )

        events.append(Event(
            timestamp=ts,
            category=EventCategory(cat),
            sentiment=sentiment,
            importance_score=importance,
            description=desc,
        ))

    return event_repository.insert_bulk(db, events)
