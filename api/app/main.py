from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import games, clips, players

app = FastAPI(title="ClipFarm API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(games.router)
app.include_router(clips.router)
app.include_router(players.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
