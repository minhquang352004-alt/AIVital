"""
scripts/benchmarks/profile_process_frame.py
============================================
BUOC 0 - Do co so: profile thoi gian tung thanh phan cua process_frame()
khi buffer da day (trang thai ready, 8 s @ 30 FPS = 240 mau).

Chay tu thu muc goc AIVital/:
    python scripts/benchmarks/profile_process_frame.py

Khong sua bat ky file source nao.
N_ITER = 500, SEED = 42, fs = 30.0 Hz, win = 8.0 s (240 mau)
"""
import sys
import os
import time
import numpy as np

# Ensure imports work from project root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

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

# --- CONFIG -------------------------------------------------------------------
FS      = 30.0
WIN_SEC = 8.0
N_SAMP  = int(WIN_SEC * FS)   # 240
N_ITER  = 500
SEED    = 42
BUDGET_MS = 1000.0 / FS       # 33.33 ms

rng = np.random.default_rng(SEED)
cfg = SignalConfig()

# --- SYNTHETIC INPUT ----------------------------------------------------------
t      = np.linspace(0, WIN_SEC, N_SAMP, endpoint=False)
pulse  = np.sin(2 * np.pi * 1.2 * t)
R_sig  = 160.0 - 0.6 * pulse + rng.normal(0, 0.5, N_SAMP)
G_sig  = 110.0 - 1.8 * pulse + rng.normal(0, 0.5, N_SAMP)
B_sig  = 85.0  - 0.3 * pulse + rng.normal(0, 0.5, N_SAMP)
rgb_window = np.column_stack([R_sig, G_sig, B_sig])   # (240, 3)
timestamps = t.copy()

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
    lambda: resample_to_fixed_fps(timestamps, rgb_window, target_fps=FS)
)

# --- 2a. POS inner loop (Python for-loop, no detrend/filter) -----------------
pos      = POSMethod(fps=FS, window_sec=1.6)
WIN_LEN  = pos.window_len
PROJ_MAT = np.array([[0.0, 1.0, -1.0], [-2.0, 1.0, 1.0]])

def pos_inner_loop(rgb):
    N = rgb.shape[0]
    H = np.zeros(N)
    for n in range(N):
        m = n - WIN_LEN
        if m >= 0:
            sub  = rgb[m:n, :]
            mean_rgb = np.mean(sub, axis=0)
            mean_rgb[mean_rgb == 0] = 1e-7
            Cn   = (sub / mean_rgb).T
            S    = np.matmul(PROJ_MAT, Cn)
            std0, std1 = np.std(S[0]), np.std(S[1])
            alpha = (std0 / std1) if std1 > 1e-7 else 0.0
            h    = S[0] + alpha * S[1]
            H[m:n] += h - np.mean(h)
    return H

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
        H_detrended, cfg.low_cutoff_hz, cfg.high_cutoff_hz,
        fs=FS, order=cfg.filter_order
    )
)
bvp_filtered = butter_bandpass_filter(
    H_detrended, cfg.low_cutoff_hz, cfg.high_cutoff_hz,
    fs=FS, order=cfg.filter_order
)

# --- 2d. SQI ------------------------------------------------------------------
median_sqi, min_sqi = measure_ms(
    lambda: calculate_bvp_quality(bvp_filtered, fs=FS)
)

# --- 2e. POS.process() FULL (loop + detrend + filter) -------------------------
median_pos_full, min_pos_full = measure_ms(
    lambda: pos.process(rgb_window)
)

# --- 3. TOTAL process_frame() WITH FULL PIPELINE ------------------------------
pipeline = RealtimeSignalPipeline(
    method="POS",
    window_sec=WIN_SEC,
    min_sec=WIN_SEC * 0.5,
    target_fps=FS,
)

# Pre-fill buffer: 200 frames
for i in range(200):
    b_v = int(np.clip(85  + rng.integers(-2, 3), 0, 255))
    g_v = int(np.clip(110 + rng.integers(-2, 3), 0, 255))
    r_v = int(np.clip(160 + rng.integers(-2, 3), 0, 255))
    frame = np.full((100, 100, 3), [b_v, g_v, r_v], dtype=np.uint8)
    pipeline.process_frame(frame, timestamp=i / FS)

assert pipeline.is_ready, "Buffer not ready after 200 frames!"

# Measure each subsequent frame (buffer always full after this point)
frame_times = []
for i in range(N_ITER):
    b_v = int(np.clip(85  + rng.integers(-2, 3), 0, 255))
    g_v = int(np.clip(110 + rng.integers(-2, 3), 0, 255))
    r_v = int(np.clip(160 + rng.integers(-2, 3), 0, 255))
    frame = np.full((100, 100, 3), [b_v, g_v, r_v], dtype=np.uint8)
    ts    = (200 + i) / FS
    t0    = time.perf_counter()
    pipeline.process_frame(frame, timestamp=ts)
    frame_times.append((time.perf_counter() - t0) * 1e3)

frame_arr       = np.array(frame_times)
median_frame    = float(np.median(frame_arr))
p95_frame       = float(np.percentile(frame_arr, 95))
min_frame       = float(np.min(frame_arr))

# --- PRINT RESULTS -----------------------------------------------------------
print("=" * 72)
print("BUOC 0 - DO CO SO: PROFILE PROCESS_FRAME()")
print(f"Config: fs={FS} Hz | win={WIN_SEC}s | N_samp={N_SAMP} | N_iter={N_ITER} | seed={SEED}")
print("=" * 72)

print(f"\n--- Phan tach thanh phan (tren cua so {N_SAMP} mau, {N_ITER} lan do) ---")
print(f"{'Thanh phan':<40} {'Median(ms)':>10} {'Min(ms)':>9} {'% 33ms':>8}")
print("-" * 72)
rows = [
    ("Resample  (np.interp, 240x3)",      median_resample, min_resample),
    ("POS inner loop (Python for-loop)",   median_pos_loop, min_pos_loop),
    ("Detrend   (smoothness_priors)",      median_detrend,  min_detrend),
    ("Bandpass  (filtfilt, ord=1)",        median_filter,   min_filter),
    ("SQI       (periodogram)",            median_sqi,      min_sqi),
    ("--- POS.process() FULL ---",         median_pos_full, min_pos_full),
    ("  = loop + detrend + filter",        median_pos_full, min_pos_full),
]
for name, med, mn in rows:
    print(f"{name:<40} {med:>10.3f} {mn:>9.3f} {med/BUDGET_MS*100:>7.1f}%")

print(f"\n--- Tong process_frame() (buffer day, frame 100x100) ---")
print(f"{'':>40} {'Median':>10} {'p95':>9} {'% 33ms':>8}")
print("-" * 72)
print(f"{'process_frame() end-to-end':<40} {median_frame:>10.3f} {p95_frame:>9.3f} {median_frame/BUDGET_MS*100:>7.1f}%")
print(f"  Ghi chu: bao gom Face detect (Haar cascade, fallback), ROI extract, buffer push, resample, POS, SQI")

print(f"\n--- Cua so truot: chong lan giua 2 frame lien tiep ---")
step_samples  = 1
overlap_pct   = (N_SAMP - step_samples) / N_SAMP * 100.0
print(f"  Cua so: {N_SAMP} mau | Buoc truot: {step_samples} mau/frame")
print(f"  => Chong lan: {overlap_pct:.2f}%  ({N_SAMP - step_samples}/{N_SAMP} mau giong nhau)")
print(f"  => Moi frame TINH LAI BVP tren TOAN BO {N_SAMP} mau (khong co incremental): YES")
print(f"  => window_len (sub-window POS): {WIN_LEN} mau ({WIN_LEN/FS:.2f}s)")
