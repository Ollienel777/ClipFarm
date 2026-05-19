"""
Annotate a video with ball positions from a ball_track.json file.

No API calls — reads pre-computed positions produced by track_ball.py.

Usage:
    python annotate_video.py <video> <ball_track.json> [output] [--start S] [--end E]

Examples:
    python annotate_video.py game.mp4 game_ball_track.json
    python annotate_video.py game.mp4 game_ball_track.json out.mp4
    python annotate_video.py game.mp4 game_ball_track.json out.mp4 --start 60 --end 120
"""
import argparse
import json
from pathlib import Path

import cv2

parser = argparse.ArgumentParser(description="Annotate video with pre-computed ball track")
parser.add_argument("video",      help="Input video path")
parser.add_argument("track",      help="ball_track.json from track_ball.py")
parser.add_argument("output",     nargs="?", default=None,
                    help="Output video path (default: <video_stem>_annotated.mp4)")
parser.add_argument("--start",    type=float, default=None, metavar="S",
                    help="Start time in seconds (default: from track file)")
parser.add_argument("--end",      type=float, default=None, metavar="E",
                    help="End time in seconds (default: from track file)")
args = parser.parse_args()

track = json.loads(Path(args.track).read_text(encoding="utf-8"))

# Build frame-index lookup for fast access
frame_lookup: dict[int, dict] = {
    d["frame"]: d for d in track["detections"] if d["tracked"]
}

cap = cv2.VideoCapture(args.video)
if not cap.isOpened():
    raise FileNotFoundError(f"Cannot open video: {args.video}")

native_fps    = cap.get(cv2.CAP_PROP_FPS)
total_frames  = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
width         = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height        = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
duration_s    = total_frames / native_fps

start_s = args.start if args.start is not None else track.get("start", 0.0)
end_s   = args.end   if args.end   is not None else track.get("end",   duration_s)
start_s = max(0.0, min(start_s, duration_s))
end_s   = max(start_s, min(end_s, duration_s))

start_frame = int(start_s * native_fps)
end_frame   = int(end_s   * native_fps)

output_path = args.output or str(Path(args.video).stem) + "_annotated.mp4"

tracked_in_window = sum(
    1 for d in track["detections"]
    if d["tracked"] and start_frame <= d["frame"] < end_frame
)

print(f"Video   : {args.video}  ({width}x{height} @ {native_fps:.1f}fps)")
print(f"Track   : {args.track}  (model: {track.get('model', 'unknown')})")
print(f"Window  : {start_s:.1f}s – {end_s:.1f}s")
print(f"Balls   : {tracked_in_window} tracked detections in window")
print(f"Output  : {output_path}\n")

if start_frame > 0:
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

fourcc = cv2.VideoWriter_fourcc(*"mp4v")
out    = cv2.VideoWriter(output_path, fourcc, native_fps, (width, height))

frame_idx = start_frame
written   = 0

while frame_idx < end_frame:
    ret, frame = cap.read()
    if not ret:
        break

    det = frame_lookup.get(frame_idx)
    if det is not None:
        x, y = det["x"], det["y"]
        w, h = det.get("width", 30), det.get("height", 30)
        x1, y1 = int(x - w / 2), int(y - h / 2)
        x2, y2 = int(x + w / 2), int(y + h / 2)
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(frame, f"{det['confidence']:.2f}", (x1, y1 - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    # Timestamp overlay on every frame
    t = frame_idx / native_fps
    cv2.putText(frame, f"{t:.2f}s", (10, 24),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1, cv2.LINE_AA)

    out.write(frame)
    written += 1
    frame_idx += 1

cap.release()
out.release()
print(f"Done — {written} frames written → {output_path}")
