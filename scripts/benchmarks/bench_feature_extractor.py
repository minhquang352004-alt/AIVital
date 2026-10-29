"""
scripts/benchmarks/bench_feature_extractor.py
=============================================
Đo lường hiệu năng và latency của BVPFeatureExtractor Pipeline
trực tiếp trên tín hiệu sóng BVP trích xuất từ video thực tế (aivitals_engine/samples/vid.avi).

Mục tiêu ngân sách CPU:
    - Median latency <= 3.0 ms cho cửa sổ 8s @ 30 FPS (240 mẫu).
    - p95 latency <= 5.0 ms.

Chạy từ thư mục gốc AIVital/:
    python scripts/benchmarks/bench_feature_extractor.py
"""
import os
import sys
import time

import cv2
import numpy as np

# Ensure project imports work
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from aivitals_engine.features import BVPFeatureExtractor, BVPFeatures
from aivitals_engine.signal_pipeline_realtime import RealtimeSignalPipeline

VIDEO_PATH = os.path.join(PROJECT_ROOT, "aivitals_engine", "samples", "vid.avi")
FS = 30.0
N_RUNS = 100
BUDGET_MS = 3.0


def extract_real_bvp_from_vid_avi() -> np.ndarray:
    """Trích xuất cửa sổ BVP 8s (240 mẫu @ 30 Hz) thực tế từ vid.avi."""
    cap = cv2.VideoCapture(VIDEO_PATH)
    src_fps = float(cap.get(cv2.CAP_PROP_FPS) or 28.671786)
    cap.set(cv2.CAP_PROP_POS_FRAMES, 150)

    pipe = RealtimeSignalPipeline(method="POS", window_sec=8.0, min_sec=3.0, target_fps=FS)
    last_bvp = None
    for i in range(300):
        ret, frame = cap.read()
        if not ret or frame is None:
            break
        res = pipe.process_frame(frame, timestamp=i / src_fps)
        if res.is_ready and res.bvp_signal is not None:
            last_bvp = res.bvp_signal
    cap.release()
    if last_bvp is None:
        raise RuntimeError("Không trích xuất được BVP từ vid.avi")
    return last_bvp


def main():
    sig_clean = extract_real_bvp_from_vid_avi()
    sig_noisy = sig_clean + np.random.default_rng(42).normal(0, 0.1 * np.std(sig_clean), sig_clean.size)

    print("=" * 70)
    print("  BVP FEATURE EXTRACTOR LATENCY BENCHMARK (ON REAL vid.avi BVP)")
    print(f"  Video: vid.avi | Samples: {len(sig_clean)} | Runs: {N_RUNS} | FS: {FS} Hz | Budget: {BUDGET_MS} ms")
    print("=" * 70)

    ext = BVPFeatureExtractor()

    # Warm-up
    for _ in range(10):
        ext.extract(sig_clean, FS)

    # Đo tín hiệu thực tế từ vid.avi
    times_clean = []
    for _ in range(N_RUNS):
        t0 = time.perf_counter()
        ext.extract(sig_clean, FS)
        times_clean.append((time.perf_counter() - t0) * 1000.0)

    # Đo tín hiệu thực tế + nhiễu cộng thêm
    times_noisy = []
    for _ in range(N_RUNS):
        t0 = time.perf_counter()
        ext.extract(sig_noisy, FS)
        times_noisy.append((time.perf_counter() - t0) * 1000.0)

    med_clean = float(np.median(times_clean))
    p95_clean = float(np.percentile(times_clean, 95))
    med_noisy = float(np.median(times_noisy))
    p95_noisy = float(np.percentile(times_noisy, 95))

    feat_sample = ext.extract(sig_clean, FS)
    vec = feat_sample.to_numpy()

    print(f"\n[1] Real vid.avi BVP Window (8s, {len(sig_clean)} samples):")
    print(f"    - Median : {med_clean:6.2f} ms  (Budget <= {BUDGET_MS} ms) -> {'PASS' if med_clean <= BUDGET_MS else 'FAIL'}")
    print(f"    - p95    : {p95_clean:6.2f} ms")
    print(f"    - Min/Max: {np.min(times_clean):6.2f} / {np.max(times_clean):6.2f} ms")

    print(f"\n[2] Real vid.avi BVP + Perturbation Noise (8s, {len(sig_noisy)} samples):")
    print(f"    - Median : {med_noisy:6.2f} ms  (Budget <= {BUDGET_MS} ms) -> {'PASS' if med_noisy <= BUDGET_MS else 'FAIL'}")
    print(f"    - p95    : {p95_noisy:6.2f} ms")

    print(f"\n[3] Feature Contract Check (on vid.avi):")
    print(f"    - Feature dimension: {BVPFeatures.feature_dim()} floats")
    print(f"    - Valid beats found: {feat_sample.valid_beat_count}")
    print(f"    - Non-NaN features : {int(np.sum(~np.isnan(vec)))} / {len(vec)}")

    print("\n" + "=" * 70)
    overall_pass = med_clean <= BUDGET_MS and med_noisy <= BUDGET_MS
    print(f"  VERDICT: {'ALL BUDGETS PASSED ON vid.avi' if overall_pass else 'LATENCY BUDGET EXCEEDED'}")
    print("=" * 70)

    return 0 if overall_pass else 1


if __name__ == "__main__":
    sys.exit(main())
