"""
Action detection pipeline.

Phase 1 (MVP): Rule-based heuristics on YOLOv8-pose skeleton keypoints.
Phase 2 (v1.1): Replace/augment with trained MLP/LSTM classifier.

Outputs a list of detections:
  [{"start": float, "end": float, "action": str, "confidence": float}, ...]
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import cv2
import numpy as np

logger = logging.getLogger(__name__)

ActionType = Literal["spike", "serve", "dig", "set", "block", "unknown"]

# YOLOv8 pose keypoint indices (COCO 17-point)
NOSE = 0
L_SHOULDER, R_SHOULDER = 5, 6
L_ELBOW, R_ELBOW = 7, 8
L_WRIST, R_WRIST = 9, 10
L_HIP, R_HIP = 11, 12
L_KNEE, R_KNEE = 13, 14
L_ANKLE, R_ANKLE = 15, 16

# ── Sliding window config ─────────────────────────────────────────────────────
WINDOW_FRAMES = 30   # 1 s @ 30 fps
STRIDE_FRAMES = 10   # 10-frame stride (3× overlap)
SKIP_FRAMES = 4      # Analyse every Nth frame for speed (4× speedup)

# Clip padding around detected peak
PAD_BEFORE = 2.0   # seconds
PAD_AFTER = 3.0    # seconds
MIN_CLIP_GAP = 1.5  # Merge detections closer than this (seconds)


@dataclass
class Detection:
    peak_time: float
    action: ActionType
    confidence: float
    start: float = field(init=False)
    end: float = field(init=False)

    def __post_init__(self):
        self.start = max(0.0, self.peak_time - PAD_BEFORE)
        self.end = self.peak_time + PAD_AFTER


def run_detection(video_path: str) -> list[dict]:
    """
    Run full detection pipeline on a video file.
    Returns list of {start, end, action, confidence} dicts.
    """
    try:
        from ultralytics import YOLO
        model = YOLO("yolov8n-pose.pt")  # Downloads automatically on first run
    except ImportError:
        logger.warning("ultralytics not installed — returning stub detections")
        return _stub_detections(video_path)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    logger.info("Video: %.1f fps, %d frames (%.0f s)", fps, total_frames, total_frames / fps)

    frame_detections: list[tuple[float, ActionType, float]] = []  # (time, action, conf)

    frame_idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % SKIP_FRAMES != 0:
            frame_idx += 1
            continue

        t = frame_idx / fps
        results = model(frame, verbose=False)

        for result in results:
            if result.keypoints is None:
                continue
            kps = result.keypoints.xy.cpu().numpy()  # (N, 17, 2)
            confs = result.keypoints.conf.cpu().numpy() if result.keypoints.conf is not None else None

            for person_idx in range(len(kps)):
                person_kps = kps[person_idx]  # (17, 2)
                person_conf = confs[person_idx] if confs is not None else None
                action, confidence = classify_action(person_kps, person_conf)
                if action != "unknown":
                    frame_detections.append((t, action, confidence))

        frame_idx += 1

    cap.release()
    logger.info("Raw detections: %d", len(frame_detections))

    detections = _merge_detections(frame_detections, total_frames / fps)
    logger.info("Merged detections: %d", len(detections))
    return [{"start": d.start, "end": d.end, "action": d.action, "confidence": d.confidence}
            for d in detections]


def classify_action(
    kps: np.ndarray,
    confs: np.ndarray | None,
    conf_threshold: float = 0.4,
) -> tuple[ActionType, float]:
    """
    Rule-based action classification from 17 COCO keypoints.

    Returns (action_type, confidence_estimate).
    """
    def visible(idx: int) -> bool:
        if confs is None:
            return True
        return bool(confs[idx] > conf_threshold)

    def y(idx: int) -> float:
        return float(kps[idx][1])

    def x(idx: int) -> float:
        return float(kps[idx][0])

    # Guard: need at least shoulders and wrists
    if not all(visible(i) for i in [L_SHOULDER, R_SHOULDER]):
        return "unknown", 0.0

    shoulder_y = (y(L_SHOULDER) + y(R_SHOULDER)) / 2
    hip_y = (y(L_HIP) + y(R_HIP)) / 2 if (visible(L_HIP) and visible(R_HIP)) else shoulder_y + 50

    body_height = abs(hip_y - shoulder_y) + 1e-6

    # ── Spike / serve heuristic ────────────────────────────────────────────────
    # One or both wrists are above the shoulder line
    wrist_above = 0
    if visible(L_WRIST) and y(L_WRIST) < shoulder_y:
        wrist_above += 1
    if visible(R_WRIST) and y(R_WRIST) < shoulder_y:
        wrist_above += 1

    if wrist_above >= 1:
        # Distinguish spike vs serve by elbow angle (rough heuristic)
        # Spike: arm extended upward (wrist above elbow above shoulder)
        elbow_above = 0
        if visible(L_ELBOW) and y(L_ELBOW) < shoulder_y:
            elbow_above += 1
        if visible(R_ELBOW) and y(R_ELBOW) < shoulder_y:
            elbow_above += 1

        if elbow_above >= 1:
            conf = min(0.6 + 0.2 * wrist_above, 0.9)
            return "spike", conf

        return "serve", 0.55

    # ── Dig heuristic ──────────────────────────────────────────────────────────
    # Both wrists below hip level (platform pass position)
    if (visible(L_WRIST) and visible(R_WRIST)
            and y(L_WRIST) > hip_y and y(R_WRIST) > hip_y):
        # Additional: wrists close together
        wrist_dist = abs(x(L_WRIST) - x(R_WRIST))
        if wrist_dist < body_height * 0.5:
            return "dig", 0.6

    # ── Set heuristic ──────────────────────────────────────────────────────────
    # Both hands near face level, slightly above shoulders
    face_y = y(NOSE) if visible(NOSE) else shoulder_y - 20
    if (visible(L_WRIST) and visible(R_WRIST)):
        lw_near_face = abs(y(L_WRIST) - face_y) < body_height * 0.3
        rw_near_face = abs(y(R_WRIST) - face_y) < body_height * 0.3
        wrist_spread = abs(x(L_WRIST) - x(R_WRIST))
        if lw_near_face and rw_near_face and wrist_spread < body_height * 0.6:
            return "set", 0.5

    # ── Block heuristic ───────────────────────────────────────────────────────
    # Both arms extended upward (both wrists AND elbows above shoulders)
    if (visible(L_WRIST) and visible(R_WRIST)
            and visible(L_ELBOW) and visible(R_ELBOW)
            and y(L_WRIST) < shoulder_y and y(R_WRIST) < shoulder_y
            and y(L_ELBOW) < shoulder_y and y(R_ELBOW) < shoulder_y):
        # Wrists spread wide (hands apart at net)
        wrist_spread = abs(x(L_WRIST) - x(R_WRIST))
        if wrist_spread > body_height * 0.5:
            return "block", 0.6

    return "unknown", 0.0


def _merge_detections(
    frame_dets: list[tuple[float, ActionType, float]],
    video_duration: float,
) -> list[Detection]:
    """Group nearby frame-level detections into single clips."""
    if not frame_dets:
        return []

    # Sort by time
    frame_dets.sort(key=lambda x: x[0])

    groups: list[list[tuple[float, ActionType, float]]] = []
    current_group: list[tuple[float, ActionType, float]] = [frame_dets[0]]

    for t, action, conf in frame_dets[1:]:
        if t - current_group[-1][0] <= MIN_CLIP_GAP:
            current_group.append((t, action, conf))
        else:
            groups.append(current_group)
            current_group = [(t, action, conf)]
    groups.append(current_group)

    detections = []
    for group in groups:
        # Pick dominant action by confidence
        action_scores: dict[str, float] = {}
        for _, action, conf in group:
            action_scores[action] = action_scores.get(action, 0) + conf

        best_action = max(action_scores, key=action_scores.__getitem__)  # type: ignore[arg-type]
        best_conf = min(action_scores[best_action] / len(group), 0.95)
        peak_time = max(group, key=lambda x: x[2])[0]

        d = Detection(peak_time=peak_time, action=best_action, confidence=best_conf)  # type: ignore[arg-type]
        d.end = min(d.end, video_duration)
        detections.append(d)

    return detections


def _stub_detections(video_path: str) -> list[dict]:
    """Fallback for environments without ultralytics (returns fake data for dev)."""
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    duration = total_frames / fps

    actions = ["spike", "serve", "dig", "set", "block"]
    # Generate ~10-15 clips max, spread across the video
    target_clips = min(15, max(3, int(duration / 60)))  # ~1 clip per minute, max 15
    interval = max(10, int(duration / target_clips))
    start_offset = min(5, duration * 0.05)
    return [
        {
            "start": max(0, t - 2),
            "end": min(duration, t + 3),
            "action": actions[i % len(actions)],
            "confidence": 0.75,
        }
        for i, t in enumerate(range(int(start_offset), max(int(start_offset) + 1, int(duration) - 2), interval))
    ]
