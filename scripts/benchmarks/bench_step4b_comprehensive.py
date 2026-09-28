"""
scripts/benchmarks/bench_step4b_comprehensive.py
=================================================
BUOC 4b - Do luong toan dien theo yeu cau cua User:

A. Kiem chung cac van de:
   (1) Filter chain thuc: detrend + bandpass
   (2) In-band SNR vs Full-band SNR (0.75-2.5 Hz)
   (3) Ly do FP white noise va POS noise deu la 1.70% tai 4s

B. Sweep mach + nhieu trang voi SNR TAI TRONG DAI [0.75, 2.5] Hz:
   - Muc SNR: -10 dB, -5 dB, 0 dB, +5 dB
   - Cua so: 6 s va 8 s
   - N = 2000, seed = 42
   - Thong ke: ACF p50 (med), p5, % >= 0.46; SQI SNR hien tai p50 (med), p5, % >= 0.40

C. Thong ke vi tri lag cua diem cao nhat (histogram tau in [12, 40]):
   - Voi cac ca nhieu (trang, pink, random walk) vuot 0.46
   - Co don o mep (12 hoac 40) khong?

D. So sanh 3 cach lay diem tren CUNG bo tin hieu (cung seed):
   (i) max tho (hien tai): max(rho[12:41])
   (ii) dinh cuc bo that: find_peaks trong khoang [12, 40], khong lay mep
   (iii) dinh dau tien: find_peaks trong [12, 40], lay dinh co lag nho nhat
   Do: mach sach, mach -5 dB, mach 0 dB, % lot luoi o 0.46, va nguong ung voi 1% FPR.

E. So sanh CUNG CUA SO voi SQI SNR hien tai cho random walk va pink noise (6s va 8s).
"""
import sys, os, time
import numpy as np
from scipy import signal

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

if hasattr(sys.stdout, "reconfigure"):
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass

from aivitals_engine.quality.sqi import calculate_bvp_quality, calculate_periodicity_sqi
from aivitals_engine.signal.detrend import smoothness_priors_detrend
from aivitals_engine.signal.filter import butter_bandpass_filter
from aivitals_engine.config.settings import SignalConfig

cfg = SignalConfig()
FS = 30.0
N_RUNS = 2000
SEED = 42

def apply_real_filter_chain(x):
    d = smoothness_priors_detrend(x, lambda_value=cfg.detrend_lambda)
    return butter_bandpass_filter(d, cfg.low_cutoff_hz, cfg.high_cutoff_hz, fs=FS, order=cfg.filter_order)

def get_normalized_acf(bvp):
    sig = np.asarray(bvp, dtype=np.float64).flatten()
    if len(sig) < 16 or np.all(sig == 0):
        return np.zeros(len(sig))
    x = sig - np.mean(sig)
    var = np.sum(x**2)
    if var < 1e-12:
        return np.zeros(len(sig))
    r = signal.correlate(x, x, mode="full")
    r = r[len(x)-1:]
    return r / var

def eval_3_methods(rho, tau_min=12, tau_max=40):
    tau_max = min(tau_max, len(rho) - 1)
    if tau_min > tau_max:
        return 0.0, 0.0, 0.0, None

    window = rho[tau_min : tau_max + 1]
    # (i) Max tho
    max_raw = float(np.max(window))
    argmax_rel = int(np.argmax(window))
    best_tau = tau_min + argmax_rel

    # (ii) Dinh cuc bo that (local peaks)
    # Dung find_peaks tren toan bo rho de tranh meo o bien roi loc tau in [tau_min, tau_max]
    peaks_all, _ = signal.find_peaks(rho)
    valid_peaks = [p for p in peaks_all if tau_min <= p <= tau_max]
    
    if len(valid_peaks) > 0:
        max_local = float(np.max(rho[valid_peaks]))
        # (iii) Dinh dau tien
        first_peak = float(rho[valid_peaks[0]])
    else:
        max_local = 0.0
        first_peak = 0.0

    return max_raw, max_local, first_peak, best_tau

def run_all():
    print("=" * 80)
    print(f"BENCHMARK BUOC 4b (N={N_RUNS}, SEED={SEED}, FS={FS})")
    print("=" * 80)

    for T in [6.0, 8.0]:
        n = int(T * FS)
        t = np.linspace(0, T, n, endpoint=False)
        print(f"\n================================================================================")
        print(f"  CUA SO T = {T:.1f} s ({n} mau)")
        print(f"================================================================================")

        r_pulse = np.random.default_rng(SEED)
        clean_pulses = []
        for _ in range(N_RUNS):
            f0 = r_pulse.uniform(0.8, 2.2)
            phi = r_pulse.uniform(0, 2*np.pi)
            clean_pulses.append(np.sin(2 * np.pi * f0 * t + phi))

        # Generator nhieu
        r_white = np.random.default_rng(SEED + 1)
        white_raw = [r_white.standard_normal(n) for _ in range(N_RUNS)]

        r_pink = np.random.default_rng(SEED + 2)
        f_p = np.fft.rfftfreq(n, 1.0/FS)
        f_p[0] = f_p[1] if len(f_p) > 1 else 1.0
        pink_raw = []
        for _ in range(N_RUNS):
            w = r_pink.standard_normal(n)
            pink_raw.append(np.fft.irfft(np.fft.rfft(w)/np.sqrt(f_p), n=n))

        r_rw = np.random.default_rng(SEED + 3)
        rw_raw = [np.cumsum(r_rw.standard_normal(n)) for _ in range(N_RUNS)]

        # Loc chuoi that
        white_bvp = [apply_real_filter_chain(w) for w in white_raw]
        pink_bvp  = [apply_real_filter_chain(p) for p in pink_raw]
        rw_bvp    = [apply_real_filter_chain(rw) for rw in rw_raw]
        clean_bvp = [apply_real_filter_chain(c) for c in clean_pulses]

        # ------------------------------------------------------------------
        # PHAN B: Sweep mach + nhieu trang voi IN-BAND SNR
        # ------------------------------------------------------------------
        print(f"\n--- PHAN B: SWEEP IN-BAND SNR [-10, -5, 0, +5 dB] (Do sau chuoi loc that) ---")
        print(f"{'Dieu kien SNR':<22} | {'ACF p50 (med)':>13} {'ACF p5':>8} {'% >= 0.46':>10} | {'SQI SNR p50':>12} {'SQI p5':>8} {'% >= 0.40':>10}")
        print("-" * 92)

        in_band_snrs = [-10.0, -5.0, 0.0, 5.0]
        snr_bvps = {}

        for target_snr in in_band_snrs:
            r_mix = np.random.default_rng(SEED + 100 + int(target_snr))
            bvp_mix_list = []
            for clean in clean_pulses:
                w = r_mix.standard_normal(n)
                # Loc in-band truoc de do dung cong suat trong dai [0.75, 2.5] Hz
                c_filt = apply_real_filter_chain(clean)
                w_filt = apply_real_filter_chain(w)
                p_c = np.mean(c_filt ** 2)
                p_w = np.mean(w_filt ** 2)
                # Tinh he so scale de cong suat IN-BAND dat dung target_snr
                target_ratio = 10.0 ** (target_snr / 10.0)
                scale = np.sqrt(p_c / (target_ratio * p_w + 1e-12))
                # Cong tin hieu roi qua chuoi loc
                combined = clean + scale * w
                bvp_mix = apply_real_filter_chain(combined)
                bvp_mix_list.append(bvp_mix)
            snr_bvps[target_snr] = bvp_mix_list

            acf_scores = [calculate_periodicity_sqi(b, fs=FS)[1] for b in bvp_mix_list]
            sqi_scores = [calculate_bvp_quality(b, fs=FS) for b in bvp_mix_list]

            acf_arr = np.array(acf_scores)
            sqi_arr = np.array(sqi_scores)

            print(f"SNR {target_snr:+3.0f} dB in-band    | "
                  f"{np.median(acf_arr):>13.3f} {np.percentile(acf_arr, 5):>8.3f} {np.mean(acf_arr >= 0.46)*100:>9.2f}% | "
                  f"{np.median(sqi_arr):>12.2f} {np.percentile(sqi_arr, 5):>8.2f} {np.mean(sqi_arr >= 0.40)*100:>9.2f}%")

        # ------------------------------------------------------------------
        # PHAN C: Thong ke vi tri lag cua diem cao nhat (histogram tau 12..40)
        # ------------------------------------------------------------------
        print(f"\n--- PHAN C: THONG KE VI TRI LAG TAU CUA CAC CA NHIEU VUOT 0.46 ---")
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

            n_left  = sum(1 for t_val in tau_over_046 if t_val == 12)
            n_right = sum(1 for t_val in tau_over_046 if t_val == 40)
            n_mid   = sum(1 for t_val in tau_over_046 if 12 < t_val < 40)

            print(f"{name:<20} ({n_total} ca / {N_RUNS}):")
            print(f"  Mep trai (tau = 12, 150 BPM) : {n_left:>4} ca ({n_left/n_total*100:5.1f}%)")
            print(f"  Mep phai (tau = 40,  45 BPM) : {n_right:>4} ca ({n_right/n_total*100:5.1f}%)")
            print(f"  O giua   (13 <= tau <= 39)   : {n_mid:>4} ca ({n_mid/n_total*100:5.1f}%)")

        # ------------------------------------------------------------------
        # PHAN D: So sanh 3 cach lay diem tren CUNG bo tin hieu
        # ------------------------------------------------------------------
        print(f"\n--- PHAN D: SO SANH 3 CACH LAY DIEM ACF (Cung seed, cung bo tin hieu) ---")
        print(f"{'Phuong an':<28} | {'Clean':>7} {'-5 dB':>7} {'0 dB':>7} | {'White FP':>9} {'Pink FP':>9} {'RW FP':>9} | {'Nguong 1% White':>15}")
        print("-" * 105)

        eval_sets = {
            "Clean": clean_bvp,
            "-5 dB": snr_bvps[-5.0],
            "0 dB":  snr_bvps[0.0],
            "White": white_bvp,
            "Pink":  pink_bvp,
            "RW":    rw_bvp,
        }

        # Thu thap diem cho ca 3 phuong an
        scores_3 = {"(i) Max tho": {}, "(ii) Dinh cuc bo": {}, "(iii) Dinh dau tien": {}}
        for key in ["(i) Max tho", "(ii) Dinh cuc bo", "(iii) Dinh dau tien"]:
            for dname in eval_sets:
                scores_3[key][dname] = []

        for dname, blist in eval_sets.items():
            for b in blist:
                rho = get_normalized_acf(b)
                m1, m2, m3, _ = eval_3_methods(rho, 12, 40)
                scores_3["(i) Max tho"][dname].append(m1)
                scores_3["(ii) Dinh cuc bo"][dname].append(m2)
                scores_3["(iii) Dinh dau tien"][dname].append(m3)

        for method_name in ["(i) Max tho", "(ii) Dinh cuc bo", "(iii) Dinh dau tien"]:
            m_clean = np.median(scores_3[method_name]["Clean"])
            m_m5    = np.median(scores_3[method_name]["-5 dB"])
            m_0     = np.median(scores_3[method_name]["0 dB"])

            fp_w  = np.mean(np.array(scores_3[method_name]["White"]) >= 0.46) * 100
            fp_p  = np.mean(np.array(scores_3[method_name]["Pink"])  >= 0.46) * 100
            fp_rw = np.mean(np.array(scores_3[method_name]["RW"])    >= 0.46) * 100

            # Nguong ung voi 1% FPR tren White noise (p99)
            th_1pct = float(np.percentile(scores_3[method_name]["White"], 99))

            print(f"{method_name:<28} | {m_clean:>7.3f} {m_m5:>7.3f} {m_0:>7.3f} | {fp_w:>8.2f}% {fp_p:>8.2f}% {fp_rw:>8.2f}% | {th_1pct:>15.3f}")

        # ------------------------------------------------------------------
        # PHAN E: So sanh CUNG CUA SO voi SQI SNR hien tai cho RW va Pink
        # ------------------------------------------------------------------
        print(f"\n--- PHAN E: SO SANH CUNG CUA SO GIUA ACF VA SQI SNR HIEN TAI (RW & Pink) ---")
        print(f"{'Loai nhieu':<20} | {'ACF p50':>9} {'ACF p95':>9} {'ACF %>=0.46':>12} | {'SQI p50':>9} {'SQI p95':>9} {'SQI %>=0.40':>12}")
        print("-" * 82)
        for dname, blist in [("Pink noise (1/f)", pink_bvp), ("Random walk (1/f^2)", rw_bvp)]:
            acf_arr = np.array([calculate_periodicity_sqi(b, fs=FS)[1] for b in blist])
            sqi_arr = np.array([calculate_bvp_quality(b, fs=FS) for b in blist])

            print(f"{dname:<20} | "
                  f"{np.median(acf_arr):>9.3f} {np.percentile(acf_arr, 95):>9.3f} {np.mean(acf_arr >= 0.46)*100:>11.2f}% | "
                  f"{np.median(sqi_arr):>9.2f} {np.percentile(sqi_arr, 95):>9.2f} {np.mean(sqi_arr >= 0.40)*100:>11.2f}%")

if __name__ == "__main__":
    t0 = time.time()
    run_all()
    print(f"\nTong thoi gian chay Buoc 4b: {time.time() - t0:.1f} s")
