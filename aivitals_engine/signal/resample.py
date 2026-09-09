import numpy as np

def resample_to_fixed_fps(
    timestamps: np.ndarray,
    data: np.ndarray,
    target_fps: float = 30.0
) -> np.ndarray:
    """
    Nội suy tuyến tính dữ liệu tín hiệu để khắc phục hiện tượng trôi khung hình (FPS jitter) của webcam.
    
    Args:
        timestamps: Mảng mốc thời gian thực của từng frame (giây hoặc mili-giây)
        data: Mảng dữ liệu 1D (T,) hoặc 2D (T, C)
        target_fps: Tần số lấy mẫu đều mục tiêu (mặc định 30.0 Hz)
        
    Returns:
        Mảng dữ liệu đã được resample đều đặn theo thời gian
    """
    ts = np.asarray(timestamps)
    if len(ts) < 2:
        return np.asarray(data)

    duration = ts[-1] - ts[0]
    if duration <= 0:
        return np.asarray(data)

    target_num_samples = int(np.round(duration * target_fps))
    if target_num_samples < 2:
        return np.asarray(data)

    new_ts = np.linspace(ts[0], ts[-1], target_num_samples)
    data_arr = np.asarray(data)
    
    if data_arr.ndim == 1:
        return np.interp(new_ts, ts, data_arr)
    else:
        # Xử lý nhiều kênh (ví dụ R, G, B)
        num_channels = data_arr.shape[1]
        resampled = np.zeros((target_num_samples, num_channels), dtype=data_arr.dtype)
        for c in range(num_channels):
            resampled[:, c] = np.interp(new_ts, ts, data_arr[:, c])
        return resampled
