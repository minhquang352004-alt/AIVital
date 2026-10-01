"""
scripts/benchmarks/bench_sub_roi_cost.py
=========================================
BUOC 2 - Do chi phi them moi frame cua extract_sub_roi_rgbs() va buffer push.

Chay tu thu muc goc AIVital/:
    python scripts/benchmarks/bench_sub_roi_cost.py

Khong sua bat ky file source nao.
Config: N=500, seed=42, frame 100x100 BGR, bbox=(10,10,80,80)
"""
import sys, os, time
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

if hasattr(sys.stdout, "reconfigure"):
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass

from aivitals_engine.roi.extractor import ROIExtractor
from aivitals_engine.signal.sliding_buffer import SlidingWindowBuffer

N    = 500
SEED = 42
rng  = np.random.default_rng(SEED)

extractor = ROIExtractor()
frame     = np.full((100, 100, 3), [85, 110, 160], dtype=np.uint8)
bbox      = (10, 10, 80, 80)

# Pre-compute reference RGB
base_rgb = extractor.extract_mean_rgb(frame, bbox)

# --- 1. Cost of extract_mean_rgb (existing) ---
def fn_mean():
    extractor.extract_mean_rgb(frame, bbox)

def fn_sub():
    extractor.extract_sub_roi_rgbs(frame, bbox)

def measure(fn):
    times = []
    for _ in range(N):
        t0 = time.perf_counter()
        fn()
        times.append((time.perf_counter() - t0) * 1e3)
    arr = np.array(times)
    return float(np.median(arr)), float(np.percentile(arr, 95))

med_mean, p95_mean = measure(fn_mean)
med_sub,  p95_sub  = measure(fn_sub)
extra = med_sub - med_mean

# --- 2. Cost of buffer push with vs without sub_rgbs ---
sub_val = extractor.extract_sub_roi_rgbs(frame, bbox)
buf     = SlidingWindowBuffer(window_sec=8.0, min_sec=1.0, target_fps=30.0, artifact_threshold=None)

def fn_push_no_sub():
    buf._rgb_buffer.append(base_rgb)
    buf._timestamps.append(time.perf_counter())

def fn_push_with_sub():
    buf._rgb_buffer.append(base_rgb)
    buf._timestamps.append(time.perf_counter())
    buf._forehead_buf.append(sub_val.forehead)
    buf._left_cheek_buf.append(sub_val.left_cheek)
    buf._right_cheek_buf.append(sub_val.right_cheek)

med_push_no,   p95_push_no   = measure(fn_push_no_sub)
med_push_with, p95_push_with = measure(fn_push_with_sub)

print("=" * 64)
print("BUOC 2 - CHI PHI THEM CUA EXTRACT_SUB_ROI_RGBS()")
print(f"Config: N={N}, seed={SEED}, frame=100x100 BGR, bbox=(10,10,80,80)")
print("=" * 64)
print(f"\n{'Phep do':<45} {'Median(ms)':>10} {'p95(ms)':>9}")
print("-" * 65)
print(f"{'extract_mean_rgb() [hien tai]':<45} {med_mean:>10.3f} {p95_mean:>9.3f}")
print(f"{'extract_sub_roi_rgbs() [moi]':<45} {med_sub:>10.3f} {p95_sub:>9.3f}")
print(f"{'Chi phi them (sub - mean)':<45} {extra:>10.3f} {p95_sub-p95_mean:>9.3f}")
print()
print(f"{'push() khong sub_rgbs':<45} {med_push_no:>10.3f} {p95_push_no:>9.3f}")
print(f"{'push() co sub_rgbs':<45} {med_push_with:>10.3f} {p95_push_with:>9.3f}")
print(f"{'Chi phi them push':<45} {med_push_with-med_push_no:>10.3f} {p95_push_with-p95_push_no:>9.3f}")
print(f"\nTong chi phi them moi frame (extractor + push): ~{extra + (med_push_with-med_push_no):.3f} ms")
print(f"Ngan sach 30 FPS: 33.33 ms / frame")
print(f"(Frame size khi do: 100x100 BGR)")
