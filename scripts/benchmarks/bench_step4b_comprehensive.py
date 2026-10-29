"""
scripts/benchmarks/bench_step4b_comprehensive.py
=================================================
BUOC 4b - Đo lường toàn diện In-band SNR, ACF lag histogram và SQI
trực tiếp trên chuỗi tín hiệu sóng mạch trích xuất từ video thực tế (aivitals_engine/samples/vid.avi).
"""
import os
import sys
import cv2
import numpy as np
from scipy import signal

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from aivitals_engine.config.settings import SignalConfig
from aivitals_engine.quality.sqi import calculate_bvp_quality, calculate_periodicity_sqi
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


def apply_real_filter_chain(x):
    d = smoothness_priors_detrend(x, lambda_value=cfg.detrend_lambda)
    return butter_bandpass_filter(d, cfg.low_cutoff_hz, cfg.high_cutoff_hz, fs=FS, order=cfg.filter_order)


def get_normalized_acf(bvp):
    sig = np.asarray(bvp, dtype=np.float64).flatten()
    if len(sig) < 16 or np.all(sig == 0):
        return np.zeros(len(sig))
    x = sig - np.mean(sig)
    var = np.sum(x ** 2)
    if var < 1e-12:
        return np.zeros(len(sig))
    r = signal.correlate(x, x, mode="full")
    r = r[len(x) - 1 :]
    return r / var


def eval_3_methods(rho, tau_min=12, tau_max=40):
    tau_max = min(tau_max, len(rho) - 1)
    if tau_min > tau_max:
        return 0.0, 0.0, 0.0, None

    window = rho[tau_min : tau_max + 1]
    max_raw = float(np.max(window))
    argmax_rel = int(np.argmax(window))
    best_tau = tau_min + argmax_rel

    peaks_all, _ = signal.find_peaks(rho)
    valid_peaks = [p for p in peaks_all if tau_min <= p <= tau_max]

    if len(valid_peaks) > 0:
        max_local = float(np.max(rho[valid_peaks]))
        first_peak = float(rho[valid_peaks[0]])
    else:
        max_local = 0.0
        first_peak = 0.0

    return max_raw, max_local, first_peak, best_tau


def run_all():
    real_bvp_long = extract_real_pulse_from_vid_avi(n_frames=450)

    print("=" * 88)
    print(f"BENCHMARK BUOC 4b TREN DU LIEU VIDEO THUC TE vid.avi (N={N_RUNS}, SEED={SEED}, FS={FS})")
    print(f"Video: aivitals_engine/samples/vid.avi | Extracted BVP samples: {len(real_bvp_long)}")
    print("=" * 88)

    for T in [6.0, 8.0]:
        n = int(T * FS)
        max_offset = max(1, len(real_bvp_long) - n)
        print(f"\n================================================================================")
        print(f"  vid.avi WINDOW T = {T:.1f} s ({n} mau)")
        print(f"================================================================================")

        clean_pulses = [real_bvp_long[(i % max_offset) : (i % max_offset) + n] for i in range(N_RUNS)]

        r_white = np.random.default_rng(SEED + 1)
        white_raw = [r_white.standard_normal(n) for _ in range(N_RUNS)]

        r_pink = np.random.default_rng(SEED + 2)
        f_p = np.fft.rfftfreq(n, 1.0 / FS)
        f_p[0] = f_p[1] if len(f_p) > 1 else 1.0
        pink_raw = [
            np.fft.irfft(np.fft.rfft(r_pink.standard_normal(n)) / np.sqrt(f_p), n=n)
            for _ in range(N_RUNS)
        ]

        r_rw = np.random.default_rng(SEED + 3)
        rw_raw = [np.cumsum(r_rw.standard_normal(n)) for _ in range(N_RUNS)]

        white_bvp = [apply_real_filter_chain(w) for w in white_raw]
        pink_bvp = [apply_real_filter_chain(p) for p in pink_raw]
        rw_bvp = [apply_real_filter_chain(rw) for rw in rw_raw]

        print("\n--- PHAN B: SWEEP IN-BAND SNR TREN MACH vid.avi [-10, -5, 0, +5 dB] ---")
        print(
            f"{'Dieu kien SNR':<22} | {'ACF p50 (med)':>13} {'ACF p5':>8} {'% >= 0.46':>10} | "
            f"{'SQI SNR p50':>12} {'SQI p5':>8} {'% >= 0.40':>10}"
        )
        print("-" * 92)

        for target_snr in [-10.0, -5.0, 0.0, 5.0]:
            r_mix = np.random.default_rng(SEED + 100 + int(target_snr))
            bvp_mix_list = []
            for clean in clean_pulses:
                w = r_mix.standard_normal(n)
                c_filt = apply_real_filter_chain(clean)
                w_filt = apply_real_filter_chain(w)
                p_c = np.mean(c_filt ** 2)
                p_w = np.mean(w_filt ** 2)
                target_ratio = 10.0 ** (target_snr / 10.0)
                scale = np.sqrt(p_c / (target_ratio * p_w + 1e-12))
                bvp_mix = apply_real_filter_chain(clean + scale * w)
                bvp_mix_list.append(bvp_mix)

            acf_arr = np.array([calculate_periodicity_sqi(b, fs=FS)[1] for b in bvp_mix_list])
            sqi_arr = np.array([calculate_bvp_quality(b, fs=FS) for b in bvp_mix_list])

            print(
                f"SNR {target_snr:+3.0f} dB in-band    | "
                f"{np.median(acf_arr):>13.3f} {np.percentile(acf_arr, 5):>8.3f} {np.mean(acf_arr >= 0.46)*100:>9.2f}% | "
                f"{np.median(sqi_arr):>12.2f} {np.percentile(sqi_arr, 5):>8.2f} {np.mean(sqi_arr >= 0.40)*100:>9.2f}%"
            )

        print("\n--- PHAN C: THONG KE VI TRI LAG TAU CUA CAC CA NHIEU VUOT 0.46 ---")
        for name, bvps in [("Gaussian trang", white_bvp), ("Pink noise", pink_bvp), ("Random walk", rw_bvp)]:
            tau_over_046 = []
            for b in bvps:
                rho = get_normalized_acf(b)
                m_raw, _, _, best_t = eval_3_methods(rho, 12, 40)
                if m_raw >= 0.46:
                    tau_over_046.append(best_t)

            n_total = len(tau_over_046)
            if n_total == 0:
                print(f"{name:<20}: 0 ca vuot 0.46")
                continue

            n_left = sum(1 for t_val in tau_over_046 if t_val == 12)
            n_right = sum(1 for t_val in tau_over_046 if t_val == 40)
            n_mid = sum(1 for t_val in tau_over_046 if 12 < t_val < 40)
            print(
                f"{name:<20} ({n_total} ca / {N_RUNS}): "
                f"tau=12: {n_left} | tau=40: {n_right} | mid: {n_mid}"
            )


if __name__ == "__main__":
    run_all()
