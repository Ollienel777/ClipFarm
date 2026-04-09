import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, String, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DeadTimeRunStatus(str, enum.Enum):
    queued = "queued"
    processing = "processing"
    ready = "ready"
    failed = "failed"


class DeadTimeRun(Base):
    __tablename__ = "dead_time_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[DeadTimeRunStatus] = mapped_column(
        SAEnum(DeadTimeRunStatus),
        default=DeadTimeRunStatus.queued,
        nullable=False,
    )
    raw_video_url: Mapped[str | None] = mapped_column(String(2048))
    error_message: Mapped[str | None] = mapped_column(String(1024))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    clips: Mapped[list["DeadTimeClip"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class DeadTimeClip(Base):
    __tablename__ = "dead_time_clips"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("dead_time_runs.id", ondelete="CASCADE"), nullable=False
    )
    start_time: Mapped[float] = mapped_column(Float, nullable=False)
    end_time: Mapped[float] = mapped_column(Float, nullable=False)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    clip_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    thumbnail_url: Mapped[str | None] = mapped_column(String(2048))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    run: Mapped[DeadTimeRun] = relationship(back_populates="clips")
