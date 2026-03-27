from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Integer, String, Text

from app.db.database import Base


class EventORM(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    category = Column(String(32), nullable=False, index=True)
    sentiment = Column(Float, nullable=False)
    importance_score = Column(Float, nullable=False)
    description = Column(Text, nullable=False)
    source_raw = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
