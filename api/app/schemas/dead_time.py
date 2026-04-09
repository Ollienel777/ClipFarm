import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.dead_time import DeadTimeRunStatus


class DeadTimeRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    status: DeadTimeRunStatus
    created_at: datetime
    clip_count: int | None = None


class DeadTimeClipOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    run_id: uuid.UUID
    start_time: float
    end_time: float
    score: float
    clip_url: str
    thumbnail_url: str | None
    created_at: datetime
