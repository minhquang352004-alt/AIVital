"""
scripts/benchmarks/bench_periodicity_sqi.py
============================================
BUOC 4 - Benchmark chi tiết cho Periodicity SQI (ACF đỉnh chuẩn hóa)
trực tiếp trên chuỗi tín hiệu sóng mạch trích xuất từ video thực tế (aivitals_engine/samples/vid.avi).
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
from aivitals_engine.quality.sqi import calculate_periodicity_sqi
from aivitals_engine.rppg.pos import POSMethod
from aivitals_engine.signal.detrend import smoothness_priors_detrend
from aivitals_engine.signal.filter import butter_bandpass_filter
from aivitals_engine.signal.resample import resample_to_fixed_fps
from aivitals_engine.signal_pipeline_realtime import RealtimeSignalPipeline

VIDEO_PATH = os.path.join(PROJECT_ROOT, "aivitals_engine", "samples", "vid.avi")
cfg = SignalConfig()
FS = 30.0
N_RUNS = 500
SEED = 42


def extract_real_pulse_from_vid_avi(n_frames: int = 450) -> np.ndarray:
    """Trích xuất chuỗi BVP thực tế dài (~15s) từ vid.avi."""
    cap = cv2.VideoCapture(VIDEO_PATH)
    src_fps = float(cap.get(cv2.CAP_PROP_FPS) or 28.671786)
    cap.set(cv2.CAP_PROP_POS_FRAMES, 150)

    pipe = RealtimeSignalPipeline(method="POS", window_sec=16.0, min_sec=3.0, target_fps=FS)
    for i in range(n_frames):
        ret, frame = cap.read()
        if not ret or frame is None:
            break
        pipe.process_frame(frame, timestamp=i / src_fps)
    cap.release()

    rgb_raw, ts_raw = pipe._buffer.get_raw_window()
    rgb_res = resample_to_fixed_fps(ts_raw, rgb_raw, target_fps=FS)
    bvp = POSMethod(fps=FS).process(rgb_res)
    return (bvp - np.mean(bvp)) / (np.std(bvp) + 1e-8)


def filter_pipeline(x):
    d = smoothness_priors_detrend(x, lambda_value=cfg.detrend_lambda)
    return butter_bandpass_filter(d, cfg.low_cutoff_hz, cfg.high_cutoff_hz, fs=FS, order=cfg.filter_order)


def run_benchmark():
    real_bvp_long = extract_real_pulse_from_vid_avi(n_frames=450)

    print("=" * 84)
    print(f"BUOC 4 - BENCHMARK PERIODICITY SQI (ACF CHUAN HOA) TREN vid.avi (N={N_RUNS})")
    print(f"Video: aivitals_engine/samples/vid.avi | Extracted BVP samples: {len(real_bvp_long)}")
    print("=" * 84)

    for T in [6.0, 8.0]:
        n = int(T * FS)
        max_offset = max(1, len(real_bvp_long) - n)
        print(f"\n====================== vid.avi WINDOW T = {T:.1f} s ({n} mau) ======================")

        clean_pulses = [real_bvp_long[(i % max_offset) : (i % max_offset) + n] for i in range(N_RUNS)]

        r_white = np.random.default_rng(SEED + 1)
        white_noises = [r_white.standard_normal(n) for _ in range(N_RUNS)]

        r_pink = np.random.default_rng(SEED + 2)
        pink_noises = []
        f_pink = np.fft.rfftfreq(n, 1.0 / FS)
        f_pink[0] = f_pink[1] if len(f_pink) > 1 else 1.0
        for _ in range(N_RUNS):
            w = r_pink.standard_normal(n)
            p = np.fft.irfft(np.fft.rfft(w) / np.sqrt(f_pink), n=n)
            pink_noises.append(p)

        r_rw = np.random.default_rng(SEED + 3)
        rw_noises = [np.cumsum(r_rw.standard_normal(n)) for _ in range(N_RUNS)]

        snr_mixes = {}
        for snr_db in [10.0, 5.0, 0.0]:
            r_mix = np.random.default_rng(SEED + int(snr_db) + 10)
            mix_list = []
            for clean in clean_pulses:
                w = r_mix.standard_normal(n)
                p_c = np.mean(clean ** 2)
                p_w = np.mean(w ** 2)
                scale = np.sqrt(p_c / (10 ** (snr_db / 10.0) * p_w + 1e-12))
                mix_list.append(clean + scale * w)
            snr_mixes[snr_db] = mix_list

        datasets = [
            ("vid.avi BVP (Real Clean)", clean_pulses),
            ("vid.avi + SNR +10 dB", snr_mixes[10.0]),
            ("vid.avi + SNR +5 dB", snr_mixes[5.0]),
            ("vid.avi + SNR 0 dB", snr_mixes[0.0]),
            ("Gaussian trang", white_noises),
            ("Pink noise (1/f)", pink_noises),
            ("Random walk (1/f^2)", rw_noises),
        ]

        hdr = f"{'Loai tin hieu / nhieu':<32} {'p50 (med)':>10} {'p95':>8} {'p99':>8} {'% >= 0.46 (Pass)':>22}"
        print(hdr)
        print("-" * 84)

        for label, sig_list in datasets:
            raw_peaks = []
            for raw_sig in sig_list:
                bvp = filter_pipeline(raw_sig)
                _, peak = calculate_periodicity_sqi(
                    bvp, fs=FS, min_bpm=cfg.periodicity_min_bpm, max_bpm=cfg.periodicity_max_bpm
                )
                raw_peaks.append(peak)

            arr = np.array(raw_peaks)
            p50 = np.median(arr)
            p95 = np.percentile(arr, 95)
            p99 = np.percentile(arr, 99)
            fp = np.mean(arr >= cfg.periodicity_threshold) * 100.0

            print(f"{label:<32} {p50:>10.3f} {p95:>8.3f} {p99:>8.3f} {fp:>21.2f}%")


if __name__ == "__main__":
    t0 = time.time()
    run_benchmark()
    print(f"\nDa xong trong {time.time() - t0:.1f} s")
