from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, Text

from app.db.database import Base


class UserProfileSnapshotORM(Base):
    __tablename__ = "profile_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    version = Column(Integer, nullable=False, index=True)
    event_count = Column(Integer, nullable=False)
    profile_json = Column(Text, nullable=False)   # serialized UserProfile
    state_json = Column(Text, nullable=False)      # serialized ProfileState (for incremental)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
