"""
scripts/benchmarks/bench_filter_edge.py
========================================
BUOC 1 - Do meo bien cua filter: so sanh 4 phuong an.

Chay tu thu muc goc AIVital/:
    python scripts/benchmarks/bench_filter_edge.py

Khong sua bat ky file source nao.

Thiet lap:
- fs = 30.0 Hz
- Cua so: 4.0 s (120 mau) va 8.0 s (240 mau)
- N_RUNS = 500 tin hieu kiem tra (nhieu tan so va pha ngau nhien)
- SEED = 42
- Dung dung bo loc cua repo: butter bac 1, [0.75, 2.5] Hz, filtfilt
- Muc tieu: sin sach + sin + nhieu Gaussian in-band SNR 0 dB

4 phuong an:
  (a) Hien tai: filtfilt(b, a, data) -- khong truyen padlen (scipy mac dinh: 3*max(len(a),len(b)))
  (b) filtfilt voi padlen = 3 * N_SAMP (lon hon so voi mac dinh)
  (c) sosfiltfilt (sos precision cao hon, padding mac dinh)
  (d) Loc tren cua so dai hon (8+2=10 s hay 4+2=6 s), cat 1 s hai dau, lay 8 s hay 4 s giua

Bao cao voi moi phuong an:
- MAE 1 s dau, 1 s cuoi, vung giua (tren sin sach)
- Sai so HR (FFT, tren sin + nhieu)
- Thoi gian chay (ms)
"""
import sys
import os
import time
import numpy as np
from scipy import signal as scipy_signal

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from aivitals_engine.signal.detrend import smoothness_priors_detrend
from aivitals_engine.vitals.hr import calculate_fft_hr
from aivitals_engine.config.settings import SignalConfig

# --- CONFIG -------------------------------------------------------------------
FS      = 30.0
N_RUNS  = 500
SEED    = 42
LOW_CUT = 0.75
HIGH_CUT = 2.5
ORDER   = 1   # Dung dung bac 1 nhu config/settings.py
BUDGET_MS = 1000.0 / FS

cfg = SignalConfig()
rng = np.random.default_rng(SEED)

# Kiem tra nhanh: scipy default padlen cho bac 1
b_ref, a_ref = scipy_signal.butter(ORDER, [LOW_CUT / (0.5 * FS), HIGH_CUT / (0.5 * FS)], btype="bandpass")
DEFAULT_PADLEN = 3 * max(len(a_ref), len(b_ref))
sos_ref = scipy_signal.butter(ORDER, [LOW_CUT / (0.5 * FS), HIGH_CUT / (0.5 * FS)], btype="bandpass", output="sos")

# --- FILTER IMPLEMENTATIONS ---------------------------------------------------
def build_ba(fs):
    nyq = 0.5 * fs
    low  = max(0.001, min(LOW_CUT / nyq, 0.99))
    high = max(low + 0.001, min(HIGH_CUT / nyq, 0.999))
    return scipy_signal.butter(ORDER, [low, high], btype="bandpass")

def build_sos(fs):
    nyq = 0.5 * fs
    low  = max(0.001, min(LOW_CUT / nyq, 0.99))
    high = max(low + 0.001, min(HIGH_CUT / nyq, 0.999))
    return scipy_signal.butter(ORDER, [low, high], btype="bandpass", output="sos")

b_coef, a_coef = build_ba(FS)
sos_coef = build_sos(FS)

def filt_a_current(x):
    """Phuong an (a): filtfilt khong truyen padlen (scipy mac dinh)."""
    if len(x) < 9:
        return x
    return scipy_signal.filtfilt(b_coef, a_coef, x.astype(np.float64))

def filt_b_padlen(x, n_samp):
    """Phuong an (b): filtfilt voi padlen = 3 * N_SAMP."""
    if len(x) < 9:
        return x
    padlen = 3 * n_samp
    if padlen >= len(x):
        padlen = len(x) - 1
    return scipy_signal.filtfilt(b_coef, a_coef, x.astype(np.float64), padlen=padlen)

def filt_c_sos(x):
    """Phuong an (c): sosfiltfilt (mac dinh padding)."""
    if len(x) < 9:
        return x
    return scipy_signal.sosfiltfilt(sos_coef, x.astype(np.float64))

def filt_d_trim(x, trim_sec=1.0):
    """
    Phuong an (d): loc tren cua so goc, cat trim_sec o hai dau, tra ve phan giua.
    Do tre them: trim_sec (khong co du lieu tuong lai -> chi cat bien truoc,
    bien sau la bien cua cua so hien tai).
    Tra ve doan [trim:] de bao toan do dai, cap nhat nhat quan voi cua so 'hien tai'.
    De giu do dai = N_SAMP, HAM NAY nhan mang da co them trim_sec o dau (extended).
    Trong kich ban thuc: buffer can giu (N + trim_sec*fs) mau.
    """
    if len(x) < 9:
        return x
    filtered = scipy_signal.filtfilt(b_coef, a_coef, x.astype(np.float64))
    trim_n = int(trim_sec * FS)
    return filtered[trim_n:]   # cat bien dau, giu bien cuoi nguyen (van co meo)

# --- METRICS ------------------------------------------------------------------
def edge_mae(original, filtered, n_1s):
    """
    Tinh MAE tren 3 vung: 1s dau, 1s cuoi, phan giua.
    So sanh filtered vs original (sin sach).
    Chi su dung phan giua neu dai > 2*n_1s.
    """
    n = len(original)
    if n <= 2 * n_1s:
        return np.nan, np.nan, np.nan
    mae_start  = np.mean(np.abs(filtered[:n_1s]  - original[:n_1s]))
    mae_end    = np.mean(np.abs(filtered[-n_1s:] - original[-n_1s:]))
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

# --- EXPERIMENT PER WINDOW LENGTH ---------------------------------------------
def run_window(dur_sec):
    n_samp = int(dur_sec * FS)
    n_1s   = int(1.0 * FS)
    t      = np.linspace(0, dur_sec, n_samp, endpoint=False)

    maes_start  = {k: [] for k in ["a", "b", "c", "d"]}
    maes_end    = {k: [] for k in ["a", "b", "c", "d"]}
    maes_center = {k: [] for k in ["a", "b", "c", "d"]}
    hr_errs     = {k: [] for k in ["a", "b", "c", "d"]}
    true_hrs    = []

    # --- D extended window pre-computation ---
    trim_n = int(1.0 * FS)
    n_ext  = n_samp + trim_n    # extended window for option (d)

    for _ in range(N_RUNS):
        # Random pulse frequency and phase
        f0  = rng.uniform(0.8, 2.3)
        phi = rng.uniform(0, 2 * np.pi)
        true_hr = f0 * 60.0
        true_hrs.append(true_hr)

        # Clean sine (ground truth for MAE)
        clean = np.sin(2 * np.pi * f0 * t + phi)

        # Noisy signal for HR error (in-band SNR = 0 dB: equal power pulse and noise)
        noise = rng.standard_normal(n_samp)
        noise_filt = scipy_signal.filtfilt(b_coef, a_coef, noise)
        p_pulse = np.mean(clean ** 2)
        p_noise = np.mean(noise_filt ** 2)
        scale   = np.sqrt(p_pulse / (p_noise + 1e-12))
        noisy   = clean + scale * noise_filt

        # Option (a) - current
        fa = filt_a_current(clean)
        fn_a = filt_a_current(noisy)
        s, e, c = edge_mae(clean, fa, n_1s)
        maes_start["a"].append(s); maes_end["a"].append(e); maes_center["a"].append(c)
        hr_errs["a"].append(abs(calculate_fft_hr(fn_a, fs=FS) - true_hr))

        # Option (b) - large padlen
        fb = filt_b_padlen(clean, n_samp)
        fn_b = filt_b_padlen(noisy, n_samp)
        s, e, c = edge_mae(clean, fb, n_1s)
        maes_start["b"].append(s); maes_end["b"].append(e); maes_center["b"].append(c)
        hr_errs["b"].append(abs(calculate_fft_hr(fn_b, fs=FS) - true_hr))

        # Option (c) - sosfiltfilt
        fc = filt_c_sos(clean)
        fn_c = filt_c_sos(noisy)
        s, e, c = edge_mae(clean, fc, n_1s)
        maes_start["c"].append(s); maes_end["c"].append(e); maes_center["c"].append(c)
        hr_errs["c"].append(abs(calculate_fft_hr(fn_c, fs=FS) - true_hr))

        # Option (d) - extended window + trim (simulate: buffer has 1s extra at front)
        t_ext   = np.linspace(-1.0, dur_sec, n_ext, endpoint=False)
        clean_ext = np.sin(2 * np.pi * f0 * t_ext + phi)
        noisy_ext = clean_ext + scale * scipy_signal.filtfilt(b_coef, a_coef, rng.standard_normal(n_ext))
        fd = filt_d_trim(clean_ext, trim_sec=1.0)
        fn_d = filt_d_trim(noisy_ext, trim_sec=1.0)
        # fd and fn_d have length n_samp (trimmed 1s from front)
        s, e, c = edge_mae(clean, fd[:n_samp], n_1s)
        maes_start["d"].append(s); maes_end["d"].append(e); maes_center["d"].append(c)
        hr_errs["d"].append(abs(calculate_fft_hr(fn_d[:n_samp], fs=FS) - true_hr))

    # --- TIMING (on fixed clean sine for reproducibility) ---
    f0_fixed  = 1.2
    clean_ref = np.sin(2 * np.pi * f0_fixed * t)
    clean_ext_ref = np.sin(2 * np.pi * f0_fixed * np.linspace(-1.0, dur_sec, n_ext, endpoint=False))

    t_a_med, t_a_p95 = measure_ms(lambda: filt_a_current(clean_ref))
    t_b_med, t_b_p95 = measure_ms(lambda: filt_b_padlen(clean_ref, n_samp))
    t_c_med, t_c_p95 = measure_ms(lambda: filt_c_sos(clean_ref))
    t_d_med, t_d_p95 = measure_ms(lambda: filt_d_trim(clean_ext_ref, trim_sec=1.0))

    # --- PRINT ------------------------------------------------------------------
    print(f"\n=== WINDOW = {dur_sec:.1f} s ({n_samp} mau) | N_RUNS = {N_RUNS} | SEED = {SEED} ===")
    print(f"  scipy default padlen = {DEFAULT_PADLEN} mau, phuong an (b) padlen = {min(3*n_samp, n_samp-1)} mau")
    print(f"\n--- SAI SO BIEN (MAE tren sin sach so voi clean - phuong an tot hon = thap hon) ---")
    hdr = f"{'Phuong an':<40} {'MAE 1s dau':>12} {'MAE 1s cuoi':>12} {'MAE giua':>10} {'Ti le cuoi/giua':>16}"
    print(hdr)
    print("-" * 95)
    keys_labels = [
        ("a", f"(a) filtfilt, padlen default={DEFAULT_PADLEN}"),
        ("b", f"(b) filtfilt, padlen=3xN={min(3*n_samp,n_samp-1)}"),
        ("c", "(c) sosfiltfilt, padlen default"),
        ("d", "(d) extended+trim 1s (do tre = 1s them vao buffer)"),
    ]
    for k, label in keys_labels:
        ms = np.median(maes_start[k])
        me = np.median(maes_end[k])
        mc = np.median(maes_center[k])
        ratio = me / mc if mc > 1e-12 else float("nan")
        print(f"{label:<40} {ms:>12.4f} {me:>12.4f} {mc:>10.4f} {ratio:>15.2f}x")

    print(f"\n--- SAI SO HR (|HR_uoc_luong - HR_that|, BPM) - sin + nhieu in-band 0 dB ---")
    hdr2 = f"{'Phuong an':<40} {'Median err BPM':>15} {'p95 err BPM':>13}"
    print(hdr2)
    print("-" * 72)
    for k, label in keys_labels:
        med_hr = np.median(hr_errs[k])
        p95_hr = np.percentile(hr_errs[k], 95)
        print(f"{label:<40} {med_hr:>15.3f} {p95_hr:>13.3f}")

    print(f"\n--- THOI GIAN CHAY (tren sin sach co dinh) ---")
    hdr3 = f"{'Phuong an':<40} {'Median(ms)':>12} {'p95(ms)':>9} {'% 33ms':>8}"
    print(hdr3)
    print("-" * 72)
    for (k, label), (tmed, tp95) in zip(keys_labels, [
            (t_a_med, t_a_p95), (t_b_med, t_b_p95), (t_c_med, t_c_p95), (t_d_med, t_d_p95)]):
        print(f"{label:<40} {tmed:>12.3f} {tp95:>9.3f} {tmed/BUDGET_MS*100:>7.1f}%")

    print(f"\n  Ghi chu phuong an (d): can buffer giu them {trim_n} mau (1 s) o dau cua so.")
    print(f"  Do tre cua so (d): bien cuoi la bien moi nhat, bien dau bi cat -> KHONG them do tre.")
    print(f"  Tuy nhien, tong so mau yeu cau tang tu {n_samp} len {n_ext} ({n_ext/FS:.1f}s).")


if __name__ == "__main__":
    print("=" * 72)
    print("BUOC 1 - DO MEO BIEN CUA FILTER: 4 PHUONG AN")
    print(f"Config: fs={FS} Hz | order={ORDER} | [{LOW_CUT}-{HIGH_CUT}] Hz | N_RUNS={N_RUNS} | SEED={SEED}")
    print(f"Frame size khi do: N/A (chi do filter tren mang 1D, KHONG qua Face Detect)")
    print("=" * 72)

    for dur in [4.0, 8.0]:
        run_window(dur)
