from functools import lru_cache
import numpy as np
from scipy import signal


@lru_cache(maxsize=32)
def _get_butter_ba(order: int, low: float, high: float):
    """Lưu cache hệ số bộ lọc Butterworth (b, a) để tránh tính lại ở mỗi frame."""
    return signal.butter(order, [low, high], btype="bandpass")


def butter_bandpass_filter(
    data: np.ndarray,
    lowcut: float,
    highcut: float,
    fs: float,
    order: int = 1
) -> np.ndarray:
    """
    Bộ lọc dải thông Butterworth 2 chiều (Zero-phase filtfilt) với đối xứng biên lẻ
    (odd padding) để giảm méo biên (edge ringing) trên cửa sổ trượt thời gian thực.

    Args:
        data: Tín hiệu 1D cần lọc
        lowcut: Tần số cắt thấp (Hz)
        highcut: Tần số cắt cao (Hz)
        fs: Tần số lấy mẫu (FPS)
        order: Bậc bộ lọc (thường là 1 đến 3)
    """
    data_arr = np.asarray(data, dtype=np.float64).flatten()
    if len(data_arr) < 9:
        return data_arr

    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq

    # Kiểm tra giới hạn Nyquist
    low = round(max(0.001, min(low, 0.99)), 6)
    high = round(max(low + 0.001, min(high, 0.999)), 6)

    b, a = _get_butter_ba(int(order), low, high)
    padlen = min(3 * (max(len(a), len(b)) - 1), len(data_arr) - 1)
    filtered = signal.filtfilt(b, a, data_arr, padtype="odd", padlen=padlen)
    return filtered


def normalize_signal(data: np.ndarray) -> np.ndarray:
    """Z-score chuẩn hóa tín hiệu (mean=0, std=1)"""
    arr = np.asarray(data)
    std_val = np.std(arr)
    if std_val < 1e-7:
        return arr - np.mean(arr)
    return (arr - np.mean(arr)) / std_val
