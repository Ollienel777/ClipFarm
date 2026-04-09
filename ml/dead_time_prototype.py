"""Dead-time detection prototype for volleyball videos.

This module is intentionally separate from the action detection pipeline.
It estimates low-activity intervals using frame-to-frame motion, with optional
pose metadata when `ultralytics` is installed.
"""
from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class Sample:
    time: float
    motion: float
    pose_count: int = 0
    pose_confidence: float = 0.0


@dataclass(slots=True)
class Segment:
    start: float
    end: float
    score: float
    average_motion: float
    average_pose_count: float = 0.0


def _load_pose_model() -> Any | None:
    try:
        from importlib import import_module
    except ImportError:
        logger.info("ultralytics not installed; running motion-only dead-time detection")
        return None

    ultralytics_module = import_module("ultralytics")
    return ultralytics_module.YOLO("yolov8n-pose.pt")


def _motion_score(previous_gray: np.ndarray, current_gray: np.ndarray) -> float:
    diff = cv2.absdiff(previous_gray, current_gray)
    return float(np.mean(diff) / 255.0)


def _estimate_pose_metadata(model: Any, frame: np.ndarray) -> tuple[int, float]:
    results = model(frame, verbose=False)

    pose_count = 0
    confidence_sum = 0.0
    confidence_count = 0

    for result in results:
        if result.keypoints is None:
            continue

        keypoints = result.keypoints
        pose_count += len(keypoints.xy)

        if keypoints.conf is not None:
            conf_array = keypoints.conf.cpu().numpy()
            confidence_sum += float(np.sum(conf_array))
            confidence_count += int(conf_array.size)

    confidence = confidence_sum / confidence_count if confidence_count else 0.0
    return pose_count, confidence


def analyze_video(
    video_path: str | Path,
    *,
    sample_stride: int = 4,
    min_dead_seconds: float = 3.0,
    merge_gap_seconds: float = 1.0,
    pad_seconds: float = 0.75,
    threshold_override: float | None = None,
) -> dict[str, Any]:
    """Detect dead-time intervals in a volleyball video.

    The prototype uses a simple motion-based activity score and turns sustained
    low-motion runs into dead-time segments.
    """
    video_path = str(video_path)
    pose_model = _load_pose_model()

    capture = cv2.VideoCapture(video_path)
    if not capture.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")

    fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps if fps else 0.0

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

        pose_count = 0
        pose_confidence = 0.0
        if pose_model is not None:
            try:
                pose_count, pose_confidence = _estimate_pose_metadata(pose_model, frame)
            except Exception:
                logger.exception("Pose metadata estimation failed at frame %d", frame_index)

        samples.append(
            Sample(
                time=frame_index / fps,
                motion=motion,
                pose_count=pose_count,
                pose_confidence=pose_confidence,
            )
        )

        previous_gray = gray
        frame_index += 1

    capture.release()

    if not samples:
        return {
            "video": video_path,
            "duration": duration,
            "threshold": 0.0,
            "segments": [],
        }

    smoothed_motion = _smooth([sample.motion for sample in samples], window_size=5)
    threshold = threshold_override if threshold_override is not None else _adaptive_threshold(smoothed_motion)

    inactive_ranges = _build_inactive_ranges(
        samples=samples,
        smoothed_motion=smoothed_motion,
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
        "threshold": threshold,
        "segments": [
            {
                "start": round(segment.start, 3),
                "end": round(segment.end, 3),
                "score": round(segment.score, 4),
                "average_motion": round(segment.average_motion, 4),
                "average_pose_count": round(segment.average_pose_count, 3),
            }
            for segment in inactive_ranges
        ],
    }


def _smooth(values: list[float], window_size: int) -> list[float]:
    if window_size <= 1 or len(values) <= 1:
        return list(values)

    kernel = np.ones(window_size, dtype=np.float32) / window_size
    padded = np.pad(values, (window_size // 2, window_size - 1 - window_size // 2), mode="edge")
    return np.convolve(padded, kernel, mode="valid").astype(float).tolist()


def _adaptive_threshold(values: list[float]) -> float:
    array = np.asarray(values, dtype=np.float32)
    if array.size == 0:
        return 0.0

    q25 = float(np.percentile(array, 25))
    q50 = float(np.percentile(array, 50))
    q75 = float(np.percentile(array, 75))
    spread = max(q75 - q25, 1e-6)

    # Favor conservative dead-time detection: the threshold sits above the
    # quietest quarter of the video, but still tracks the video's overall pace.
    return max(0.008, min(q50, q25 + 0.35 * spread))


def _build_inactive_ranges(
    *,
    samples: list[Sample],
    smoothed_motion: list[float],
    threshold: float,
    min_dead_seconds: float,
    merge_gap_seconds: float,
    pad_seconds: float,
    duration: float,
) -> list[Segment]:
    segments: list[Segment] = []
    if not samples:
        return segments

    inactive_start: float | None = None

    for index, sample in enumerate(samples):
        is_inactive = smoothed_motion[index] < threshold
        if is_inactive and inactive_start is None:
            inactive_start = sample.time
        elif not is_inactive and inactive_start is not None:
            inactive_end = sample.time
            if inactive_end - inactive_start >= min_dead_seconds:
                segment = _make_segment(
                    samples=samples,
                    smoothed_motion=smoothed_motion,
                    start=inactive_start,
                    end=inactive_end,
                    pad_seconds=pad_seconds,
                    duration=duration,
                    threshold=threshold,
                )
                _merge_or_append(segments, segment, merge_gap_seconds)
            inactive_start = None

    if inactive_start is not None and duration - inactive_start >= min_dead_seconds:
        segment = _make_segment(
            samples=samples,
            smoothed_motion=smoothed_motion,
            start=inactive_start,
            end=duration,
            pad_seconds=pad_seconds,
            duration=duration,
            threshold=threshold,
        )
        _merge_or_append(segments, segment, merge_gap_seconds)

    return segments


def _make_segment(
    *,
    samples: list[Sample],
    smoothed_motion: list[float],
    start: float,
    end: float,
    pad_seconds: float,
    duration: float,
    threshold: float,
) -> Segment:
    padded_start = max(0.0, start - pad_seconds)
    padded_end = min(duration, end + pad_seconds)

    indices = [i for i, sample in enumerate(samples) if padded_start <= sample.time <= padded_end]
    motion_values = [smoothed_motion[i] for i in indices]
    pose_counts = [samples[i].pose_count for i in indices]

    average_motion = float(np.mean(motion_values)) if motion_values else 0.0
    average_pose_count = float(np.mean(pose_counts)) if pose_counts else 0.0

    # Higher score means more confidently dead time.
    score = max(0.0, min(1.0, 1.0 - (average_motion / max(threshold, 1e-6))))
    return Segment(
        start=padded_start,
        end=padded_end,
        score=score,
        average_motion=average_motion,
        average_pose_count=average_pose_count,
    )


def _merge_or_append(segments: list[Segment], candidate: Segment, merge_gap_seconds: float) -> None:
    if segments and candidate.start - segments[-1].end <= merge_gap_seconds:
        previous = segments[-1]
        segments[-1] = Segment(
            start=previous.start,
            end=max(previous.end, candidate.end),
            score=max(previous.score, candidate.score),
            average_motion=(previous.average_motion + candidate.average_motion) / 2,
            average_pose_count=(previous.average_pose_count + candidate.average_pose_count) / 2,
        )
        return

    segments.append(candidate)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Detect dead-time intervals in a volleyball video")
    parser.add_argument("video_path", help="Path to the input video")
    parser.add_argument("--sample-stride", type=int, default=4, help="Read every Nth frame")
    parser.add_argument("--min-dead-seconds", type=float, default=3.0, help="Minimum duration for a dead-time segment")
    parser.add_argument("--merge-gap-seconds", type=float, default=1.0, help="Merge nearby segments separated by a short gap")
    parser.add_argument("--pad-seconds", type=float, default=0.75, help="Pad each detected segment on both sides")
    parser.add_argument("--threshold", type=float, default=None, help="Override the adaptive motion threshold")
    parser.add_argument("--output", type=str, default=None, help="Optional path to write the JSON result")
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
    )

    payload = json.dumps(result, indent=2 if args.pretty else None)
    print(payload)

    if args.output:
        output_path = Path(args.output)
        output_path.write_text(payload + "\n", encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())