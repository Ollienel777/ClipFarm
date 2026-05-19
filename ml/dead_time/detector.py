"""Dead-time detection for volleyball videos.

Two-signal pipeline:
  1. Ball tracking (Roboflow): rally windows from contact trajectory physics.
  2. Pose estimation (YOLOv8): keypoint-based volleyball action classification.

A moment is dead when neither signal indicates active play.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# ── Pose inference config ─────────────────────────────────────────────────────
_POSE_INFER_SIZE = 960
_POSE_DETECT_CONF = 0.20
_POSE_KP_CONF = 0.25
_POSE_ACTION_CONF = 0.50  # minimum action confidence to count as "active"

# ── COCO 17-point keypoint indices ────────────────────────────────────────────
_NOSE = 0
_L_SHOULDER, _R_SHOULDER = 5, 6
_L_ELBOW, _R_ELBOW = 7, 8
_L_WRIST, _R_WRIST = 9, 10
_L_HIP, _R_HIP = 11, 12


@dataclass(slots=True)
class Sample:
    time: float
    motion: float
    pose_activity: float = 0.0
    ball_activity: float = 0.0


@dataclass(slots=True)
class Segment:
    start: float
    end: float
    score: float
    average_motion: float
    average_pose_activity: float = 0.0
    average_ball_activity: float = 0.0


# ── Pose helpers ──────────────────────────────────────────────────────────────

def _load_pose_model(model_name: str) -> Any | None:
    try:
        from ultralytics import YOLO
    except ImportError:
        logger.info("ultralytics not installed; running without pose inference")
        return None
    return YOLO(model_name)


def _classify_pose_action(
    kps: np.ndarray,
    confs: np.ndarray | None,
) -> tuple[str, float]:
    """
    Classify a volleyball action from one player's 17-point COCO keypoints.

    Ported from ball-track/annotate_pose.py — same heuristics used for annotation.
    Returns (action, confidence) where action ∈ {spike, serve, dig, set, block, unknown}.
    """
    def vis(i: int) -> bool:
        return confs is None or bool(confs[i] > _POSE_KP_CONF)

    def y(i: int) -> float:
        return float(kps[i][1])

    def x(i: int) -> float:
        return float(kps[i][0])

    if not (vis(_L_SHOULDER) and vis(_R_SHOULDER)):
        return "unknown", 0.0

    shoulder_y = (y(_L_SHOULDER) + y(_R_SHOULDER)) / 2
    hip_y = (
        (y(_L_HIP) + y(_R_HIP)) / 2
        if (vis(_L_HIP) and vis(_R_HIP))
        else shoulder_y + 50
    )
    body_h = abs(hip_y - shoulder_y) + 1e-6

    wrist_above = sum([
        vis(_L_WRIST) and y(_L_WRIST) < shoulder_y,
        vis(_R_WRIST) and y(_R_WRIST) < shoulder_y,
    ])

    if wrist_above >= 1:
        elbow_above = sum([
            vis(_L_ELBOW) and y(_L_ELBOW) < shoulder_y,
            vis(_R_ELBOW) and y(_R_ELBOW) < shoulder_y,
        ])
        if elbow_above >= 1 and wrist_above >= 2:
            return "spike", 0.85
        if elbow_above >= 1:
            return "spike", 0.65
        if wrist_above >= 2:
            return "serve", 0.60
        return "unknown", 0.0

    if (
        vis(_L_WRIST) and vis(_R_WRIST)
        and y(_L_WRIST) > hip_y + body_h * 0.2
        and y(_R_WRIST) > hip_y + body_h * 0.2
        and abs(x(_L_WRIST) - x(_R_WRIST)) < body_h * 0.4
    ):
        return "dig", 0.60

    face_y = y(_NOSE) if vis(_NOSE) else shoulder_y - 20
    if vis(_L_WRIST) and vis(_R_WRIST):
        if (
            abs(y(_L_WRIST) - face_y) < body_h * 0.25
            and abs(y(_R_WRIST) - face_y) < body_h * 0.25
            and abs(x(_L_WRIST) - x(_R_WRIST)) < body_h * 0.5
        ):
            return "set", 0.55

    if (
        vis(_L_WRIST) and vis(_R_WRIST)
        and vis(_L_ELBOW) and vis(_R_ELBOW)
        and y(_L_WRIST) < shoulder_y
        and y(_R_WRIST) < shoulder_y
        and y(_L_ELBOW) < shoulder_y
        and y(_R_ELBOW) < shoulder_y
        and abs(x(_L_WRIST) - x(_R_WRIST)) > body_h * 0.5
    ):
        return "block", 0.65

    return "unknown", 0.0


def _estimate_pose_activity(model: Any, frame: np.ndarray) -> float:
    """
    Run YOLOv8 pose on a frame; return fraction of court players in active volleyball poses.

    Active = classified as spike / serve / dig / set / block with conf >= _POSE_ACTION_CONF.
    Returns 0.0 when no court players are detected.
    """
    frame_h, frame_w = frame.shape[:2]
    court_x_left = frame_w * 0.08
    court_x_right = frame_w * 0.92
    min_box_h = frame_h * 0.07

    results = model(frame, conf=_POSE_DETECT_CONF, imgsz=_POSE_INFER_SIZE, verbose=False)

    active = 0
    total = 0

    for result in results:
        if result.keypoints is None:
            continue

        kps_all = result.keypoints.xy.cpu().numpy()
        conf_all = result.keypoints.conf.cpu().numpy() if result.keypoints.conf is not None else None
        boxes = result.boxes.xyxy.cpu().numpy() if result.boxes is not None else None

        for pi in range(len(kps_all)):
            if boxes is not None and pi < len(boxes):
                x1, y1, x2, y2 = boxes[pi]
                if (y2 - y1) < min_box_h:
                    continue
                box_cx = (x1 + x2) / 2
                if not (court_x_left <= box_cx <= court_x_right):
                    continue

            kps = kps_all[pi]
            confs = conf_all[pi] if conf_all is not None else None
            action, conf = _classify_pose_action(kps, confs)
            total += 1
            if action != "unknown" and conf >= _POSE_ACTION_CONF:
                active += 1

    return active / total if total > 0 else 0.0


# ── Ball tracking helpers ─────────────────────────────────────────────────────

def _ball_activity_score(
    sample_time: float,
    contacts: list[dict],
    rallies: list[dict],
) -> float:
    for rally in rallies:
        if rally["start"] <= sample_time <= rally["end"]:
            return 1.0

    if not contacts:
        return 0.0

    nearest = min(abs(sample_time - c["time"]) for c in contacts)
    return float(np.exp(-nearest / 2.5))


def _collect_ball_signals(
    video_path: str,
    duration: float,
    frame_height: int,
    api_key: str | None,
    sample_every: int,
) -> tuple[list[dict], list[dict]]:
    if not api_key:
        logger.info("ROBOFLOW_API_KEY not set; using pose and motion only")
        return [], []

    try:
        from ml.pipeline.ball import contacts_to_rallies, find_contacts, track_ball

        tracker = track_ball(video_path, api_key, sample_every=sample_every)
        contacts = find_contacts(tracker, frame_height=frame_height)
        rallies = contacts_to_rallies(contacts, duration, frame_height)
        logger.info("Ball signals: %d contacts → %d rally windows", len(contacts), len(rallies))
        return contacts, rallies
    except Exception:
        logger.exception("Ball tracking failed; continuing with pose and motion only")
        return [], []


# ── Scoring ───────────────────────────────────────────────────────────────────

def _motion_score(previous_gray: np.ndarray, current_gray: np.ndarray) -> float:
    diff = cv2.absdiff(previous_gray, current_gray)
    return float(np.mean(diff) / 255.0)


def _live_score(ball: float, pose: float, motion: float) -> float:
    """
    Combined liveness: how likely is this moment to be active play?

    Ball (Roboflow rally window) is primary — saturates the score inside a rally.
    Pose (YOLOv8 action classification) is strong secondary.
    Motion (frame diff) is a weak corroborating signal.

    Using max rather than weighted average prevents any single inactive signal
    from overriding a strong "live" signal from another source.
    """
    return float(np.clip(max(ball, 0.75 * pose, 0.30 * motion), 0.0, 1.0))


def _smooth(values: list[float], window_size: int) -> list[float]:
    if window_size <= 1 or len(values) <= 1:
        return list(values)

    kernel = np.ones(window_size, dtype=np.float32) / window_size
    padded = np.pad(values, (window_size // 2, window_size - 1 - window_size // 2), mode="edge")
    return np.convolve(padded, kernel, mode="valid").astype(float).tolist()


def _normalize(values: list[float]) -> list[float]:
    array = np.asarray(values, dtype=np.float32)
    if array.size == 0:
        return []

    low = float(np.percentile(array, 10))
    high = float(np.percentile(array, 90))
    if high - low < 1e-6:
        return [0.5 for _ in values]

    return np.clip((array - low) / (high - low), 0.0, 1.0).astype(float).tolist()


def _adaptive_threshold(values: list[float]) -> float:
    array = np.asarray(values, dtype=np.float32)
    if array.size == 0:
        return 0.0

    q25 = float(np.percentile(array, 25))
    q50 = float(np.percentile(array, 50))
    q75 = float(np.percentile(array, 75))
    spread = max(q75 - q25, 1e-6)

    return max(0.42, min(0.88, q50 + 0.30 * spread))


# ── Video sampling ────────────────────────────────────────────────────────────

def _sample_video(
    video_path: str,
    sample_stride: int,
    pose_model: Any | None,
    contacts: list[dict],
    rallies: list[dict],
) -> list[Sample]:
    capture = cv2.VideoCapture(video_path)
    if not capture.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")

    fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
    samples: list[Sample] = []
    previous_gray: np.ndarray | None = None
    frame_index = 0

    while True:
        ret, frame = capture.read()
        if not ret:
            break

        if frame_index % sample_stride != 0:
            frame_index += 1
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)

        motion = 0.0
        if previous_gray is not None:
            motion = _motion_score(previous_gray, gray)

        sample_time = frame_index / fps
        ball_activity = _ball_activity_score(sample_time, contacts, rallies)

        # Skip expensive pose inference when ball tracking already confirms a live rally.
        # Threshold of 0.85 means we're clearly inside a rally window (returns 1.0)
        # or very close to a contact (exp decay). This skips ~70% of pose calls
        # on a typical game with good Roboflow coverage.
        pose_activity = 0.0
        if pose_model is not None and ball_activity < 0.85:
            try:
                pose_activity = _estimate_pose_activity(pose_model, frame)
            except Exception:
                logger.exception("Pose estimation failed at frame %d", frame_index)

        samples.append(
            Sample(
                time=sample_time,
                motion=motion,
                pose_activity=pose_activity,
                ball_activity=ball_activity,
            )
        )

        previous_gray = gray
        frame_index += 1

    capture.release()
    return samples


# ── Segment building ──────────────────────────────────────────────────────────

def _make_segment(
    *,
    samples: list[Sample],
    smoothed_motion: list[float],
    smoothed_deadness: list[float],
    start: float,
    end: float,
    pad_seconds: float,
    duration: float,
) -> Segment:
    padded_start = max(0.0, start - pad_seconds)
    padded_end = min(duration, end + pad_seconds)

    indices = [i for i, s in enumerate(samples) if padded_start <= s.time <= padded_end]
    motion_values = [smoothed_motion[i] for i in indices]
    deadness_values = [smoothed_deadness[i] for i in indices]
    pose_values = [samples[i].pose_activity for i in indices]
    ball_values = [samples[i].ball_activity for i in indices]

    return Segment(
        start=padded_start,
        end=padded_end,
        score=float(np.mean(deadness_values)) if deadness_values else 0.0,
        average_motion=float(np.mean(motion_values)) if motion_values else 0.0,
        average_pose_activity=float(np.mean(pose_values)) if pose_values else 0.0,
        average_ball_activity=float(np.mean(ball_values)) if ball_values else 0.0,
    )


def _merge_or_append(segments: list[Segment], candidate: Segment, merge_gap_seconds: float) -> None:
    if segments and candidate.start - segments[-1].end <= merge_gap_seconds:
        prev = segments[-1]
        d_prev = max(prev.end - prev.start, 1e-6)
        d_cand = max(candidate.end - candidate.start, 1e-6)
        total = d_prev + d_cand

        segments[-1] = Segment(
            start=prev.start,
            end=max(prev.end, candidate.end),
            score=(prev.score * d_prev + candidate.score * d_cand) / total,
            average_motion=(prev.average_motion * d_prev + candidate.average_motion * d_cand) / total,
            average_pose_activity=(prev.average_pose_activity * d_prev + candidate.average_pose_activity * d_cand) / total,
            average_ball_activity=(prev.average_ball_activity * d_prev + candidate.average_ball_activity * d_cand) / total,
        )
        return

    segments.append(candidate)


def _build_dead_ranges(
    *,
    samples: list[Sample],
    smoothed_motion: list[float],
    smoothed_deadness: list[float],
    threshold: float,
    min_dead_seconds: float,
    merge_gap_seconds: float,
    pad_seconds: float,
    duration: float,
) -> list[Segment]:
    segments: list[Segment] = []
    if not samples:
        return segments

    dead_start: float | None = None

    for index, sample in enumerate(samples):
        is_dead = smoothed_deadness[index] >= threshold
        if is_dead and dead_start is None:
            dead_start = sample.time
        elif not is_dead and dead_start is not None:
            if sample.time - dead_start >= min_dead_seconds:
                seg = _make_segment(
                    samples=samples,
                    smoothed_motion=smoothed_motion,
                    smoothed_deadness=smoothed_deadness,
                    start=dead_start,
                    end=sample.time,
                    pad_seconds=pad_seconds,
                    duration=duration,
                )
                _merge_or_append(segments, seg, merge_gap_seconds)
            dead_start = None

    if dead_start is not None and duration - dead_start >= min_dead_seconds:
        seg = _make_segment(
            samples=samples,
            smoothed_motion=smoothed_motion,
            smoothed_deadness=smoothed_deadness,
            start=dead_start,
            end=duration,
            pad_seconds=pad_seconds,
            duration=duration,
        )
        _merge_or_append(segments, seg, merge_gap_seconds)

    return segments


# ── Public API ────────────────────────────────────────────────────────────────

def analyze_video(
    video_path: str | Path,
    *,
    sample_stride: int = 4,
    min_dead_seconds: float = 3.0,
    merge_gap_seconds: float = 1.0,
    pad_seconds: float = 0.75,
    threshold_override: float | None = None,
    ball_api_key: str | None = None,
    ball_sample_every: int = 10,
    pose_model_name: str = "yolov8n-pose.pt",
) -> dict[str, Any]:
    """Detect dead-time intervals in a volleyball video.

    Ball tracking (Roboflow) is the primary liveness signal — rally windows gate
    the score before pose is considered. YOLOv8 pose estimation catches active play
    missed by ball tracking (occluded ball, rapid serve) via volleyball action
    classification. Motion provides a weak tertiary signal.
    """
    video_path = str(video_path)
    if sample_stride <= 0:
        raise ValueError("sample_stride must be greater than zero")

    capture = cv2.VideoCapture(video_path)
    if not capture.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")

    fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 1
    duration = total_frames / fps if fps else 0.0
    capture.release()

    pose_model = _load_pose_model(pose_model_name)
    contacts, rallies = _collect_ball_signals(
        video_path=video_path,
        duration=duration,
        frame_height=frame_height,
        api_key=ball_api_key or os.environ.get("ROBOFLOW_API_KEY"),
        sample_every=ball_sample_every,
    )

    samples = _sample_video(
        video_path=video_path,
        sample_stride=sample_stride,
        pose_model=pose_model,
        contacts=contacts,
        rallies=rallies,
    )

    if not samples:
        return {
            "video": video_path,
            "fps": fps,
            "frames": total_frames,
            "duration": duration,
            "sample_stride": sample_stride,
            "threshold": 0.0,
            "ball_contacts": len(contacts),
            "ball_rallies": len(rallies),
            "segments": [],
        }

    smoothed_motion = _smooth([s.motion for s in samples], window_size=5)
    motion_normalized = _normalize(smoothed_motion)
    pose_activity = [s.pose_activity for s in samples]
    ball_activity = [s.ball_activity for s in samples]

    live_scores = [
        _live_score(ball_activity[i], pose_activity[i], motion_normalized[i])
        for i in range(len(samples))
    ]
    deadness = [1.0 - ls for ls in live_scores]
    smoothed_deadness = _smooth(deadness, window_size=5)
    threshold = threshold_override if threshold_override is not None else _adaptive_threshold(smoothed_deadness)

    dead_ranges = _build_dead_ranges(
        samples=samples,
        smoothed_motion=smoothed_motion,
        smoothed_deadness=smoothed_deadness,
        threshold=threshold,
        min_dead_seconds=min_dead_seconds,
        merge_gap_seconds=merge_gap_seconds,
        pad_seconds=pad_seconds,
        duration=duration,
    )

    return {
        "video": video_path,
        "fps": fps,
        "frames": total_frames,
        "duration": duration,
        "sample_stride": sample_stride,
        "threshold": round(threshold, 4),
        "ball_contacts": len(contacts),
        "ball_rallies": len(rallies),
        "segments": [
            {
                "start": round(seg.start, 3),
                "end": round(seg.end, 3),
                "score": round(seg.score, 4),
                "average_motion": round(seg.average_motion, 4),
                "average_pose_activity": round(seg.average_pose_activity, 3),
                "average_ball_activity": round(seg.average_ball_activity, 4),
            }
            for seg in dead_ranges
        ],
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Detect dead-time intervals in a volleyball video")
    parser.add_argument("video_path", help="Path to the input video")
    parser.add_argument("--sample-stride", type=int, default=4, help="Read every Nth frame (default: 4)")
    parser.add_argument("--min-dead-seconds", type=float, default=3.0, help="Minimum dead-time segment duration")
    parser.add_argument("--merge-gap-seconds", type=float, default=1.0, help="Merge nearby segments within this gap")
    parser.add_argument("--pad-seconds", type=float, default=0.75, help="Pad each segment on both sides")
    parser.add_argument("--threshold", type=float, default=None, help="Override the adaptive deadness threshold")
    parser.add_argument("--ball-api-key", type=str, default=None, help="Roboflow API key for ball tracking")
    parser.add_argument("--ball-sample-every", type=int, default=10, help="Run ball tracking every N frames")
    parser.add_argument("--pose-model", type=str, default="yolov8n-pose.pt", help="YOLOv8 pose model name")
    parser.add_argument("--output", type=str, default=None, help="Write JSON result to this path")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON to stdout")
    parser.add_argument("--log-level", default="INFO", help="Logging level")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))

    result = analyze_video(
        args.video_path,
        sample_stride=args.sample_stride,
        min_dead_seconds=args.min_dead_seconds,
        merge_gap_seconds=args.merge_gap_seconds,
        pad_seconds=args.pad_seconds,
        threshold_override=args.threshold,
        ball_api_key=args.ball_api_key,
        ball_sample_every=args.ball_sample_every,
        pose_model_name=args.pose_model,
    )

    payload = json.dumps(result, indent=2 if args.pretty else None)
    print(payload)

    if args.output:
        Path(args.output).write_text(payload + "\n", encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
