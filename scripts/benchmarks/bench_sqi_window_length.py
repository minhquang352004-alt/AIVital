"""
scripts/benchmarks/bench_sqi_window_length.py
==============================================
BUOC 3 - Kiểm chứng giả thuyết SQI phụ thuộc độ dài cửa sổ (T = 4s, 6s, 8s)
trực tiếp trên tín hiệu sóng mạch BVP trích xuất từ video thực tế (aivitals_engine/samples/vid.avi).
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

from aivitals_engine.rppg.pos import POSMethod
from aivitals_engine.signal.resample import resample_to_fixed_fps
from aivitals_engine.signal_pipeline_realtime import RealtimeSignalPipeline

VIDEO_PATH = os.path.join(PROJECT_ROOT, "aivitals_engine", "samples", "vid.avi")
FS = 30.0
N_RUNS = 500
SEED = 42


def extract_bvp_trace_from_vid_avi(n_frames: int = 450) -> np.ndarray:
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


def calc_snr_custom(sig, delta_f, fs=30.0):
    sig = np.asarray(sig, dtype=np.float64).flatten()
    if len(sig) < 16 or np.all(sig == 0):
        return -10.0
    nfft = max(512, 1 if len(sig) == 0 else 2 ** (len(sig) - 1).bit_length())
    freqs, pxx = signal.periodogram(sig, fs=fs, nfft=nfft, detrend=False)

    band_mask = (freqs >= 0.75) & (freqs <= 2.50)
    if not np.any(band_mask):
        return -10.0
    band_freqs = freqs[band_mask]
    band_pxx = pxx[band_mask]

    f0 = band_freqs[np.argmax(band_pxx)]
    f1 = 2.0 * f0

    idx_h1 = (freqs >= (f0 - delta_f)) & (freqs <= (f0 + delta_f))
    idx_h2 = (freqs >= (f1 - delta_f)) & (freqs <= (f1 + delta_f))
    signal_mask = idx_h1 | idx_h2
    noise_mask = band_mask & ~signal_mask

    p_signal = np.sum(pxx[signal_mask])
    p_noise = np.sum(pxx[noise_mask])

    if p_noise <= 1e-12:
        return 15.0 if p_signal > 0 else -10.0
    return float(10.0 * np.log10(p_signal / p_noise))


def calc_sqi_custom(sig, delta_f, fs=30.0):
    snr = calc_snr_custom(sig, delta_f, fs)
    return float(round(np.clip((snr + 5.0) / 15.0, 0.0, 1.0), 2))


def compute_auc(pos_scores, neg_scores):
    pos = np.asarray(pos_scores)
    neg = np.asarray(neg_scores)
    all_scores = np.concatenate([pos, neg])
    ranks = np.argsort(np.argsort(all_scores)) + 1
    rank_pos = np.sum(ranks[: len(pos)])
    n1, n2 = len(pos), len(neg)
    u = rank_pos - n1 * (n1 + 1) / 2.0
    return float(u / (n1 * n2))


def gen_white(n, r):
    return r.standard_normal(n)


def gen_pink(n, r):
    w = r.standard_normal(n)
    f = np.fft.rfftfreq(n, 1.0 / FS)
    f[0] = f[1] if len(f) > 1 else 1.0
    return np.fft.irfft(np.fft.rfft(w) / np.sqrt(f), n=n)


def gen_rw(n, r):
    return np.cumsum(r.standard_normal(n))


def run_benchmarks():
    real_bvp_long = extract_bvp_trace_from_vid_avi(n_frames=450)

    print("=" * 84)
    print(f"BUOC 3 - BENCHMARK SQI THEO DO DAI CUA SO TREN vid.avi (N={N_RUNS}, SEED={SEED})")
    print(f"Video: aivitals_engine/samples/vid.avi | Extracted BVP samples: {len(real_bvp_long)}")
    print("=" * 84)

    for T in [4.0, 6.0, 8.0]:
        n_samp = int(T * FS)
        print(f"\n====================== vid.avi WINDOW T = {T:.1f} s ({n_samp} mau) ======================")

        cands = {
            "d0_fixed_0.10": 0.10,
            "d1_rayleigh": 1.0 / T,
            "d2_max01_06T": max(0.10, 0.6 / T),
            "d3_max01_08T": max(0.10, 0.8 / T),
        }

        max_offset = max(1, len(real_bvp_long) - n_samp)
        clean_pulses = [real_bvp_long[(i % max_offset) : (i % max_offset) + n_samp] for i in range(N_RUNS)]

        r_noise = np.random.default_rng(SEED + 1)
        noises = {
            "Gaussian_White": [gen_white(n_samp, r_noise) for _ in range(N_RUNS)],
            "Pink_1/f": [gen_pink(n_samp, r_noise) for _ in range(N_RUNS)],
            "Random_Walk": [gen_rw(n_samp, r_noise) for _ in range(N_RUNS)],
        }

        snr_mixes = {}
        for snr_target in [0.0, 5.0, 10.0]:
            r_mix = np.random.default_rng(SEED + int(snr_target) + 10)
            mix_list = []
            for clean in clean_pulses:
                w = r_mix.standard_normal(n_samp)
                p_s = np.mean(clean ** 2)
                p_w = np.mean(w ** 2)
                target_ratio = 10.0 ** (snr_target / 10.0)
                scale = np.sqrt(p_s / (target_ratio * p_w + 1e-12))
                mix_list.append(clean + scale * w)
            snr_mixes[snr_target] = mix_list

        print("\n--- A. DIEM SQI TRUNG VI & AUC TREN TIN HIEU MACH vid.avi ---")
        print(f"{'Dieu kien':<22} | " + " | ".join([f"{name} (df={df:.3f})" for name, df in cands.items()]))
        print("-" * 88)

        row_clean = [f"{'vid.avi Clean BVP':<22}"]
        for name, df in cands.items():
            scores = [calc_sqi_custom(s, df) for s in clean_pulses]
            row_clean.append(f"med={np.median(scores):.2f}")
        print(" | ".join(row_clean))

        for snr_val in [10.0, 5.0, 0.0]:
            row_snr = [f"SNR {snr_val:+2.0f} dB (med / AUC)"]
            white_noise = noises["Gaussian_White"]
            for name, df in cands.items():
                scores = [calc_sqi_custom(s, df) for s in snr_mixes[snr_val]]
                noise_scores = [calc_sqi_custom(s, df) for s in white_noise]
                auc = compute_auc(scores, noise_scores)
                row_snr.append(f"{np.median(scores):.2f} / {auc:.3f}")
            print(" | ".join(row_snr))


if __name__ == "__main__":
    run_benchmarks()
