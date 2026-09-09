import numpy as np
from scipy import signal

def butter_bandpass_filter(
    data: np.ndarray,
    lowcut: float,
    highcut: float,
    fs: float,
    order: int = 1
) -> np.ndarray:
    """
    Bộ lọc dải thông Butterworth 2 chiều (Zero-phase filtfilt).
    
    Args:
        data: Tín hiệu 1D cần lọc
        lowcut: Tần số cắt thấp (Hz)
        highcut: Tần số cắt cao (Hz)
        fs: Tần số lấy mẫu (FPS)
        order: Bậc bộ lọc (thường là 1 đến 3)
    """
    data_arr = np.asarray(data).flatten()
    if len(data_arr) < 9:
        return data_arr

    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    
    # Kiểm tra giới hạn Nyquist
    low = max(0.001, min(low, 0.99))
    high = max(low + 0.001, min(high, 0.999))
    
    b, a = signal.butter(order, [low, high], btype="bandpass")
    filtered = signal.filtfilt(b, a, data_arr.astype(np.float64))
    return filtered

def normalize_signal(data: np.ndarray) -> np.ndarray:
    """Z-score chuẩn hóa tín hiệu (mean=0, std=1)"""
    arr = np.asarray(data)
    std_val = np.std(arr)
    if std_val < 1e-7:
        return arr - np.mean(arr)
    return (arr - np.mean(arr)) / std_val
