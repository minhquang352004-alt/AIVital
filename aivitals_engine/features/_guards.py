"""
aivitals_engine/features/_guards.py
=====================================
Epsilon-guard helpers — pure functions phòng thủ toán học.

Dùng nội bộ trong package `features/`. Không import module khác của dự án.

Thiết kế (SOLID):
    S – Mỗi hàm làm đúng một việc, không có side effects.
    D – `epsilon` luôn được truyền vào, không hard-code.
"""
from __future__ import annotations

from typing import Callable

import numpy as np


# ── Core safe arithmetic ───────────────────────────────────────────────────────

def safe_divide(numerator: float, denominator: float, *, epsilon: float) -> float:
    """
    Chia an toàn: trả NaN nếu |mẫu số| < epsilon.

    Args:
        numerator:   Tử số.
        denominator: Mẫu số.
        epsilon:     Ngưỡng coi mẫu số là bằng 0.

    Returns:
        float — kết quả chia hoặc NaN nếu không an toàn.
    """
    if abs(denominator) < epsilon:
        return float("nan")
    return float(numerator / denominator)


def safe_ratio_arrays(
    a: np.ndarray,
    b: np.ndarray,
    *,
    epsilon: float,
) -> float:
    """
    Tỷ lệ trung bình element-wise a/b trên 2 mảng — an toàn.

    Các vị trí có |b| < epsilon được thay bằng epsilon để tránh chia cho 0.

    Returns:
        float — nanmean(a / b_safe). NaN nếu cả hai mảng rỗng.
    """
    a_arr = np.asarray(a, dtype=np.float64)
    b_arr = np.asarray(b, dtype=np.float64)
    if a_arr.size == 0 or b_arr.size == 0:
        return float("nan")
    b_safe = np.where(np.abs(b_arr) < epsilon, epsilon, b_arr)
    return float(np.nanmean(a_arr / b_safe))


def safe_stat(
    arr: np.ndarray,
    func: Callable[[np.ndarray], float],
    *,
    min_len: int = 1,
) -> float:
    """
    Tính thống kê trên mảng sau khi loại NaN; trả NaN nếu quá ngắn.

    Args:
        arr:     Mảng đầu vào (có thể chứa NaN).
        func:    Hàm thống kê (np.mean, np.std, ...).
        min_len: Số phần tử tối thiểu sau khi loại NaN.

    Returns:
        float — kết quả func hoặc NaN.
    """
    valid = arr[~np.isnan(arr)] if arr.size > 0 else arr
    if valid.size < min_len:
        return float("nan")
    return float(func(valid))


# ── Signal-level helpers ───────────────────────────────────────────────────────

def nan_mean(values: list[float], *, epsilon: float = 0.0) -> float:
    """
    Trung bình của list float có thể chứa NaN.

    Returns:
        NaN nếu list rỗng hoặc toàn NaN.
    """
    finite = [v for v in values if not (v != v)]  # loại NaN
    if not finite:
        return float("nan")
    return float(np.mean(finite))


def is_degenerate(sig: np.ndarray, *, min_samples: int, epsilon: float) -> bool:
    """
    Kiểm tra tín hiệu có bị suy biến không (rỗng, quá ngắn, phẳng, toàn NaN).

    Returns:
        True nếu tín hiệu không xử lý được.
    """
    if sig.size < min_samples:
        return True
    if np.all(~np.isfinite(sig)):
        return True
    sig_range = np.nanmax(sig) - np.nanmin(sig)
    return bool(sig_range < epsilon)
