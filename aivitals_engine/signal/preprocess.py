import numpy as np
from .detrend import smoothness_priors_detrend
from .filter import normalize_signal

def preprocess_rgb(
    rgb_array: np.ndarray,
    detrend: bool = False,
    normalize: bool = False,
    detrend_lambda: float = 100.0
) -> np.ndarray:
    """
    Tiền xử lý cơ bản cho tín hiệu RGB trước khi đưa vào rPPG.
    
    Args:
        rgb_array: Mảng 2D shape (N, 3) đại diện cho [R, G, B]
        detrend: Khử trôi xu hướng tần số thấp trên từng kênh (mặc định False, vì POS/CHROM có logic riêng)
        normalize: Chuẩn hóa Z-score trên từng kênh (mean=0, std=1)
        detrend_lambda: Hệ số làm trơn nếu bật detrend
        
    Returns:
        Mảng RGB đã tiền xử lý shape (N, 3)
    """
    arr = np.asarray(rgb_array, dtype=np.float64).copy()
    if len(arr) < 3:
        return arr

    if detrend:
        for c in range(3):
            arr[:, c] = smoothness_priors_detrend(arr[:, c], lambda_value=detrend_lambda)

    if normalize:
        for c in range(3):
            arr[:, c] = normalize_signal(arr[:, c])

    return arr
