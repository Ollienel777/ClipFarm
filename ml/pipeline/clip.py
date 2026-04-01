"""
FFmpeg clip extraction and thumbnail generation.

For each detection dict {start, end, action, confidence},
cuts the clip from the source video and extracts a thumbnail
at the midpoint.
"""
from __future__ import annotations

import logging
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)


def generate_clips(
    video_path: str,
    detections: list[dict],
    output_dir: Path,
) -> list[dict]:
    """
    Cut clips and extract thumbnails for each detection.

    Returns extended detection dicts with keys:
      clip_path, thumb_path (may be None on failure)
    """
    try:
        import ffmpeg
    except ImportError:
        logger.warning("ffmpeg-python not installed — skipping clip generation")
        return []

    results = []
    for det in detections:
        clip_id = uuid.uuid4()
        clip_path = output_dir / f"{clip_id}.mp4"
        thumb_path = output_dir / f"{clip_id}.jpg"

        start = det["start"]
        duration = det["end"] - det["start"]
        mid = start + duration / 2

        # ── Cut clip ──────────────────────────────────────────────────────────
        try:
            (
                ffmpeg
                .input(video_path, ss=start, t=duration)
                .output(
                    str(clip_path),
                    vcodec="copy",
                    acodec="copy",
                    movflags="+faststart",
                    loglevel="error",
                )
                .overwrite_output()
                .run()
            )
        except Exception:
            logger.exception("Failed to cut clip for detection at %.1f", start)
            continue

        # ── Extract thumbnail ─────────────────────────────────────────────────
        thumb_ok = False
        try:
            (
                ffmpeg
                .input(video_path, ss=mid)
                .output(str(thumb_path), vframes=1, loglevel="error")
                .overwrite_output()
                .run()
            )
            thumb_ok = True
        except Exception:
            logger.warning("Thumbnail extraction failed for clip at %.1f", mid)

        results.append({
            **det,
            "clip_path": clip_path,
            "thumb_path": thumb_path if thumb_ok else None,
        })

    return results


def recut_single(
    video_path: str,
    start: float,
    end: float,
    output_dir: Path,
) -> tuple[Path, Path | None]:
    """
    Re-cut a single clip from the source video.
    Returns (clip_path, thumb_path or None).
    """
    import ffmpeg

    clip_path = output_dir / "recut.mp4"
    thumb_path = output_dir / "recut.jpg"
    duration = end - start
    mid = start + duration / 2

    (
        ffmpeg
        .input(video_path, ss=start, t=duration)
        .output(
            str(clip_path),
            vcodec="copy",
            acodec="copy",
            movflags="+faststart",
            loglevel="error",
        )
        .overwrite_output()
        .run()
    )

    thumb_ok = False
    try:
        (
            ffmpeg
            .input(video_path, ss=mid)
            .output(str(thumb_path), vframes=1, loglevel="error")
            .overwrite_output()
            .run()
        )
        thumb_ok = True
    except Exception:
        logger.warning("Thumbnail extraction failed for recut at %.1f", mid)

    return clip_path, thumb_path if thumb_ok else None
