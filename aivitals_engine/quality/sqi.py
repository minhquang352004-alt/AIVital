from typing import Tuple
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


def calculate_periodicity_sqi(
    bvp_signal: np.ndarray,
    fs: float = 30.0,
    min_bpm: float = 45.0,
    max_bpm: float = 150.0,
) -> Tuple[float, float]:
    """
    Tính chỉ số chất lượng tuần hoàn (Periodicity SQI) dựa trên đỉnh hàm tự tương quan
    (Autocorrelation Function - ACF) chuẩn hóa trong dải lag tương ứng với nhịp tim sinh lý.

    Thuật toán:
        1. Trừ trung bình tín hiệu: x_tilde = x - mean(x).
        2. Tính tự tương quan không trễ: R(0) = sum(x_tilde^2).
        3. Tự tương quan chuẩn hóa: rho(tau) = R(tau) / R(0).
        4. Tìm cực đại rho(tau) trong dải lag [tau_min, tau_max] ứng với [min_bpm, max_bpm]:
           tau_min = floor(60 * fs / max_bpm)
           tau_max = ceil(60 * fs / min_bpm)
        5. Điểm chuẩn hóa score = clip(raw_peak, 0.0, 1.0).

    Args:
        bvp_signal: Tín hiệu sóng BVP 1D.
        fs: Tần số lấy mẫu (FPS), mặc định 30.0 Hz.
        min_bpm: Giới hạn dưới tần số nhịp tim sinh lý (BPM), mặc định 45.0 (lag ~1.33 s).
        max_bpm: Giới hạn trên tần số nhịp tim sinh lý (BPM), mặc định 150.0 (lag ~0.40 s).

    Returns:
        (score, raw_peak):
            score: Điểm chất lượng tuần hoàn trong đoạn [0.0, 1.0] (làm tròn 2 chữ số thập phân).
            raw_peak: Giá trị đỉnh ACF chuẩn hóa thô trong đoạn [-1.0, 1.0] (làm tròn 4 chữ số thập phân).

    CẢNH BÁO / GIỚI HẠN ĐÃ XÁC MINH BẰNG THỰC NGHIỆM:
        Chỉ số này KHÔNG phân biệt được sóng mạch sinh học thật với các nguồn nhiễu tuần hoàn
        đơn tần (như sóng sin nhân tạo 1.2 Hz phát sinh từ chuyển động gật đầu nhịp nhàng hoặc
        đèn chớp chu kỳ cố định), vì mọi dao động có tính tuần hoàn đều có đỉnh ACF rất cao (~0.9 - 1.0).
    """
    sig = np.asarray(bvp_signal, dtype=np.float64).flatten()
    if len(sig) < 16 or np.all(sig == 0):
        return 0.0, 0.0

    tau_min = int(np.floor(fs * 60.0 / max_bpm))
    tau_max = int(np.ceil(fs * 60.0 / min_bpm))
    tau_max = min(tau_max, len(sig) - 1)

    if tau_min > tau_max or tau_min >= len(sig):
        return 0.0, 0.0

    x = sig - np.mean(sig)
    var = np.sum(x ** 2)
    if var < 1e-12:
        return 0.0, 0.0

    r = signal.correlate(x, x, mode="full")
    r = r[len(x) - 1 :]  # Các độ trễ không âm: tau = 0, 1, ..., N - 1
    rho = r / var

    window = rho[tau_min : tau_max + 1]
    if len(window) == 0:
        return 0.0, 0.0

    raw_peak = float(np.max(window))
    score = float(round(np.clip(raw_peak, 0.0, 1.0), 2))
    return score, float(round(raw_peak, 4))

def calculate_cross_roi_sqi(sub_rgbs: dict, fs: float) -> dict:
    """
    Tính chỉ số đồng thuận giữa các vùng con (Cross-ROI SQI).
    Sử dụng thuật toán rPPG gốc (POS) trên từng vùng con,
    và tính hệ số tương quan Pearson giữa 3 cặp: Trán-MáTrái, Trán-MáPhải, MáTrái-MáPhải.
    
    Args:
        sub_rgbs: Dictionary chứa tín hiệu RGB của từng vùng ('forehead', 'left_cheek', 'right_cheek').
        fs: Tần số lấy mẫu (Hz).
        
    Returns:
        Dict chứa r_forehead_left, r_forehead_right, r_left_right, r_mean, r_min.
    """
    from aivitals_engine.rppg.pos import POSMethod
    pos = POSMethod(fps=fs)
    
    def process_roi(rgb):
        if len(rgb) == 0 or np.all(rgb == 0):
            return np.zeros(len(rgb)) if len(rgb) > 0 else np.zeros(1)
        return pos.process(rgb)
        
    p_f = process_roi(sub_rgbs.get('forehead', np.array([])))
    p_l = process_roi(sub_rgbs.get('left_cheek', np.array([])))
    p_r = process_roi(sub_rgbs.get('right_cheek', np.array([])))
    
    def calc_pearson(x, y):
        if len(x) < 2 or len(y) < 2 or len(x) != len(y):
            return 0.0
        if np.std(x) < 1e-7 or np.std(y) < 1e-7:
            return 0.0
        return float(np.corrcoef(x, y)[0, 1])
        
    r_fl = calc_pearson(p_f, p_l)
    r_fr = calc_pearson(p_f, p_r)
    r_lr = calc_pearson(p_l, p_r)
    
    r_mean = float(np.mean([r_fl, r_fr, r_lr]))
    r_min = float(np.min([r_fl, r_fr, r_lr]))
    
    return {
        'r_forehead_left': r_fl,
        'r_forehead_right': r_fr,
        'r_left_right': r_lr,
        'r_mean': r_mean,
        'r_min': r_min
    }

