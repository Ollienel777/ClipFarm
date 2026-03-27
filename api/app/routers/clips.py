import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.clip import Clip, ActionType
from app.models.player import Player
from app.schemas.clip import ClipOut, ClipTagRequest

router = APIRouter(tags=["clips"])

DB = Annotated[AsyncSession, Depends(get_db)]


@router.get("/games/{game_id}/clips", response_model=list[ClipOut])
async def list_clips(
    game_id: uuid.UUID,
    db: DB,
    action_type: Annotated[str | None, Query()] = None,
    player_id: Annotated[uuid.UUID | None, Query()] = None,
    min_confidence: Annotated[float, Query(ge=0, le=1)] = 0.0,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
):
    q = select(Clip).where(Clip.game_id == game_id)

    if action_type:
        types = [ActionType(t.strip()) for t in action_type.split(",") if t.strip()]
        if types:
            q = q.where(Clip.action_type.in_(types))

    if player_id:
        q = q.where(Clip.player_id == player_id)

    if min_confidence > 0:
        q = q.where(Clip.confidence >= min_confidence)

    q = q.order_by(Clip.start_time).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    clips = result.scalars().all()

    # Attach player names
    player_ids = {c.player_id for c in clips if c.player_id}
    player_map: dict[uuid.UUID, str] = {}
    if player_ids:
        pr = await db.execute(select(Player).where(Player.id.in_(player_ids)))
        for p in pr.scalars():
            player_map[p.id] = p.name

    out = []
    for c in clips:
        d = ClipOut.model_validate(c)
        d.player_name = player_map.get(c.player_id) if c.player_id else None  # type: ignore[arg-type]
        out.append(d)
    return out


@router.patch("/clips/{clip_id}/tag", response_model=ClipOut)
async def tag_clip(clip_id: uuid.UUID, body: ClipTagRequest, db: DB):
    clip = await db.get(Clip, clip_id)
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    player = await db.get(Player, body.player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    clip.player_id = body.player_id
    await db.commit()
    await db.refresh(clip)

    out = ClipOut.model_validate(clip)
    out.player_name = player.name
    return out


@router.get("/clips/{clip_id}/share")
async def share_clip(clip_id: uuid.UUID, db: DB):
    clip = await db.get(Clip, clip_id)
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")
    # Return the direct clip URL as the share link
    return {"url": clip.clip_url}
