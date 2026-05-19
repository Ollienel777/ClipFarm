"""Compatibility wrapper for the dead-time detector.

The implementation now lives in :mod:`ml.dead_time.detector`.
"""

from ml.dead_time.detector import analyze_video, main


if __name__ == "__main__":
    raise SystemExit(main())