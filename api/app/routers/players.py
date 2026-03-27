import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.player import Player
from app.schemas.player import PlayerOut, PlayerCreate

router = APIRouter(prefix="/players", tags=["players"])

DB = Annotated[AsyncSession, Depends(get_db)]


@router.get("", response_model=list[PlayerOut])
async def list_players(
    db: DB,
    team_id: Annotated[uuid.UUID | None, Query()] = None,
):
    q = select(Player)
    if team_id:
        q = q.where(Player.team_id == team_id)
    result = await db.execute(q.order_by(Player.jersey_number.nullslast(), Player.name))
    return result.scalars().all()


@router.post("", response_model=PlayerOut, status_code=status.HTTP_201_CREATED)
async def create_player(body: PlayerCreate, db: DB):
    player = Player(**body.model_dump())
    db.add(player)
    await db.commit()
    await db.refresh(player)
    return player


@router.patch("/{player_id}", response_model=PlayerOut)
async def update_player(player_id: uuid.UUID, body: PlayerCreate, db: DB):
    player = await db.get(Player, player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(player, k, v)
    await db.commit()
    await db.refresh(player)
    return player
