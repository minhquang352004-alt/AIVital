"""
scripts/benchmarks/profile_process_frame.py
============================================
BUOC 0 - Đo cơ sở: profile thời gian từng thành phần của process_frame()
trực tiếp trên luồng khung hình thực tế từ video (aivitals_engine/samples/vid.avi)
khi buffer đã đầy (trạng thái ready, 8s @ 30 FPS = 240 mẫu).

Chạy từ thư mục gốc AIVital/:
    python scripts/benchmarks/profile_process_frame.py
"""
import os
import sys
import time
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

from aivitals_engine.config.settings import SignalConfig
from aivitals_engine.signal.detrend import smoothness_priors_detrend
from aivitals_engine.signal.filter import butter_bandpass_filter
from aivitals_engine.signal.resample import resample_to_fixed_fps
from aivitals_engine.quality.sqi import calculate_bvp_quality
from aivitals_engine.rppg.pos import POSMethod
from aivitals_engine.signal_pipeline_realtime import RealtimeSignalPipeline

VIDEO_PATH = os.path.join(PROJECT_ROOT, "aivitals_engine", "samples", "vid.avi")
FS = 30.0
WIN_SEC = 8.0
N_SAMP = int(WIN_SEC * FS)  # 240
N_ITER = 200
BUDGET_MS = 1000.0 / FS  # 33.33 ms

cfg = SignalConfig()

# --- LOAD REAL FRAMES FROM vid.avi --------------------------------------------
cap = cv2.VideoCapture(VIDEO_PATH)
src_fps = float(cap.get(cv2.CAP_PROP_FPS) or 28.671786)
cap.set(cv2.CAP_PROP_POS_FRAMES, 150)

vid_frames = []
while len(vid_frames) < (260 + N_ITER):
    ret, f = cap.read()
    if not ret or f is None:
        break
    vid_frames.append(f)
cap.release()

pipeline = RealtimeSignalPipeline(
    method="POS",
    window_sec=WIN_SEC,
    min_sec=WIN_SEC * 0.5,
    target_fps=FS,
)

# Pre-fill buffer with 250 real frames from vid.avi (~8.7 seconds)
for i in range(250):
    pipeline.process_frame(vid_frames[i], timestamp=i / src_fps)

assert pipeline.is_ready, "Buffer not ready after 250 frames from vid.avi!"

rgb_raw, timestamps = pipeline._buffer.get_raw_window()
rgb_window = resample_to_fixed_fps(timestamps, rgb_raw, target_fps=FS)


# --- HELPER -------------------------------------------------------------------
def measure_ms(fn, n=N_ITER):
    """Return (median_ms, min_ms) over n calls."""
    times = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        times.append(time.perf_counter() - t0)
    arr = np.array(times) * 1e3
    return float(np.median(arr)), float(np.min(arr))


# --- 1. RESAMPLE --------------------------------------------------------------
median_resample, min_resample = measure_ms(
    lambda: resample_to_fixed_fps(timestamps, rgb_raw, target_fps=FS)
)

# --- 2a. POS inner loop (Python for-loop, no detrend/filter) -----------------
pos = POSMethod(fps=FS, window_sec=1.6)
WIN_LEN = pos.window_len
PROJ_MAT = np.array([[0.0, 1.0, -1.0], [-2.0, 1.0, 1.0]])


def pos_inner_loop(rgb):
    N = rgb.shape[0]
    H = np.zeros(N)
    weights = np.zeros(N)
    for n in range(WIN_LEN, N + 1):
        m = n - WIN_LEN
        sub = rgb[m:n, :]
        mean_rgb = np.mean(sub, axis=0)
        mean_rgb[mean_rgb == 0] = 1e-7
        Cn = (sub / mean_rgb).T
        S = np.matmul(PROJ_MAT, Cn)
        std0, std1 = np.std(S[0]), np.std(S[1])
        alpha = (std0 / std1) if std1 > 1e-7 else 0.0
        h = S[0] + alpha * S[1]
        H[m:n] += h - np.mean(h)
        weights[m:n] += 1.0
    return np.divide(H, weights, out=np.zeros_like(H), where=weights > 0)


H_baseline = pos_inner_loop(rgb_window)
median_pos_loop, min_pos_loop = measure_ms(lambda: pos_inner_loop(rgb_window))

# --- 2b. DETREND --------------------------------------------------------------
median_detrend, min_detrend = measure_ms(
    lambda: smoothness_priors_detrend(H_baseline, lambda_value=cfg.detrend_lambda)
)
H_detrended = smoothness_priors_detrend(H_baseline, lambda_value=cfg.detrend_lambda)

# --- 2c. BANDPASS FILTER ------------------------------------------------------
median_filter, min_filter = measure_ms(
    lambda: butter_bandpass_filter(
        H_detrended, cfg.low_cutoff_hz, cfg.high_cutoff_hz, fs=FS, order=cfg.filter_order
    )
)
bvp_filtered = butter_bandpass_filter(
    H_detrended, cfg.low_cutoff_hz, cfg.high_cutoff_hz, fs=FS, order=cfg.filter_order
)

# --- 2d. SQI ------------------------------------------------------------------
median_sqi, min_sqi = measure_ms(
    lambda: calculate_bvp_quality(bvp_filtered, fs=FS)
)

# --- 2e. POS.process() FULL (loop + detrend + filter) -------------------------
median_pos_full, min_pos_full = measure_ms(
    lambda: pos.process(rgb_window)
)

# --- 3. TOTAL process_frame() WITH FULL PIPELINE ON vid.avi -------------------
frame_times = []
for i in range(N_ITER):
    frame = vid_frames[(250 + i) % len(vid_frames)]
    ts = (250 + i) / src_fps
    t0 = time.perf_counter()
    pipeline.process_frame(frame, timestamp=ts)
    frame_times.append((time.perf_counter() - t0) * 1e3)

frame_arr = np.array(frame_times)
median_frame = float(np.median(frame_arr))
p95_frame = float(np.percentile(frame_arr, 95))

h, w = vid_frames[0].shape[:2]
print("=" * 74)
print("BUOC 0 - DO CO SO: PROFILE PROCESS_FRAME() TREN vid.avi")
print(f"Video: vid.avi ({w}x{h} @ {src_fps:.2f} FPS) | win={WIN_SEC}s | N_samp={len(rgb_window)} | N_iter={N_ITER}")
print("=" * 74)

print(f"\n--- Phan tach thanh phan (tren cua so {len(rgb_window)} mau tu vid.avi, {N_ITER} lan do) ---")
print(f"{'Thanh phan':<40} {'Median(ms)':>10} {'Min(ms)':>9} {'% 33ms':>8}")
print("-" * 74)
rows = [
    ("Resample  (np.interp, 240x3)", median_resample, min_resample),
    ("POS inner loop (Overlap-Add)", median_pos_loop, min_pos_loop),
    ("Detrend   (Cached Sparse-LU)", median_detrend, min_detrend),
    ("Bandpass  (filtfilt, ord=1)", median_filter, min_filter),
    ("SQI       (periodogram)", median_sqi, min_sqi),
    ("--- POS.process() FULL ---", median_pos_full, min_pos_full),
]
for name, med, mn in rows:
    print(f"{name:<40} {med:>10.3f} {mn:>9.3f} {med/BUDGET_MS*100:>7.1f}%")

print(f"\n--- Tong process_frame() (buffer day, frame {w}x{h} tu vid.avi) ---")
print(f"{'':>40} {'Median':>10} {'p95':>9} {'% 33ms':>8}")
print("-" * 74)
print(f"{'process_frame() end-to-end (vid.avi)':<40} {median_frame:>10.3f} {p95_frame:>9.3f} {median_frame/BUDGET_MS*100:>7.1f}%")
print("  Ghi chu: bao gom MediaPipe Face Mesh (478 landmarks), Multi-ROI, buffer, resample, POS, SQI")
