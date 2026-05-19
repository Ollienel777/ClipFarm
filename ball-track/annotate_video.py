"""
Ball detection + annotation using the Roboflow hosted inference API.

Frames are encoded as JPEG and POSTed to detect.roboflow.com — no local
model weights needed, works with any model architecture including RF-DETR.

Usage:
    python annotate_video.py [input] [output] [--start S] [--end E] [--fps F]

Examples:
    python annotate_video.py                              # uses defaults below
    python annotate_video.py game.mp4 out.mp4
    python annotate_video.py game.mp4 out.mp4 --start 60 --end 300
    python annotate_video.py game.mp4 out.mp4 --fps 5    # sample 5 frames/sec
"""
import argparse
import base64
import os
import time
import cv2
import numpy as np
import requests
from dotenv import load_dotenv

load_dotenv()

# ── Defaults (overridden by CLI args) ─────────────────────────────────────────
INPUT_VIDEO  = "test.MOV"
OUTPUT_VIDEO = "annotated_test.mp4"
API_KEY      = os.getenv("ROBOFLOW_API_KEY")
MODEL_ID     = "volleyball-ball-tracking-0eo7r/3"

SAMPLE_FPS   = 3      # inference samples per second
MIN_CONF     = 0.40   # ignore detections below this confidence
MAX_JUMP_PX  = 300    # max px a ball can move between sampled frames
MAX_MISS     = 5      # reset track after this many consecutive missed frames
# ─────────────────────────────────────────────────────────────────────────────

parser = argparse.ArgumentParser(description="Annotate ball detections in a video")
parser.add_argument("input",  nargs="?", default=INPUT_VIDEO,  help="Input video path")
parser.add_argument("output", nargs="?", default=OUTPUT_VIDEO, help="Output video path")
parser.add_argument("--start", type=float, default=None, metavar="S",
                    help="Start time in seconds (default: beginning)")
parser.add_argument("--end",   type=float, default=None, metavar="E",
                    help="End time in seconds (default: end of video)")
parser.add_argument("--fps",   type=float, default=SAMPLE_FPS, metavar="F",
                    help=f"Inference samples per second (default: {SAMPLE_FPS})")
args = parser.parse_args()

if not API_KEY:
    raise RuntimeError("Set ROBOFLOW_API_KEY in environment or .env file")


def infer_frame(frame: np.ndarray) -> list[dict]:
    """POST a frame to the Roboflow hosted API; return list of prediction dicts."""
    _, buf = cv2.imencode(".jpg", frame)
    img_b64 = base64.b64encode(buf).decode("utf-8")
    r = requests.post(
        f"https://detect.roboflow.com/{MODEL_ID}",
        params={"api_key": API_KEY, "confidence": int(MIN_CONF * 100)},
        data=img_b64,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json().get("predictions", [])


cap = cv2.VideoCapture(args.input)
if not cap.isOpened():
    raise FileNotFoundError(f"Could not open video: {args.input}")

native_fps    = cap.get(cv2.CAP_PROP_FPS)
total_frames  = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
width         = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height        = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
duration_s    = total_frames / native_fps

# ── Resolve start / end frames ────────────────────────────────────────────────
start_s = args.start if args.start is not None else 0.0
end_s   = args.end   if args.end   is not None else duration_s

start_s = max(0.0, min(start_s, duration_s))
end_s   = max(start_s, min(end_s, duration_s))

start_frame   = int(start_s * native_fps)
end_frame     = int(end_s   * native_fps)
window_frames = end_frame - start_frame
sample_stride = max(1, round(native_fps / args.fps))

print(f"Video  : {width}x{height} @ {native_fps:.1f}fps | {duration_s:.1f}s | {total_frames} frames")
print(f"Window : {start_s:.1f}s – {end_s:.1f}s  ({window_frames} frames)")
print(f"Sample : {args.fps:.1f} fps  (every {sample_stride} frames, "
      f"~{window_frames // sample_stride} inferences)")
print(f"Output : {args.output}\n")

if start_frame > 0:
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

fourcc = cv2.VideoWriter_fourcc(*"mp4v")
out    = cv2.VideoWriter(args.output, fourcc, native_fps, (width, height))

frame_idx = start_frame
written   = 0
detected  = 0
misses    = 0
last_x: float | None = None
last_y: float | None = None
t_start   = time.time()

while frame_idx < end_frame:
    ret, frame = cap.read()
    if not ret:
        break

    if frame_idx % sample_stride == 0:
        try:
            preds = infer_frame(frame)
        except Exception as e:
            print(f"  {frame_idx / native_fps:7.2f}s  f{frame_idx:6d} | API error: {e}")
            preds = []

        preds = sorted(preds, key=lambda p: p["confidence"], reverse=True)

        best = None
        if preds:
            if last_x is None:
                best = preds[0]
            else:
                closest = min(preds, key=lambda p: np.hypot(p["x"] - last_x, p["y"] - last_y))
                if np.hypot(closest["x"] - last_x, closest["y"] - last_y) <= MAX_JUMP_PX:
                    best = closest

        if best:
            detected += 1
            misses = 0
            last_x, last_y = best["x"], best["y"]
            x1 = int(best["x"] - best["width"]  / 2)
            y1 = int(best["y"] - best["height"] / 2)
            x2 = int(best["x"] + best["width"]  / 2)
            y2 = int(best["y"] + best["height"] / 2)
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(frame, f"{best['confidence']:.2f}", (x1, y1 - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            print(f"  {frame_idx / native_fps:7.2f}s  f{frame_idx:6d} | "
                  f"ball at ({best['x']:.0f}, {best['y']:.0f}) | conf {best['confidence']:.2f}")
        else:
            misses += 1
            if misses >= MAX_MISS:
                last_x = last_y = None
                misses = 0
            print(f"  {frame_idx / native_fps:7.2f}s  f{frame_idx:6d} | no detection")

    out.write(frame)
    written += 1
    frame_idx += 1

cap.release()
out.release()

sampled = window_frames // sample_stride
elapsed = time.time() - t_start
print(f"\nDone in {elapsed:.1f}s | {written} frames written -> {args.output}")
print(f"Detected ball in {detected}/{sampled} sampled frames "
      f"({100 * detected / max(sampled, 1):.0f}%)")
