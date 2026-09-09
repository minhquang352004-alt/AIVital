"""
AIVitals Vitals Module - Heart Rate (HR)
Trích xuất nhịp tim (BPM) từ sóng BVP bằng FFT hoặc Peak Detection.
Kế thừa & tối ưu từ rPPG-Toolbox/evaluation/post_process.py
"""

from typing import Optional
import numpy as np
import scipy.signal


def _next_power_of_2(x: int) -> int:
    """Tính lũy thừa 2 gần nhất để tối ưu FFT periodogram."""
    return 1 if x == 0 else 2 ** (x - 1).bit_length()


def calculate_fft_hr(
    bvp_signal: np.ndarray,
    fs: float = 30.0,
    low_cutoff_hz: float = 0.75,
    high_cutoff_hz: float = 2.50
) -> float:
    """
    Ước lượng nhịp tim (BPM) qua biến đổi Fourier (FFT Periodogram).
    Tham chiếu: rPPG-Toolbox evaluation/post_process.py (_calculate_fft_hr)

    Args:
        bvp_signal: Tín hiệu BVP 1D
        fs: Tần số lấy mẫu (FPS)
        low_cutoff_hz: Tần số cắt thấp (0.75 Hz = 45 BPM)
        high_cutoff_hz: Tần số cắt cao (2.50 Hz = 150 BPM)

    Returns:
        Nhịp tim ước lượng (BPM)
    """
    sig = np.asarray(bvp_signal, dtype=np.float64).flatten()
    if len(sig) < 16:
        return 0.0

    nfft = max(512, _next_power_of_2(len(sig)))
    f_ppg, pxx_ppg = scipy.signal.periodogram(sig, fs=fs, nfft=nfft, detrend=False)

    mask = (f_ppg >= low_cutoff_hz) & (f_ppg <= high_cutoff_hz)
    if not np.any(mask):
        return 0.0

    band_f = f_ppg[mask]
    band_pxx = pxx_ppg[mask]

    peak_freq = band_f[np.argmax(band_pxx)]
    return float(peak_freq * 60.0)


def calculate_peak_hr(bvp_signal: np.ndarray, fs: float = 30.0) -> float:
    """
    Ước lượng nhịp tim (BPM) qua phát hiện khoảng cách giữa các đỉnh xung (Peak Detection).
    Tham chiếu: rPPG-Toolbox evaluation/post_process.py (_calculate_peak_hr)

    Args:
        bvp_signal: Tín hiệu BVP 1D
        fs: Tần số lấy mẫu (FPS)

    Returns:
        Nhịp tim ước lượng (BPM)
    """
    sig = np.asarray(bvp_signal, dtype=np.float64).flatten()
    if len(sig) < 16:
        return 0.0

    # Khoảng cách tối thiểu giữa 2 đỉnh là 0.4s (tương ứng nhịp tối đa 150 BPM)
    min_dist = max(1, int(fs * 0.4))
    peaks, _ = scipy.signal.find_peaks(sig, distance=min_dist)
    if len(peaks) < 2:
        return 0.0

    mean_diff = np.mean(np.diff(peaks))
    if mean_diff <= 0:
        return 0.0

    return float(60.0 / (mean_diff / fs))
