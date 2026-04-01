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
from app.models.game import Game
from app.schemas.clip import ClipOut, ClipTagRequest, ClipLabelsRequest, ClipTrimRequest
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


VALID_LABELS = {"spike", "serve", "dig", "set", "block", "not_an_action"}


@router.patch("/clips/{clip_id}/labels", response_model=ClipOut)
async def update_clip_labels(
    clip_id: uuid.UUID,
    body: ClipLabelsRequest,
    db: DB,
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Set up to 2 action labels on a clip. Saves correction as ML training data."""
    invalid = set(body.labels) - VALID_LABELS
    if invalid:
        raise HTTPException(status_code=400, detail=f"Invalid labels: {invalid}. Must be from: {VALID_LABELS}")

    clean_labels = [l for l in body.labels if l != "not_an_action"]
    if len(clean_labels) > 2:
        raise HTTPException(status_code=400, detail="Maximum 2 action labels per clip")

    clip = await db.get(Clip, clip_id)
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    # Determine labels for correction record (preserve user selection order)
    user_labels = body.labels
    label_1 = user_labels[0] if len(user_labels) > 0 else "not_an_action"
    label_2 = user_labels[1] if len(user_labels) > 1 else None

    # Save correction as ML training data
    correction = Correction(
        clip_id=clip.id,
        user_id=user_id,
        original_action=clip.action_type,
        corrected_label_1=label_1,
        corrected_label_2=label_2,
        original_confidence=clip.confidence,
        start_time=clip.start_time,
        end_time=clip.end_time,
    )
    db.add(correction)

    # Update labels on clip
    clip.labels = list(set(clean_labels))

    # Update primary action type based on labels
    if "not_an_action" in body.labels or not clean_labels:
        clip.action_type = ActionType.unknown
        clip.confidence = 0.0
    else:
        clip.action_type = ActionType(clean_labels[0])
        clip.confidence = 1.0

    await db.commit()
    await db.refresh(clip)

    out = ClipOut.model_validate(clip)
    urls = _rewrite_urls(clip)
    out.clip_url = urls["clip_url"]
    out.thumbnail_url = urls["thumbnail_url"]
    return out


TRIM_STEP = 2.0  # seconds
MAX_CLIP_DURATION = 30.0
MIN_CLIP_DURATION = 1.0


@router.patch("/clips/{clip_id}/trim", response_model=ClipOut)
async def trim_clip(
    clip_id: uuid.UUID,
    body: ClipTrimRequest,
    db: DB,
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """
    Adjust a clip's start/end time and re-cut the video from the source.

    start_delta: negative = extend earlier, positive = shrink from start
    end_delta:   positive = extend later, negative = shrink from end
    """
    clip = await db.get(Clip, clip_id)
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    game = await db.get(Game, clip.game_id)
    if not game or not game.raw_video_url:
        raise HTTPException(status_code=400, detail="Source video not available for trimming")

    new_start = max(0, clip.start_time + body.start_delta)
    new_end = clip.end_time + body.end_delta
    if new_end <= new_start:
        raise HTTPException(status_code=400, detail="End time must be after start time")

    duration = new_end - new_start
    if duration < MIN_CLIP_DURATION:
        raise HTTPException(status_code=400, detail=f"Clip too short (min {MIN_CLIP_DURATION}s)")
    if duration > MAX_CLIP_DURATION:
        raise HTTPException(status_code=400, detail=f"Clip too long (max {MAX_CLIP_DURATION}s)")

    # Update times in DB
    clip.start_time = new_start
    clip.end_time = new_end
    await db.commit()
    await db.refresh(clip)

    # Kick off background re-cut via Celery
    from app.workers.celery_app import celery_app
    celery_app.send_task(
        "recut_clip",
        args=[str(clip.id), str(clip.game_id), game.raw_video_url, new_start, new_end],
    )

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
