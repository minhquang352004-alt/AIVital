"""
scripts/benchmarks/bench_sqi_window_length.py
==============================================
BUOC 3 - Kiem chung gia thuyet SQI phu thuoc do dai cua so (T = 4s, 6s, 8s).

Thiet lap:
- fs = 30.0 Hz
- T in [4.0, 6.0, 8.0] s (N = 120, 180, 240 mau)
- N = 2000 lan thu moi dieu kien, seed = 42
- Tin hieu mach: f0 in [0.8, 2.2] Hz (ngau nhien deu), pha ngau nhien
- Cac muc SNR: sach (inf), +10 dB, +5 dB, 0 dB
- Cac loai nhieu thuan:
    1. Gaussian trang
    2. Pink noise (1/f)
    3. Random walk (Brownian 1/f^2)
    4. POS tren RGB nhieu (3 kenh RGB doc lap cong nhieu Gaussian + drift nhe)

Cac phuong an delta_f:
  (0) Hien tai: delta_f = 0.10 Hz (co dinh)
  (1) delta_f = 1/T (0.25 Hz o 4s, 0.167 Hz o 6s, 0.125 Hz o 8s)
  (2) delta_f = max(0.10, 0.6 / T) (0.15 Hz o 4s, 0.10 Hz o 6s, 0.10 Hz o 8s)
  (3) delta_f = max(0.10, 0.8 / T) (0.20 Hz o 4s, 0.133 Hz o 6s, 0.10 Hz o 8s)
"""
import sys, os, time
import numpy as np
from scipy import signal

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

if hasattr(sys.stdout, "reconfigure"):
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass

FS = 30.0
N_RUNS = 2000
SEED = 42

rng = np.random.default_rng(SEED)

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
    # ROC AUC via Mann-Whitney U
    pos = np.asarray(pos_scores)
    neg = np.asarray(neg_scores)
    # Count pairs pos > neg + 0.5 * (pos == neg)
    all_scores = np.concatenate([pos, neg])
    ranks = np.argsort(np.argsort(all_scores)) + 1
    rank_pos = np.sum(ranks[:len(pos)])
    n1, n2 = len(pos), len(neg)
    u = rank_pos - n1 * (n1 + 1) / 2.0
    return float(u / (n1 * n2))

# Noise generators
def gen_white(n, r): return r.standard_normal(n)

def gen_pink(n, r):
    w = r.standard_normal(n)
    f = np.fft.rfftfreq(n, 1.0/FS)
    f[0] = f[1] if len(f) > 1 else 1.0
    return np.fft.irfft(np.fft.rfft(w) / np.sqrt(f), n=n)

def gen_rw(n, r): return np.cumsum(r.standard_normal(n))

def gen_pos_rgb_noise(n, r):
    # Simulate 3-channel RGB noise through POS
    R = 160.0 + r.normal(0, 1.0, n)
    G = 110.0 + r.normal(0, 1.0, n)
    B = 85.0  + r.normal(0, 1.0, n)
    rgb = np.column_stack([R, G, B])
    # POS on noise
    l = min(n, 48)
    H = np.zeros(n)
    proj = np.array([[0.0, 1.0, -1.0], [-2.0, 1.0, 1.0]])
    for idx in range(n):
        m = idx - l
        if m >= 0:
            sub = rgb[m:idx, :]
            mean_c = np.mean(sub, axis=0)
            mean_c[mean_c == 0] = 1e-7
            Cn = (sub / mean_c).T
            S = np.matmul(proj, Cn)
            s0, s1 = np.std(S[0]), np.std(S[1])
            alpha = (s0 / s1) if s1 > 1e-7 else 0.0
            h = S[0] + alpha * S[1]
            H[m:idx] += (h - np.mean(h))
    return H

def run_benchmarks():
    print("=" * 80)
    print(f"BUOC 3 - BENCHMARK SQI PHU THUOC DO DAI CUA SO (N={N_RUNS}, SEED={SEED})")
    print("=" * 80)
    
    for T in [4.0, 6.0, 8.0]:
        n_samp = int(T * FS)
        t = np.linspace(0, T, n_samp, endpoint=False)
        print(f"\n====================== WINDOW T = {T:.1f} s ({n_samp} mau) ======================")
        
        # Candidate delta_f definitions for this T:
        cands = {
            "d0_fixed_0.10": 0.10,
            "d1_rayleigh":   1.0 / T,
            "d2_max01_06T":  max(0.10, 0.6 / T),
            "d3_max01_08T":  max(0.10, 0.8 / T),
        }
        
        # 1. Generate clean pulses
        r = np.random.default_rng(SEED)
        clean_pulses = []
        for _ in range(N_RUNS):
            f0 = r.uniform(0.8, 2.2)
            phi = r.uniform(0, 2*np.pi)
            clean_pulses.append(np.sin(2 * np.pi * f0 * t + phi))
            
        # 2. Generate pure noises
        r_noise = np.random.default_rng(SEED + 1)
        noises = {
            "Gaussian_White": [gen_white(n_samp, r_noise) for _ in range(N_RUNS)],
            "Pink_1/f":       [gen_pink(n_samp, r_noise) for _ in range(N_RUNS)],
            "Random_Walk":    [gen_rw(n_samp, r_noise) for _ in range(N_RUNS)],
            "POS_RGB_Noise":  [gen_pos_rgb_noise(n_samp, r_noise) for _ in range(N_RUNS)],
        }
        
        # 3. Generate SNR mixes (0 dB, +5 dB, +10 dB)
        snr_mixes = {}
        for snr_target in [0.0, 5.0, 10.0]:
            r_mix = np.random.default_rng(SEED + int(snr_target) + 10)
            mix_list = []
            for clean in clean_pulses:
                # Add white noise scaled to snr_target in [0.75, 2.5] band
                w = r_mix.standard_normal(n_samp)
                p_s = np.mean(clean ** 2)
                p_w = np.mean(w ** 2)
                target_ratio = 10.0 ** (snr_target / 10.0)
                scale = np.sqrt(p_s / (target_ratio * p_w + 1e-12))
                mix_list.append(clean + scale * w)
            snr_mixes[snr_target] = mix_list

        print(f"\n--- A. DIEM SQI TRUNG VI & AUC TREN TIN HIEU MACH ---")
        print(f"{'Dieu kien':<22} | " + " | ".join([f"{name} (df={df:.3f})" for name, df in cands.items()]))
        print("-" * 88)
        
        # Clean
        row_clean = [f"{'Clean Pulse':<22}"]
        for name, df in cands.items():
            scores = [calc_sqi_custom(s, df) for s in clean_pulses]
            row_clean.append(f"med={np.median(scores):.2f}")
        print(" | ".join(row_clean))
        
        # SNR 10 dB
        for snr_val in [10.0, 5.0, 0.0]:
            row_snr = [f"SNR {snr_val:+2.0f} dB (med / AUC)"]
            white_noise = noises["Gaussian_White"]
            for name, df in cands.items():
                scores = [calc_sqi_custom(s, df) for s in snr_mixes[snr_val]]
                noise_scores = [calc_sqi_custom(s, df) for s in white_noise]
                auc = compute_auc(scores, noise_scores)
                row_snr.append(f"{np.median(scores):.2f} / {auc:.3f}")
            print(" | ".join(row_snr))
            
        print(f"\n--- B. TY LE CHAP NHAN NHAM NHIEU THUAN (SQI >= 0.40) ---")
        print(f"{'Loai nhieu':<22} | " + " | ".join([f"{name} (df={df:.3f})" for name, df in cands.items()]))
        print("-" * 88)
        for noise_name, sig_list in noises.items():
            row_noise = [f"{noise_name:<22}"]
            for name, df in cands.items():
                scores = [calc_sqi_custom(s, df) for s in sig_list]
                fp_pct = np.mean(np.array(scores) >= 0.40) * 100.0
                row_noise.append(f"{fp_pct:6.2f}%")
            print(" | ".join(row_noise))

if __name__ == "__main__":
    t0 = time.time()
    run_benchmarks()
    print(f"\nBenchmark completed in {time.time() - t0:.1f} s")
