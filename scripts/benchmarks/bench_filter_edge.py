"""
scripts/benchmarks/bench_filter_edge.py
========================================
BUOC 1 - Đo méo biên của filter: so sánh 4 phương án trực tiếp trên chuỗi tín hiệu
BVP thực tế trích xuất từ video chuẩn (aivitals_engine/samples/vid.avi).

Chạy từ thư mục gốc AIVital/:
    python scripts/benchmarks/bench_filter_edge.py
"""
import os
import sys
import time
import cv2
import numpy as np
from scipy import signal as scipy_signal

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from aivitals_engine.signal.detrend import smoothness_priors_detrend
from aivitals_engine.signal.resample import resample_to_fixed_fps
from aivitals_engine.signal_pipeline_realtime import RealtimeSignalPipeline
from aivitals_engine.vitals.hr import calculate_fft_hr

VIDEO_PATH = os.path.join(PROJECT_ROOT, "aivitals_engine", "samples", "vid.avi")
FS = 30.0
N_RUNS = 200
SEED = 42
LOW_CUT = 0.75
HIGH_CUT = 2.5
ORDER = 1
BUDGET_MS = 1000.0 / FS

rng = np.random.default_rng(SEED)

b_ref, a_ref = scipy_signal.butter(ORDER, [LOW_CUT / (0.5 * FS), HIGH_CUT / (0.5 * FS)], btype="bandpass")
DEFAULT_PADLEN = 3 * max(len(a_ref), len(b_ref))


def build_ba(fs):
    nyq = 0.5 * fs
    low = max(0.001, min(LOW_CUT / nyq, 0.99))
    high = max(low + 0.001, min(HIGH_CUT / nyq, 0.999))
    return scipy_signal.butter(ORDER, [low, high], btype="bandpass")


def build_sos(fs):
    nyq = 0.5 * fs
    low = max(0.001, min(LOW_CUT / nyq, 0.99))
    high = max(low + 0.001, min(HIGH_CUT / nyq, 0.999))
    return scipy_signal.butter(ORDER, [low, high], btype="bandpass", output="sos")


b_coef, a_coef = build_ba(FS)
sos_coef = build_sos(FS)


def extract_long_trace_from_vid_avi(n_frames: int = 450) -> np.ndarray:
    """Trích xuất chuỗi tín hiệu G-channel detrended dài (~15s) từ vid.avi làm tham chiếu thực tế."""
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
    raw_g = -rgb_res[:, 1].astype(np.float64)
    det_g = smoothness_priors_detrend(raw_g, lambda_value=100.0)
    det_g = (det_g - np.mean(det_g)) / (np.std(det_g) + 1e-8)
    return det_g


def filt_a_current(x):
    if len(x) < 9:
        return x
    return scipy_signal.filtfilt(b_coef, a_coef, x.astype(np.float64))


def filt_b_padlen(x, n_samp):
    if len(x) < 9:
        return x
    padlen = min(3 * n_samp, len(x) - 1)
    return scipy_signal.filtfilt(b_coef, a_coef, x.astype(np.float64), padlen=padlen, padtype="odd")


def filt_c_sos(x):
    if len(x) < 9:
        return x
    return scipy_signal.sosfiltfilt(sos_coef, x.astype(np.float64))


def filt_d_trim(x, trim_sec=1.0):
    if len(x) < 9:
        return x
    filtered = scipy_signal.filtfilt(b_coef, a_coef, x.astype(np.float64))
    trim_n = int(trim_sec * FS)
    return filtered[trim_n:]


def edge_mae(original, filtered, n_1s):
    n = len(original)
    if n <= 2 * n_1s:
        return np.nan, np.nan, np.nan
    mae_start = np.mean(np.abs(filtered[:n_1s] - original[:n_1s]))
    mae_end = np.mean(np.abs(filtered[-n_1s:] - original[-n_1s:]))
    mae_center = np.mean(np.abs(filtered[n_1s:-n_1s] - original[n_1s:-n_1s]))
    return float(mae_start), float(mae_end), float(mae_center)


def measure_ms(fn, n=N_RUNS):
    times = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        times.append((time.perf_counter() - t0) * 1e3)
    arr = np.array(times)
    return float(np.median(arr)), float(np.percentile(arr, 95))


LONG_RAW = extract_long_trace_from_vid_avi(n_frames=450)
LONG_REF = scipy_signal.filtfilt(b_coef, a_coef, LONG_RAW)


def run_window(dur_sec):
    n_samp = int(dur_sec * FS)
    n_1s = int(1.0 * FS)
    trim_n = int(1.0 * FS)
    n_ext = n_samp + trim_n

    maes_start = {k: [] for k in ["a", "b", "c", "d"]}
    maes_end = {k: [] for k in ["a", "b", "c", "d"]}
    maes_center = {k: [] for k in ["a", "b", "c", "d"]}
    hr_errs = {k: [] for k in ["a", "b", "c", "d"]}

    max_start = max(1, len(LONG_RAW) - n_ext - 1)

    for i in range(N_RUNS):
        idx0 = trim_n + (i % max(1, max_start - trim_n))
        raw_win = LONG_RAW[idx0 : idx0 + n_samp]
        clean = LONG_REF[idx0 : idx0 + n_samp]
        true_hr = calculate_fft_hr(clean, fs=FS)

        noise = rng.standard_normal(n_samp)
        noise_filt = scipy_signal.filtfilt(b_coef, a_coef, noise)
        p_pulse = np.mean(clean ** 2)
        p_noise = np.mean(noise_filt ** 2)
        scale = np.sqrt(p_pulse / (p_noise + 1e-12))
        noisy = raw_win + 0.35 * scale * noise_filt

        fa = filt_a_current(raw_win)
        fn_a = filt_a_current(noisy)
        s, e, c = edge_mae(clean, fa, n_1s)
        maes_start["a"].append(s); maes_end["a"].append(e); maes_center["a"].append(c)
        hr_errs["a"].append(abs(calculate_fft_hr(fn_a, fs=FS) - true_hr))

        fb = filt_b_padlen(raw_win, n_samp)
        fn_b = filt_b_padlen(noisy, n_samp)
        s, e, c = edge_mae(clean, fb, n_1s)
        maes_start["b"].append(s); maes_end["b"].append(e); maes_center["b"].append(c)
        hr_errs["b"].append(abs(calculate_fft_hr(fn_b, fs=FS) - true_hr))

        fc = filt_c_sos(raw_win)
        fn_c = filt_c_sos(noisy)
        s, e, c = edge_mae(clean, fc, n_1s)
        maes_start["c"].append(s); maes_end["c"].append(e); maes_center["c"].append(c)
        hr_errs["c"].append(abs(calculate_fft_hr(fn_c, fs=FS) - true_hr))

        raw_ext = LONG_RAW[idx0 - trim_n : idx0 + n_samp]
        noisy_ext = raw_ext + 0.35 * scale * scipy_signal.filtfilt(b_coef, a_coef, rng.standard_normal(len(raw_ext)))
        fd = filt_d_trim(raw_ext, trim_sec=1.0)
        fn_d = filt_d_trim(noisy_ext, trim_sec=1.0)
        s, e, c = edge_mae(clean, fd[:n_samp], n_1s)
        maes_start["d"].append(s); maes_end["d"].append(e); maes_center["d"].append(c)
        hr_errs["d"].append(abs(calculate_fft_hr(fn_d[:n_samp], fs=FS) - true_hr))

    clean_ref = LONG_RAW[trim_n : trim_n + n_samp]
    clean_ext_ref = LONG_RAW[:n_ext]

    t_a_med, t_a_p95 = measure_ms(lambda: filt_a_current(clean_ref))
    t_b_med, t_b_p95 = measure_ms(lambda: filt_b_padlen(clean_ref, n_samp))
    t_c_med, t_c_p95 = measure_ms(lambda: filt_c_sos(clean_ref))
    t_d_med, t_d_p95 = measure_ms(lambda: filt_d_trim(clean_ext_ref, trim_sec=1.0))

    print(f"\n=== vid.avi WINDOW = {dur_sec:.1f} s ({n_samp} mau) | N_RUNS = {N_RUNS} ===")
    hdr = f"{'Phuong an':<40} {'MAE 1s dau':>12} {'MAE 1s cuoi':>12} {'MAE giua':>10} {'Median HR Err':>15} {'Median(ms)':>11}"
    print(hdr)
    print("-" * 104)
    keys_labels = [
        ("a", f"(a) filtfilt, padlen default={DEFAULT_PADLEN}"),
        ("b", f"(b) filtfilt, padtype='odd' (Current)"),
        ("c", "(c) sosfiltfilt, padlen default"),
        ("d", "(d) extended+trim 1s (extra 1s buffer)"),
    ]
    for (k, label), (tmed, _) in zip(keys_labels, [(t_a_med, t_a_p95), (t_b_med, t_b_p95), (t_c_med, t_c_p95), (t_d_med, t_d_p95)]):
        ms = np.median(maes_start[k])
        me = np.median(maes_end[k])
        mc = np.median(maes_center[k])
        mhr = np.median(hr_errs[k])
        print(f"{label:<40} {ms:>12.4f} {me:>12.4f} {mc:>10.4f} {mhr:>11.3f} BPM {tmed:>9.3f} ms")


if __name__ == "__main__":
    print("=" * 80)
    print("BUOC 1 - DO MEO BIEN CUA FILTER TREN DU LIEU VIDEO THUC TE (vid.avi)")
    print(f"Video: aivitals_engine/samples/vid.avi | fs={FS} Hz | order={ORDER} | [{LOW_CUT}-{HIGH_CUT}] Hz")
    print("=" * 80)

    for dur in [4.0, 8.0]:
        run_window(dur)
