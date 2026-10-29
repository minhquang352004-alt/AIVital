"""
scripts/benchmarks/regression_check_bvp.py
===========================================
Regression test: Verify that RealtimeSignalPipeline produces deterministic,
bit-exact identical BVP signals across consecutive runs on real video frames
from aivitals_engine/samples/vid.avi.
"""
import os
import sys
import cv2
import numpy as np

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from aivitals_engine.signal_pipeline_realtime import RealtimeSignalPipeline

VIDEO_PATH = os.path.join(PROJECT_ROOT, "aivitals_engine", "samples", "vid.avi")


def run_regression_test():
    cap = cv2.VideoCapture(VIDEO_PATH)
    src_fps = float(cap.get(cv2.CAP_PROP_FPS) or 28.671786)
    cap.set(cv2.CAP_PROP_POS_FRAMES, 150)

    frames = []
    while len(frames) < 250:
        ret, frame = cap.read()
        if not ret or frame is None:
            break
        frames.append(frame)
    cap.release()

    pipe_a = RealtimeSignalPipeline(method="POS")
    pipe_b = RealtimeSignalPipeline(method="POS")

    match_count = 0
    max_diff = 0.0

    for i, frame in enumerate(frames):
        ts = i / src_fps
        res_a = pipe_a.process_frame(frame, timestamp=ts)
        res_b = pipe_b.process_frame(frame, timestamp=ts)

        assert res_a.is_ready == res_b.is_ready
        assert res_a.status == res_b.status
        if res_a.is_ready and res_a.bvp_signal is not None:
            diff = float(np.max(np.abs(res_a.bvp_signal - res_b.bvp_signal)))
            if diff > max_diff:
                max_diff = diff
            assert np.array_equal(res_a.bvp_signal, res_b.bvp_signal), f"Mismatch at frame {i}"
            assert res_a.quality_sqi == res_b.quality_sqi
            match_count += 1

    print("=" * 68)
    print("BVP DETERMINISM & REGRESSION TEST ON REAL VIDEO (vid.avi)")
    print(f"Tested: {match_count} ready BVP windows across {len(frames)} real frames from vid.avi")
    print(f"Max absolute element-wise difference: {max_diff}")
    print("Verdict: BIT-EXACT DETERMINISTIC ON vid.avi (diff = 0.0)")
    print("=" * 68)


if __name__ == "__main__":
    run_regression_test()
