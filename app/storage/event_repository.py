from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from app.db.orm_models import EventORM
from app.models.event import Event, EventCategory


def _orm_to_event(orm: EventORM) -> Event:
    return Event(
        id=orm.id,
        timestamp=orm.timestamp,
        category=EventCategory(orm.category),
        sentiment=orm.sentiment,
        importance_score=orm.importance_score,
        description=orm.description,
        source_raw=orm.source_raw,
    )


def insert_event(db: Session, event: Event) -> Event:
    orm = EventORM(
        timestamp=event.timestamp,
        category=event.category.value,
        sentiment=event.sentiment,
        importance_score=event.importance_score,
        description=event.description,
        source_raw=event.source_raw,
        created_at=datetime.now(timezone.utc),
    )
    db.add(orm)
    db.commit()
    db.refresh(orm)
    return _orm_to_event(orm)


def insert_bulk(db: Session, events: List[Event]) -> List[Event]:
    now = datetime.now(timezone.utc)
    orm_objects = [
        EventORM(
            timestamp=e.timestamp,
            category=e.category.value,
            sentiment=e.sentiment,
            importance_score=e.importance_score,
            description=e.description,
            source_raw=e.source_raw,
            created_at=now,
        )
        for e in events
    ]
    db.add_all(orm_objects)
    db.commit()
    for orm in orm_objects:
        db.refresh(orm)
    return [_orm_to_event(orm) for orm in orm_objects]


def get_events(
    db: Session,
    category: Optional[EventCategory] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[Event]:
    query = db.query(EventORM).order_by(EventORM.timestamp.asc())
    if category:
        query = query.filter(EventORM.category == category.value)
    return [_orm_to_event(orm) for orm in query.offset(offset).limit(limit).all()]


def get_event_by_id(db: Session, event_id: int) -> Optional[Event]:
    orm = db.query(EventORM).filter(EventORM.id == event_id).first()
    return _orm_to_event(orm) if orm else None


def get_all_events(db: Session) -> List[Event]:
    """Fetch every event ordered by timestamp. Used by ProfileBuilder full rebuild."""
    return [
        _orm_to_event(orm)
        for orm in db.query(EventORM).order_by(EventORM.timestamp.asc()).all()
    ]


def get_events_after(db: Session, event_id: int) -> List[Event]:
    """
    Fetch events with id > event_id ordered by timestamp.
    Used by ProfileBuilder incremental update — only processes events not yet seen.
    """
    return [
        _orm_to_event(orm)
        for orm in db.query(EventORM)
        .filter(EventORM.id > event_id)
        .order_by(EventORM.timestamp.asc())
        .all()
    ]
