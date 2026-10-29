"""
scripts/benchmarks/bench_cross_roi_methods.py
=============================================
So sánh phương pháp tính tương quan chéo 3 vùng con (Cross-ROI SQI):
- Method A: POS -> Detrend -> Bandpass -> Pearson
- Method B: Green detrend -> Bandpass -> Pearson
Trực tiếp trên dữ liệu RGB 3 vùng con (Trán, Má Trái, Má Phải) trích xuất từ video thực tế (aivitals_engine/samples/vid.avi).
"""
import os
import sys
import time
import cv2
import numpy as np
from scipy import signal

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from aivitals_engine.rppg.pos import POSMethod
from aivitals_engine.signal.filter import butter_bandpass_filter
from aivitals_engine.signal.resample import resample_to_fixed_fps
from aivitals_engine.signal_pipeline_realtime import RealtimeSignalPipeline

VIDEO_PATH = os.path.join(PROJECT_ROOT, "aivitals_engine", "samples", "vid.avi")


def extract_sub_rois_from_vid_avi(n_frames: int = 300, fs: float = 30.0):
    """Trích xuất chuỗi RGB thực tế của 3 vùng (forehead, left_cheek, right_cheek) từ vid.avi."""
    cap = cv2.VideoCapture(VIDEO_PATH)
    src_fps = float(cap.get(cv2.CAP_PROP_FPS) or 28.671786)
    cap.set(cv2.CAP_PROP_POS_FRAMES, 150)

    pipe = RealtimeSignalPipeline(method="POS", window_sec=8.0, min_sec=3.0, target_fps=fs)
    for i in range(n_frames):
        ret, frame = cap.read()
        if not ret or frame is None:
            break
        pipe.process_frame(frame, timestamp=i / src_fps)
    cap.release()

    raw_f, raw_l, raw_r = pipe._buffer.get_sub_roi_raw_window()
    _, ts_raw = pipe._buffer.get_raw_window()
    rgb_f = resample_to_fixed_fps(ts_raw, raw_f, target_fps=fs)
    rgb_l = resample_to_fixed_fps(ts_raw, raw_l, target_fps=fs)
    rgb_r = resample_to_fixed_fps(ts_raw, raw_r, target_fps=fs)
    return rgb_f, rgb_l, rgb_r


def method_a(rgb1, rgb2, rgb3, fs):
    pos = POSMethod(fps=fs)

    def process_roi(rgb):
        if np.mean(rgb) == 0:
            return np.zeros(len(rgb))
        return pos.process(rgb)

    start = time.perf_counter()
    p1 = process_roi(rgb1)
    p2 = process_roi(rgb2)
    p3 = process_roi(rgb3)

    r12 = np.corrcoef(p1, p2)[0, 1] if np.std(p1) > 0 and np.std(p2) > 0 else 0
    r13 = np.corrcoef(p1, p3)[0, 1] if np.std(p1) > 0 and np.std(p3) > 0 else 0
    r23 = np.corrcoef(p2, p3)[0, 1] if np.std(p2) > 0 and np.std(p3) > 0 else 0
    cost = time.perf_counter() - start
    return r12, r13, r23, cost


def method_b(rgb1, rgb2, rgb3, fs):
    def process_roi(rgb):
        g = rgb[:, 1]
        if np.mean(g) == 0:
            return np.zeros(len(g))
        g = signal.detrend(g)
        g = butter_bandpass_filter(g, 0.75, 2.50, fs, order=1)
        return g

    start = time.perf_counter()
    p1 = process_roi(rgb1)
    p2 = process_roi(rgb2)
    p3 = process_roi(rgb3)

    r12 = np.corrcoef(p1, p2)[0, 1] if np.std(p1) > 0 and np.std(p2) > 0 else 0
    r13 = np.corrcoef(p1, p3)[0, 1] if np.std(p1) > 0 and np.std(p3) > 0 else 0
    r23 = np.corrcoef(p2, p3)[0, 1] if np.std(p2) > 0 and np.std(p3) > 0 else 0
    cost = time.perf_counter() - start
    return r12, r13, r23, cost


def run_experiment():
    rng = np.random.default_rng(42)
    fs = 30.0
    N_trials = 100

    base_f, base_l, base_r = extract_sub_rois_from_vid_avi(n_frames=300, fs=fs)
    n_samples = len(base_f)
    t = np.arange(n_samples) / fs

    print("=" * 72, flush=True)
    print("  CROSS-ROI CORRELATION BENCHMARK ON REAL VIDEO (vid.avi)", flush=True)
    print(f"  Video: vid.avi | Window: {n_samples} samples @ {fs} Hz | Trials: {N_trials}", flush=True)
    print("  A: POS -> Detrend -> Bandpass -> Pearson", flush=True)
    print("  B: Green detrend -> Bandpass -> Pearson", flush=True)
    print("=" * 72 + "\n", flush=True)

    scenarios = {
        "1. Real vid.avi Sub-ROIs (Unmodified)       ": {"light_amp": 0.0, "noise_amp": 0.0},
        "2. Real vid.avi + Additive Sensor Noise     ": {"light_amp": 0.0, "noise_amp": 0.5},
        "3. Real vid.avi + Shared Light Flicker (5%) ": {"light_amp": 0.05, "noise_amp": 0.2},
        "4. Real vid.avi + Heavy Independent Noise   ": {"light_amp": 0.0, "noise_amp": 2.5},
    }

    for name, params in scenarios.items():
        rA_list = []
        rB_list = []
        cost_A = 0.0
        cost_B = 0.0
        light = 1.0 + params["light_amp"] * np.sin(2 * np.pi * 0.5 * t)[:, None]
        for _ in range(N_trials):
            rgb1 = base_f * light + rng.normal(0, params["noise_amp"], base_f.shape)
            rgb2 = base_l * light + rng.normal(0, params["noise_amp"], base_l.shape)
            rgb3 = base_r * light + rng.normal(0, params["noise_amp"], base_r.shape)

            r12A, r13A, r23A, cA = method_a(rgb1, rgb2, rgb3, fs)
            r12B, r13B, r23B, cB = method_b(rgb1, rgb2, rgb3, fs)

            rA_list.extend([r12A, r13A, r23A])
            rB_list.extend([r12B, r13B, r23B])
            cost_A += cA
            cost_B += cB

        print(f"Scenario: {name}", flush=True)
        print(f"  Method A (POS)   - Mean r: {np.mean(rA_list):.3f}, 95th: {np.percentile(rA_list, 95):.3f}", flush=True)
        print(f"  Method B (Green) - Mean r: {np.mean(rB_list):.3f}, 95th: {np.percentile(rB_list, 95):.3f}", flush=True)
        print(f"  Time (per 3-ROI calc) -> A: {cost_A/N_trials*1000:.2f} ms | B: {cost_B/N_trials*1000:.2f} ms\n", flush=True)


if __name__ == "__main__":
    run_experiment()
