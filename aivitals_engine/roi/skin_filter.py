"""
aivitals_engine/roi/skin_filter.py
==================================
Bộ lọc màu da người (Skin Pixel Filtering) trong không gian màu YCrCb.

Cơ sở khoa học (Biomedical Computer Vision):
    Màu da của mọi chủng tộc loài người (Fitzpatrick Scale I - VI) khi chuyển
    sang không gian màu YCrCb đều có thành phần sắc độ (Chrominance: Cr, Cb)
    nằm trong một dải phân bố elip/chữ nhật hẹp và nhất quán:
        133 <= Cr <= 173
        77  <= Cb <= 127
    Thành phần độ chói (Luminance: Y) dùng để loại bỏ:
        Y < 20  : Bóng đổ quá tối hoặc sợi tóc đen
        Y > 240 : Vùng chói lóa ánh sáng phản chiếu (specular reflection)

Nguyên tắc SOLID:
    - SRP: Hàm thuần túy (pure function), chỉ lọc mảng pixel da, không phụ thuộc camera hay pipeline.
    - An toàn: Fallback tự động khi tỷ lệ pixel da quá thấp (< min_skin_ratio) để tránh chia cho 0.
"""
from typing import Tuple

import cv2
import numpy as np


def filter_skin_pixels(
    patch_bgr: np.ndarray,
    cr_range: Tuple[int, int] = (133, 173),
    cb_range: Tuple[int, int] = (77, 127),
    y_range: Tuple[int, int] = (20, 240),
    min_skin_ratio: float = 0.10,
) -> np.ndarray:
    """
    Lọc bỏ các pixel tóc, râu, kính, bóng tối từ mảng ảnh BGR.

    Args:
        patch_bgr:      Mảng BGR cắt từ frame, shape (H, W, 3) hoặc (N, 3).
        cr_range:       (min_cr, max_cr) ngưỡng sắc đỏ da người.
        cb_range:       (min_cb, max_cb) ngưỡng sắc xanh da người.
        y_range:        (min_y, max_y) ngưỡng độ chói chấp nhận được.
        min_skin_ratio: Tỷ lệ pixel da tối thiểu (0.0 -> 1.0) để áp dụng mặt nạ.
                        Nếu tỷ lệ da < min_skin_ratio, fallback lấy toàn bộ patch.

    Returns:
        Mảng 2D (N_skin, 3) kiểu float64 chứa các pixel BGR hợp lệ.
        Nếu rỗng trả về mảng shape (0, 3).
    """
    if patch_bgr is None or patch_bgr.size == 0:
        return np.zeros((0, 3), dtype=np.float64)

    # Đảm bảo định dạng 3 chiều (H, W, 3) để cv2.cvtColor xử lý
    if patch_bgr.ndim == 2:
        reshaped = patch_bgr.reshape(1, -1, 3).astype(np.uint8)
    elif patch_bgr.ndim == 3:
        reshaped = patch_bgr.astype(np.uint8)
    else:
        return np.zeros((0, 3), dtype=np.float64)

    # Chuyển đổi BGR sang YCrCb
    ycrcb = cv2.cvtColor(reshaped, cv2.COLOR_BGR2YCrCb)
    y = ycrcb[:, :, 0]
    cr = ycrcb[:, :, 1]
    cb = ycrcb[:, :, 2]

    # Mặt nạ pixel da
    skin_mask = (
        (cr >= cr_range[0]) & (cr <= cr_range[1]) &
        (cb >= cb_range[0]) & (cb <= cb_range[1]) &
        (y >= y_range[0]) & (y <= y_range[1])
    )

    total_pixels = y.size
    skin_count = int(np.count_nonzero(skin_mask))

    # Nếu số lượng pixel da đạt ngưỡng tin cậy (>= min_skin_ratio)
    if total_pixels > 0 and (skin_count / total_pixels) >= min_skin_ratio:
        flat_bgr = reshaped.reshape(-1, 3)
        flat_mask = skin_mask.reshape(-1)
        return flat_bgr[flat_mask].astype(np.float64)

    # Fallback an toàn: Khi da bị che khuất quá 90% hoặc ảnh đơn sắc
    return reshaped.reshape(-1, 3).astype(np.float64)
