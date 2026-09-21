import numpy as np
from scipy import sparse
from scipy.sparse.linalg import spsolve

def smoothness_priors_detrend(input_signal: np.ndarray, lambda_value: float = 100.0) -> np.ndarray:
    """
    Thuật toán Smoothness Priors Detrending (Tarvainen et al., 2002).
    Loại bỏ trôi đường đẳng điện (baseline wandering) do nhịp thở hoặc ánh sáng biến thiên chậm.

    Sử dụng sparse solver (spsolve) thay vì np.linalg.inv để đảm bảo
    hiệu năng O(N) thay vì O(N³) — phù hợp cho realtime với buffer lớn.

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

    # Ma trận vi sai bậc 2 dạng sparse (T-2, T) — dùng csc để nhân nhanh
    ones       = np.ones(T)
    minus_twos = -2.0 * np.ones(T)
    D = sparse.spdiags(
        np.array([ones, minus_twos, ones]),
        np.array([0, 1, 2]),
        T - 2, T,
        format="csc",
    )

    # Giải hệ: (I + λ² DᵀD) x = signal  →  x là thành phần xu hướng (trend)
    # Tín hiệu khử trôi = signal - trend
    # D.T @ D vẫn là sparse vì D là sparse → A là sparse banded
    DtD   = D.T @ D                                     # sparse (T, T)
    A     = sparse.eye(T, format="csc") + (lambda_value ** 2) * DtD
    trend = spsolve(A, signal_arr)                      # O(N) sparse solve
    return signal_arr - trend
