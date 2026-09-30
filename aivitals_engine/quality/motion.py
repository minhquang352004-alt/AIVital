import numpy as np
from typing import Dict, Optional
from aivitals_engine.signal.filter import butter_bandpass_filter
from aivitals_engine.config import settings

def calculate_motion_sqi(bboxes: np.ndarray, fs: float) -> Dict[str, float]:
    """
    Tính chỉ số chuyển động (Motion SQI) từ lịch sử bounding box.
    Chỉ số được định nghĩa là tỷ lệ phương sai của vận tốc chuyển động 
    nằm trong dải tần số nhịp tim (0.75 - 2.5 Hz) so với tổng phương sai vận tốc.
    
    Args:
        bboxes: np.ndarray shape (N, 4) chứa [x, y, w, h] của N frame.
        fs: Tần số lấy mẫu (Hz).
        
    Returns:
        Dict chứa:
            - motion_score: Tỷ lệ phương sai trong dải [0, 1] (Càng cao = chuyển động tuần hoàn nhiều).
            - raw_variance: Tổng phương sai vận tốc (pixels^2/s^2).
    """
    if len(bboxes) < max(10, int(fs * 2)): # Cần ít nhất 2s dữ liệu để phân tích tần số
        return {'motion_score': 0.0, 'raw_variance': 0.0}
        
    # Tính tâm bbox
    cx = bboxes[:, 0] + bboxes[:, 2] / 2
    cy = bboxes[:, 1] + bboxes[:, 3] / 2
    
    # Detrend to remove static position and slow drift
    from aivitals_engine.signal.detrend import smoothness_priors_detrend
    cx_detrended = cx - np.mean(cx)
    cy_detrended = cy - np.mean(cy)
    
    total_var = float(np.var(cx_detrended) + np.var(cy_detrended))
    
    if total_var < 1e-7:
        return {'motion_score': 0.0, 'raw_variance': 0.0}
        
    cfg = settings.SignalConfig()
    try:
        cx_band = butter_bandpass_filter(cx_detrended, cfg.low_cutoff_hz, cfg.high_cutoff_hz, fs, order=cfg.filter_order)
        cy_band = butter_bandpass_filter(cy_detrended, cfg.low_cutoff_hz, cfg.high_cutoff_hz, fs, order=cfg.filter_order)
        band_var = float(np.var(cx_band) + np.var(cy_band))
    except ValueError:
        return {'motion_score': 0.0, 'raw_variance': total_var}
        
    # Tỷ lệ
    ratio = np.clip(band_var / total_var, 0.0, 1.0)
    
    return {
        'motion_score': float(ratio), 
        'raw_variance': total_var
    }
