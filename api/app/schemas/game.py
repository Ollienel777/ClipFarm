import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.game import GameStatus


class GameOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    status: GameStatus
    created_at: datetime
    clip_count: int | None = None


class GameCreate(BaseModel):
    title: str
