"""
scripts/benchmarks/bench_periodicity_sqi.py
============================================
BUOC 4 - Benchmark chi tiet cho Periodicity SQI (ACF dinh chuan hoa).

Thiet lap:
- Cua so T in [6.0, 8.0] s (180 va 240 mau tai fs = 30.0 Hz)
- N = 2000 lan lap moi dieu kien, seed = 42
- Tat ca tin hieu DI QUA CHUOI LOC THAT cua repo:
    smoothness_priors_detrend(lambda=100) -> butter_bandpass_filter(0.75-2.5 Hz, order=1)
- Tin hieu khao sat:
    1. Mach sach (f0 in [0.8, 2.2] Hz)
    2. Mach + nhieu Gaussian trang (SNR 10 dB, 5 dB, 0 dB)
    3. Nhieu Gaussian trang thuan
    4. Nhieu Pink (1/f)
    5. Nhieu Random Walk (Brownian)
    6. Sin don tan 1.2 Hz (mo phong nhieu chuyen dong / den chớp tuan hoan)

Xac minh:
- Nguong khoi dau: 0.46 (p99 tren cua so 8s)
- Random walk co thuc su thap hon mach khong?
"""
import sys, os, time
import numpy as np
from scipy import signal

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

if hasattr(sys.stdout, "reconfigure"):
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass

from aivitals_engine.quality.sqi import calculate_periodicity_sqi
from aivitals_engine.signal.detrend import smoothness_priors_detrend
from aivitals_engine.signal.filter import butter_bandpass_filter
from aivitals_engine.config.settings import SignalConfig

cfg = SignalConfig()
FS = 30.0
N_RUNS = 2000
SEED = 42

rng = np.random.default_rng(SEED)

def filter_pipeline(x):
    d = smoothness_priors_detrend(x, lambda_value=cfg.detrend_lambda)
    return butter_bandpass_filter(d, cfg.low_cutoff_hz, cfg.high_cutoff_hz, fs=FS, order=cfg.filter_order)

def run_benchmark():
    print("=" * 80)
    print(f"BUOC 4 - BENCHMARK PERIODICITY SQI (ACF CHUAN HOA) - N={N_RUNS}, SEED={SEED}")
    print("=" * 80)

    for T in [6.0, 8.0]:
        n = int(T * FS)
        t = np.linspace(0, T, n, endpoint=False)
        print(f"\n====================== WINDOW T = {T:.1f} s ({n} mau) ======================")

        # 1. Clean pulse
        r_pulse = np.random.default_rng(SEED)
        clean_pulses = []
        for _ in range(N_RUNS):
            f0 = r_pulse.uniform(0.8, 2.2)
            phi = r_pulse.uniform(0, 2*np.pi)
            clean_pulses.append(np.sin(2 * np.pi * f0 * t + phi))

        # 2. White noise
        r_white = np.random.default_rng(SEED + 1)
        white_noises = [r_white.standard_normal(n) for _ in range(N_RUNS)]

        # 3. Pink noise
        r_pink = np.random.default_rng(SEED + 2)
        pink_noises = []
        f_pink = np.fft.rfftfreq(n, 1.0/FS)
        f_pink[0] = f_pink[1] if len(f_pink) > 1 else 1.0
        for _ in range(N_RUNS):
            w = r_pink.standard_normal(n)
            p = np.fft.irfft(np.fft.rfft(w) / np.sqrt(f_pink), n=n)
            pink_noises.append(p)

        # 4. Random walk
        r_rw = np.random.default_rng(SEED + 3)
        rw_noises = [np.cumsum(r_rw.standard_normal(n)) for _ in range(N_RUNS)]

        # 5. Artificial 1.2 Hz periodic artifact
        periodic_artifacts = [np.sin(2 * np.pi * 1.2 * t + r_pulse.uniform(0, 2*np.pi)) for _ in range(N_RUNS)]

        # 6. SNR mixtures
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
            ("Mach sach (Clean)", clean_pulses),
            ("SNR +10 dB", snr_mixes[10.0]),
            ("SNR +5 dB", snr_mixes[5.0]),
            ("SNR 0 dB", snr_mixes[0.0]),
            ("Gaussian trang", white_noises),
            ("Pink noise (1/f)", pink_noises),
            ("Random walk (1/f^2)", rw_noises),
            ("Nhiễu chu kỳ 1.2Hz (docstring)", periodic_artifacts),
        ]

        hdr = f"{'Loai tin hieu / nhieu':<32} {'p50 (med)':>10} {'p95':>8} {'p99':>8} {'% >= 0.46 (lọt lưới)':>22}"
        print(hdr)
        print("-" * 84)

        for label, sig_list in datasets:
            raw_peaks = []
            for raw_sig in sig_list:
                bvp = filter_pipeline(raw_sig)
                _, peak = calculate_periodicity_sqi(bvp, fs=FS, min_bpm=cfg.periodicity_min_bpm, max_bpm=cfg.periodicity_max_bpm)
                raw_peaks.append(peak)

            arr = np.array(raw_peaks)
            p50 = np.median(arr)
            p95 = np.percentile(arr, 95)
            p99 = np.percentile(arr, 99)
            fp  = np.mean(arr >= cfg.periodicity_threshold) * 100.0

            print(f"{label:<32} {p50:>10.3f} {p95:>8.3f} {p99:>8.3f} {fp:>21.2f}%")

if __name__ == "__main__":
    t0 = time.time()
    run_benchmark()
    print(f"\nDa xong trong {time.time() - t0:.1f} s")
