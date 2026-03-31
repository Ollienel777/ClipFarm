import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.clip import ActionType


class ClipOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    game_id: uuid.UUID
    player_id: uuid.UUID | None
    player_name: str | None = None
    action_type: ActionType
    confidence: float
    start_time: float
    end_time: float
    clip_url: str
    thumbnail_url: str | None
    created_at: datetime


class ClipTagRequest(BaseModel):
    player_id: uuid.UUID


class ClipFixActionRequest(BaseModel):
    action: str  # spike, serve, dig, set, block, not_an_action
