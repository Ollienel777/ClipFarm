import uuid
from typing import Annotated
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user_id
from app.database import get_db
from app.models.clip import Clip, ActionType
from app.models.correction import Correction
from app.models.player import Player
from app.schemas.clip import ClipOut, ClipTagRequest, ClipFixActionRequest
from app.services import storage

router = APIRouter(tags=["clips"])

DB = Annotated[AsyncSession, Depends(get_db)]

API_BASE = "http://localhost:8000"


def _rewrite_urls(clip: Clip) -> dict[str, str]:
    """Replace stored R2 URLs with our proxy endpoints."""
    return {
        "clip_url": f"{API_BASE}/media/clips/{clip.id}.mp4",
        "thumbnail_url": f"{API_BASE}/media/clips/{clip.id}/thumb.jpg" if clip.thumbnail_url else None,
    }


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
        urls = _rewrite_urls(c)
        d.clip_url = urls["clip_url"]
        d.thumbnail_url = urls["thumbnail_url"]
        out.append(d)
    return out


@router.get("/media/clips/{clip_id}.mp4")
async def stream_clip(clip_id: uuid.UUID, db: DB, request: Request):
    """Stream a clip video from R2 via the API (avoids public URL issues)."""
    clip = await db.get(Clip, clip_id)
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")
    key = urlparse(clip.clip_url).path.lstrip("/")
    client = storage._client()
    range_header = request.headers.get("range")

    if range_header:
        resp = client.get_object(
            Bucket=storage.settings.r2_bucket_name, Key=key, Range=range_header,
        )
        return StreamingResponse(
            resp["Body"].iter_chunks(),
            status_code=206,
            media_type="video/mp4",
            headers={
                "Content-Length": str(resp["ContentLength"]),
                "Content-Range": resp["ContentRange"],
                "Accept-Ranges": "bytes",
            },
        )

    resp = client.get_object(Bucket=storage.settings.r2_bucket_name, Key=key)
    return StreamingResponse(
        resp["Body"].iter_chunks(),
        media_type="video/mp4",
        headers={
            "Content-Length": str(resp["ContentLength"]),
            "Accept-Ranges": "bytes",
        },
    )


@router.get("/media/clips/{clip_id}/thumb.jpg")
async def stream_thumbnail(clip_id: uuid.UUID, db: DB):
    """Stream a clip thumbnail from R2 via the API."""
    clip = await db.get(Clip, clip_id)
    if not clip or not clip.thumbnail_url:
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    key = urlparse(clip.thumbnail_url).path.lstrip("/")
    try:
        resp = storage._client().get_object(Bucket=storage.settings.r2_bucket_name, Key=key)
    except Exception:
        raise HTTPException(status_code=404, detail="Thumbnail not found in storage")
    return StreamingResponse(
        resp["Body"].iter_chunks(),
        media_type="image/jpeg",
        headers={"Content-Length": str(resp["ContentLength"])},
    )


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


VALID_ACTIONS = {"spike", "serve", "dig", "set", "block", "not_an_action"}


@router.patch("/clips/{clip_id}/action", response_model=ClipOut)
async def fix_clip_action(
    clip_id: uuid.UUID,
    body: ClipFixActionRequest,
    db: DB,
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Let a user correct a clip's action type. Stores the correction as training data."""
    if body.action not in VALID_ACTIONS:
        raise HTTPException(status_code=400, detail=f"Invalid action. Must be one of: {VALID_ACTIONS}")

    clip = await db.get(Clip, clip_id)
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    # Save the correction as training data
    correction = Correction(
        clip_id=clip.id,
        user_id=user_id,
        original_action=clip.action_type,
        corrected_action=body.action,
        original_confidence=clip.confidence,
        start_time=clip.start_time,
        end_time=clip.end_time,
    )
    db.add(correction)

    # Update the clip's action type (or mark as hidden if "not_an_action")
    if body.action == "not_an_action":
        clip.action_type = ActionType.unknown
        clip.confidence = 0.0
    else:
        clip.action_type = ActionType(body.action)
        clip.confidence = 1.0  # User-verified = 100% confidence

    await db.commit()
    await db.refresh(clip)

    out = ClipOut.model_validate(clip)
    urls = _rewrite_urls(clip)
    out.clip_url = urls["clip_url"]
    out.thumbnail_url = urls["thumbnail_url"]
    return out


@router.get("/clips/{clip_id}/share")
async def share_clip(clip_id: uuid.UUID, db: DB):
    clip = await db.get(Clip, clip_id)
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")
    return {"url": f"{API_BASE}/media/clips/{clip.id}.mp4"}
