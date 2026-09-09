import numpy as np
from scipy import signal

def calculate_bvp_snr(
    bvp_signal: np.ndarray,
    fs: float = 30.0,
    low_cutoff: float = 0.75,
    high_cutoff: float = 2.50
) -> float:
    """
    Tính SNR (Signal-to-Noise Ratio, dB) trực tiếp từ phổ BVP mà không cần biết nhịp tim trước.
    Tập trung vào tỷ số công suất giữa đỉnh chu kỳ tuần hoàn chính (+ họa âm) và nền nhiễu.
    """
    sig = np.asarray(bvp_signal, dtype=np.float64).flatten()
    if len(sig) < 16 or np.all(sig == 0):
        return -10.0

    nfft = max(512, 1 if len(sig) == 0 else 2 ** (len(sig) - 1).bit_length())
    freqs, pxx = signal.periodogram(sig, fs=fs, nfft=nfft, detrend=False)

    # Lọc trong dải tần quan tâm
    band_mask = (freqs >= low_cutoff) & (freqs <= high_cutoff)
    if not np.any(band_mask):
        return -10.0

    band_freqs = freqs[band_mask]
    band_pxx = pxx[band_mask]

    # Đỉnh phổ cực đại f0
    f0 = band_freqs[np.argmax(band_pxx)]
    f1 = 2.0 * f0
    delta_f = 0.1  # Dung sai ±0.1 Hz

    # Vùng tín hiệu: quanh đỉnh chính và họa âm bậc 2
    idx_h1 = (freqs >= (f0 - delta_f)) & (freqs <= (f0 + delta_f))
    idx_h2 = (freqs >= (f1 - delta_f)) & (freqs <= (f1 + delta_f))
    signal_mask = idx_h1 | idx_h2

    # Vùng nhiễu: toàn bộ dải quan tâm trừ vùng tín hiệu
    noise_mask = band_mask & ~signal_mask

    p_signal = np.sum(pxx[signal_mask])
    p_noise = np.sum(pxx[noise_mask])

    if p_noise <= 1e-12:
        return 15.0 if p_signal > 0 else -10.0

    snr_db = 10.0 * np.log10(p_signal / p_noise)
    return float(snr_db)

def calculate_bvp_quality(
    bvp_signal: np.ndarray,
    fs: float = 30.0,
    snr_min: float = -5.0,
    snr_max: float = 10.0
) -> float:
    """
    Chỉ số chất lượng tín hiệu BVP (Signal Quality Index) chuẩn hóa từ 0.0 đến 1.0.
    - >= 0.7: Tín hiệu rõ nét, chu kỳ ổn định
    - 0.4 - 0.7: Tín hiệu trung bình, có nhiễu nhẹ
    - < 0.4: Tín hiệu kém, nhiễu nhiều
    """
    snr_val = calculate_bvp_snr(bvp_signal, fs=fs)
    quality = (snr_val - snr_min) / (snr_max - snr_min)
    return float(round(np.clip(quality, 0.0, 1.0), 2))
