from functools import lru_cache
import numpy as np
from scipy import sparse
from scipy.sparse.linalg import splu


@lru_cache(maxsize=32)
def _get_detrend_solver(T: int, lambda_value: float):
    """
    Phân rã trước ma trận thưa (I + λ² DᵀD) bằng Sparse LU (splu) và lưu cache theo (T, λ).
    Giúp tránh tạo lại ma trận và phân rã lại từ đầu ở mỗi frame (30 lần/giây).
    """
    ones = np.ones(T, dtype=np.float64)
    minus_twos = -2.0 * ones
    D = sparse.spdiags(
        np.array([ones, minus_twos, ones]),
        np.array([0, 1, 2]),
        T - 2,
        T,
        format="csc",
    )
    DtD = D.T @ D
    A = sparse.eye(T, format="csc", dtype=np.float64) + (float(lambda_value) ** 2) * DtD
    return splu(A)


def smoothness_priors_detrend(input_signal: np.ndarray, lambda_value: float = 100.0) -> np.ndarray:
    """
    Thuật toán Smoothness Priors Detrending (Tarvainen et al., 2002).
    Loại bỏ trôi đường đẳng điện (baseline wandering) do nhịp thở hoặc ánh sáng biến thiên chậm.

    Sử dụng pre-factorized sparse LU solver (splu + lru_cache) để đạt hiệu năng
    thế nghiệm O(N) siêu nhanh cho luồng realtime.

    Args:
        input_signal: Mảng 1D (T,) hoặc 2D (T, 1) tín hiệu đầu vào
        lambda_value: Hệ số làm trơn (mặc định 100.0)

    Returns:
        Mảng tín hiệu sau khi khử trôi
    """
    signal_arr = np.asarray(input_signal, dtype=np.float64).flatten()
    T = len(signal_arr)
    if T < 3:
        return signal_arr

    solver = _get_detrend_solver(T, float(lambda_value))
    trend = solver.solve(signal_arr)
    return signal_arr - trend
