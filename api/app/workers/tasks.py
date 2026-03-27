"""Celery tasks for async video processing."""
import logging
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="process_game", max_retries=2, default_retry_delay=60)
def process_game_task(self, game_id: str, raw_video_url: str):
    """
    Main processing pipeline:
    1. Download raw video from storage
    2. Run ML detection (via Modal or local)
    3. Generate clips with FFmpeg
    4. Persist clips to DB
    5. Update game status
    """
    from app.workers._sync_db import sync_get_game, sync_set_game_status, sync_save_clips
    from app.services import storage as s3

    gid = uuid.UUID(game_id)
    logger.info("Starting processing for game %s", game_id)

    try:
        sync_set_game_status(gid, "processing")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)

            # ── 1. Download video ──────────────────────────────────────────────
            local_video = tmp / "game.mp4"
            logger.info("Downloading %s", raw_video_url)
            with httpx.stream("GET", raw_video_url) as r:
                r.raise_for_status()
                with open(local_video, "wb") as f:
                    for chunk in r.iter_bytes():
                        f.write(chunk)

            # ── 2. Run ML detection ────────────────────────────────────────────
            from ml.pipeline.detect import run_detection
            detections = run_detection(str(local_video))
            # detections: list[{start, end, action, confidence}]

            # ── 3. Generate clips ──────────────────────────────────────────────
            from ml.pipeline.clip import generate_clips
            clips_data = generate_clips(str(local_video), detections, tmp)

            # ── 4. Upload clips and thumbnails, save to DB ─────────────────────
            rows = []
            for cd in clips_data:
                clip_id = uuid.uuid4()
                clip_url = s3.upload_file(
                    cd["clip_path"],
                    s3.clip_key(gid, clip_id),
                    "video/mp4",
                )
                thumb_url = None
                if cd.get("thumb_path"):
                    thumb_url = s3.upload_file(
                        cd["thumb_path"],
                        s3.thumbnail_key(gid, clip_id),
                        "image/jpeg",
                    )
                rows.append({
                    "id": clip_id,
                    "game_id": gid,
                    "action_type": cd["action"],
                    "confidence": cd["confidence"],
                    "start_time": cd["start"],
                    "end_time": cd["end"],
                    "clip_url": clip_url,
                    "thumbnail_url": thumb_url,
                })

            sync_save_clips(rows)
            sync_set_game_status(gid, "ready", processed_at=datetime.now(timezone.utc))
            logger.info("Done: %d clips for game %s", len(rows), game_id)

    except Exception as exc:
        logger.exception("Processing failed for game %s", game_id)
        sync_set_game_status(gid, "failed", error_message=str(exc))
        raise self.retry(exc=exc)
