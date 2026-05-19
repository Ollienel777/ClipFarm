"""
Ball tracking via Roboflow hosted inference API.

Runs detection on sampled frames, applies trajectory filtering, and writes a
ball_track.json with per-frame positions.  The JSON can then be fed to
annotate_video.py or to the dead-time / rally pipeline without re-running
the API.

Usage:
    python track_ball.py <video> [output.json] [options]

Examples:
    python track_ball.py game.mp4
    python track_ball.py game.mp4 game_track.json
    python track_ball.py game.mp4 --start 60 --end 300 --fps 5
"""
import argparse
import base64
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
import requests
from dotenv import load_dotenv

load_dotenv()

# ── Defaults ──────────────────────────────────────────────────────────────────
MODEL_ID    = "volleyball-ball-tracking-0eo7r/3"
SAMPLE_FPS  = 3      # inference samples per second
MIN_CONF    = 0.40
MAX_JUMP_PX = 300    # max px ball can move between sampled frames
MAX_MISS    = 5      # consecutive misses before track is reset
# ─────────────────────────────────────────────────────────────────────────────

parser = argparse.ArgumentParser(description="Track ball via Roboflow API and save positions to JSON")
parser.add_argument("video",  help="Input video path")
parser.add_argument("output", nargs="?", default=None,
                    help="Output JSON path (default: <video_stem>_ball_track.json)")
parser.add_argument("--start",    type=float, default=None, metavar="S",
                    help="Start time in seconds (default: beginning)")
parser.add_argument("--end",      type=float, default=None, metavar="E",
                    help="End time in seconds (default: end of video)")
parser.add_argument("--fps",      type=float, default=SAMPLE_FPS, metavar="F",
                    help=f"Inference samples per second (default: {SAMPLE_FPS})")
parser.add_argument("--min-conf", type=float, default=MIN_CONF, metavar="C",
                    help=f"Minimum detection confidence (default: {MIN_CONF})")
parser.add_argument("--model",    type=str,   default=MODEL_ID,
                    help=f"Roboflow model ID (default: {MODEL_ID})")
parser.add_argument("--api-key",  type=str,   default=None,
                    help="Roboflow API key (default: ROBOFLOW_API_KEY env var)")
args = parser.parse_args()

api_key = args.api_key or os.getenv("ROBOFLOW_API_KEY")
if not api_key:
    raise RuntimeError("Set ROBOFLOW_API_KEY in environment or pass --api-key")

output_path = args.output or str(Path(args.video).stem) + "_ball_track.json"


def _infer(frame: np.ndarray) -> list[dict]:
    """POST a frame to the Roboflow hosted API; return raw predictions."""
    _, buf = cv2.imencode(".jpg", frame)
    r = requests.post(
        f"https://detect.roboflow.com/{args.model}",
        params={"api_key": api_key, "confidence": int(args.min_conf * 100)},
        data=base64.b64encode(buf).decode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json().get("predictions", [])


cap = cv2.VideoCapture(args.video)
if not cap.isOpened():
    raise FileNotFoundError(f"Cannot open video: {args.video}")

native_fps    = cap.get(cv2.CAP_PROP_FPS)
total_frames  = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
duration_s    = total_frames / native_fps

start_s = max(0.0, min(args.start or 0.0, duration_s))
end_s   = max(start_s, min(args.end or duration_s, duration_s))

start_frame   = int(start_s * native_fps)
end_frame     = int(end_s   * native_fps)
window_frames = end_frame - start_frame
sample_stride = max(1, round(native_fps / args.fps))

print(f"Video    : {args.video}")
print(f"Window   : {start_s:.1f}s – {end_s:.1f}s  ({window_frames} frames)")
print(f"Sampling : {args.fps:.1f} fps → every {sample_stride} frames "
      f"(~{window_frames // sample_stride} API calls)")
print(f"Output   : {output_path}\n")

if start_frame > 0:
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

frame_idx = start_frame
last_x: float | None = None
last_y: float | None = None
misses  = 0
detections: list[dict] = []
t_start = time.time()

while frame_idx < end_frame:
    ret, frame = cap.read()
    if not ret:
        break

    if frame_idx % sample_stride == 0:
        sample_time = frame_idx / native_fps
        try:
            preds = sorted(_infer(frame), key=lambda p: p["confidence"], reverse=True)
        except Exception as e:
            print(f"  {sample_time:7.2f}s  f{frame_idx:6d} | API error: {e}")
            preds = []

        best = None
        if preds:
            if last_x is None:
                best = preds[0]
            else:
                closest = min(preds, key=lambda p: np.hypot(p["x"] - last_x, p["y"] - last_y))
                if np.hypot(closest["x"] - last_x, closest["y"] - last_y) <= MAX_JUMP_PX:
                    best = closest

        if best:
            misses = 0
            last_x, last_y = best["x"], best["y"]
            detections.append({
                "frame":      frame_idx,
                "time":       round(sample_time, 4),
                "x":          round(best["x"], 2),
                "y":          round(best["y"], 2),
                "width":      round(best["width"], 2),
                "height":     round(best["height"], 2),
                "confidence": round(best["confidence"], 4),
                "tracked":    True,
            })
            print(f"  {sample_time:7.2f}s  f{frame_idx:6d} | "
                  f"ball ({best['x']:.0f}, {best['y']:.0f})  conf {best['confidence']:.2f}")
        else:
            misses += 1
            if misses >= MAX_MISS:
                last_x = last_y = None
                misses = 0
            detections.append({
                "frame":      frame_idx,
                "time":       round(sample_time, 4),
                "x":          None,
                "y":          None,
                "width":      None,
                "height":     None,
                "confidence": None,
                "tracked":    False,
            })
            print(f"  {sample_time:7.2f}s  f{frame_idx:6d} | no detection")

    frame_idx += 1

cap.release()

tracked = sum(1 for d in detections if d["tracked"])
elapsed = time.time() - t_start
print(f"\nDone in {elapsed:.1f}s | tracked {tracked}/{len(detections)} sampled frames "
      f"({100 * tracked / max(len(detections), 1):.0f}%)")

payload = {
    "video":         args.video,
    "model":         args.model,
    "fps":           native_fps,
    "total_frames":  total_frames,
    "duration":      round(duration_s, 3),
    "start":         start_s,
    "end":           end_s,
    "sample_fps":    args.fps,
    "sample_stride": sample_stride,
    "min_confidence": args.min_conf,
    "created_at":    datetime.now(timezone.utc).isoformat(),
    "detections":    detections,
}

Path(output_path).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
print(f"Saved → {output_path}")
