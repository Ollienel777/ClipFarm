"""Celery tasks for async video processing."""
import logging
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_detection_modal(r2_key: str) -> list[dict]:
    """Call the Modal GPU function and return detections."""
    import modal
    detect_fn = modal.Function.from_name("clipfarm-detect", "detect_actions")
    return detect_fn.remote(r2_key)


def _run_detection_local(video_path: str) -> list[dict]:
    """Fallback: run detection locally (CPU, slow)."""
    from ml.pipeline.detect import run_detection
    return run_detection(video_path)


@celery_app.task(bind=True, name="process_game", max_retries=2, default_retry_delay=60)
def process_game_task(self, game_id: str, raw_video_url: str):
    """
    Main processing pipeline:
    1. Run ML detection via Modal GPU (or local fallback)
    2. Download video + generate clips with FFmpeg
    3. Upload clips to R2
    4. Persist clips to DB
    5. Update game status
    """
    from app.workers._sync_db import sync_set_game_status, sync_save_clips
    from app.services import storage as s3

    gid = uuid.UUID(game_id)
    r2_key = urlparse(raw_video_url).path.lstrip("/")
    logger.info("Starting processing for game %s", game_id)

    try:
        sync_set_game_status(gid, "processing")

        # ── 1. Run ML detection ───────────────────────────────────────────
        # Try Modal GPU first, fall back to local
        try:
            logger.info("Running detection via Modal GPU...")
            detections = _run_detection_modal(r2_key)
            logger.info("Modal returned %d detections", len(detections))
        except Exception as modal_err:
            logger.warning("Modal failed (%s), falling back to local detection", modal_err)
            # Need to download video for local detection
            with tempfile.TemporaryDirectory() as tmpdir:
                local_video = Path(tmpdir) / "game.mp4"
                s3.download_file(r2_key, local_video)
                detections = _run_detection_local(str(local_video))

        # ── 2. Download video + generate clips with FFmpeg ────────────────
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            local_video = tmp / "game.mp4"
            logger.info("Downloading key=%s from R2 for clip generation", r2_key)
            s3.download_file(r2_key, local_video)

            from ml.pipeline.clip import generate_clips
            clips_data = generate_clips(str(local_video), detections, tmp)

            # ── 3. Upload clips and thumbnails, save to DB ────────────────
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
