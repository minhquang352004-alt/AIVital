"""
scripts/benchmarks/bench_feature_extractor.py
=============================================
Đo lường hiệu năng và latency của BVPFeatureExtractor Pipeline.

Mục tiêu ngân sách CPU:
    - Median latency <= 3.0 ms cho cửa sổ 8s @ 30 FPS (240 mẫu).
    - p95 latency <= 5.0 ms.

Chạy từ thư mục gốc AIVital/:
    python scripts/benchmarks/bench_feature_extractor.py
"""
import os
import sys
import time

import numpy as np

# Ensure project imports work
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from aivitals_engine.features import BVPFeatureExtractor, BVPFeatures

FS = 30.0
N_RUNS = 100
BUDGET_MS = 3.0


def main():
    print("=" * 65)
    print("  BVP FEATURE EXTRACTOR LATENCY BENCHMARK")
    print(f"  Runs: {N_RUNS} | FS: {FS} Hz | Budget: {BUDGET_MS} ms")
    print("=" * 65)

    ext = BVPFeatureExtractor()
    t = np.linspace(0, 8.0, int(8.0 * FS), endpoint=False)
    sig_clean = np.sin(2 * np.pi * 1.2 * t) + 0.25 * np.sin(4 * np.pi * 1.2 * t)
    sig_noisy = sig_clean + np.random.default_rng(42).normal(0, 0.1, sig_clean.size)

    # Warm-up
    for _ in range(10):
        ext.extract(sig_clean, FS)

    # Đo tín hiệu sạch
    times_clean = []
    for _ in range(N_RUNS):
        t0 = time.perf_counter()
        ext.extract(sig_clean, FS)
        times_clean.append((time.perf_counter() - t0) * 1000.0)

    # Đo tín hiệu có nhiễu
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

    print(f"\n[1] Clean Signal (8s, 240 samples):")
    print(f"    - Median : {med_clean:6.2f} ms  (Budget <= {BUDGET_MS} ms) -> {'PASS' if med_clean <= BUDGET_MS else 'FAIL'}")
    print(f"    - p95    : {p95_clean:6.2f} ms")
    print(f"    - Min/Max: {np.min(times_clean):6.2f} / {np.max(times_clean):6.2f} ms")

    print(f"\n[2] Noisy Signal (8s, 240 samples, SNR ~20dB):")
    print(f"    - Median : {med_noisy:6.2f} ms  (Budget <= {BUDGET_MS} ms) -> {'PASS' if med_noisy <= BUDGET_MS else 'FAIL'}")
    print(f"    - p95    : {p95_noisy:6.2f} ms")

    print(f"\n[3] Feature Contract Check:")
    print(f"    - Feature dimension: {BVPFeatures.feature_dim()} floats")
    print(f"    - Valid beats found: {feat_sample.valid_beat_count}")
    print(f"    - Non-NaN features : {int(np.sum(~np.isnan(vec)))} / {len(vec)}")

    print("\n" + "=" * 65)
    overall_pass = med_clean <= BUDGET_MS and med_noisy <= BUDGET_MS
    print(f"  VERDICT: {'ALL BUDGETS PASSED' if overall_pass else 'LATENCY BUDGET EXCEEDED'}")
    print("=" * 65)

    return 0 if overall_pass else 1


if __name__ == "__main__":
    sys.exit(main())
