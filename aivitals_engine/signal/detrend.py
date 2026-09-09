import numpy as np
from scipy import sparse

def smoothness_priors_detrend(input_signal: np.ndarray, lambda_value: float = 100.0) -> np.ndarray:
    """
    Thuật toán Smoothness Priors Detrending (Tarvainen et al., 2002).
    Loại bỏ trôi đường đẳng điện (baseline wandering) do nhịp thở hoặc ánh sáng biến thiên chậm.
    
    Args:
        input_signal: Mảng 1D (T,) hoặc 2D (T, 1) tín hiệu đầu vào
        lambda_value: Hệ số làm trơn (mặc định 100.0)
        
    Returns:
        Mảng tín hiệu sau khi khử trôi
    """
    signal_arr = np.asarray(input_signal).flatten()
    T = len(signal_arr)
    if T < 3:
        return signal_arr

    # Ma trận đơn vị
    H = np.identity(T)
    
    # Ma trận vi sai bậc 2
    ones = np.ones(T)
    minus_twos = -2.0 * np.ones(T)
    diags_data = np.array([ones, minus_twos, ones])
    diags_index = np.array([0, 1, 2])
    D = sparse.spdiags(diags_data, diags_index, (T - 2), T).toarray()
    
    # Lọc thành phần xu hướng: y_stat = (I - (I + lambda^2 * D^T * D)^-1) * y
    reg = (lambda_value ** 2) * np.dot(D.T, D)
    inv_mat = np.linalg.inv(H + reg)
    filtered = np.dot((H - inv_mat), signal_arr)
    
    return filtered
