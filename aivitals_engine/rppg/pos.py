import numpy as np
from .base import RPPGMethod
from aivitals_engine.signal.detrend import smoothness_priors_detrend
from aivitals_engine.signal.filter import butter_bandpass_filter

class POSMethod(RPPGMethod):
    """
    Thuật toán POS (Plane-Orthogonal-to-Skin, Wang et al., IEEE TBME 2017).
    Kháng nhiễu chuyển động và biến thiên hình học da tốt nhất.
    """

    @property
    def name(self) -> str:
        return "POS"

    @property
    def version(self) -> str:
        return "1.0"

    def _compute_bvp(self, rgb_array: np.ndarray) -> np.ndarray:
        N = rgb_array.shape[0]
        l = self.window_len
        if N < l:
            return np.zeros(N)

        H = np.zeros(N, dtype=np.float64)
        weights = np.zeros(N, dtype=np.float64)
        projection_matrix = np.array([[0.0, 1.0, -1.0], [-2.0, 1.0, 1.0]])

        # Vector hóa toàn bộ các cửa sổ con (thay vòng lặp Python từng cửa sổ)
        rgb_f = np.ascontiguousarray(rgb_array, dtype=np.float64)
        n_win = N - l + 1
        # windows: (n_win, 3, l)
        windows = np.lib.stride_tricks.sliding_window_view(rgb_f, l, axis=0)
        mean_rgb = windows.mean(axis=2)  # (n_win, 3)
        mean_rgb[mean_rgb == 0] = 1e-7

        # Chuẩn hóa thời gian
        Cn = windows / mean_rgb[:, :, None]  # (n_win, 3, l)

        # Phép chiếu trực giao
        S = np.matmul(projection_matrix, Cn)  # (n_win, 2, l)

        # Kết hợp thích ứng
        std_s0 = S[:, 0, :].std(axis=1)
        std_s1 = S[:, 1, :].std(axis=1)
        alpha = np.divide(
            std_s0, std_s1, out=np.zeros_like(std_s0), where=std_s1 > 1e-7
        )

        h = S[:, 0, :] + alpha[:, None] * S[:, 1, :]  # (n_win, l)
        h = h - h.mean(axis=1, keepdims=True)

        # Cộng chồng chập (Overlap-Add) theo từng độ lệch trong cửa sổ
        for k in range(l):
            H[k:k + n_win] += h[:, k]
        weights = np.zeros(N, dtype=np.float64)
        for k in range(l):
            weights[k:k + n_win] += 1.0

        # Chuẩn hóa trọng số chồng chập (Overlap-Add Normalization) để triệt tiêu méo hình quả trám
        H = np.divide(H, weights, out=np.zeros_like(H), where=weights > 0)

        # Khử trôi đường đẳng điện + Lọc dải thông trên sóng BVP 1D
        bvp = smoothness_priors_detrend(H, lambda_value=self.detrend_lambda)
        bvp = butter_bandpass_filter(
            bvp,
            lowcut=self.lowcut,
            highcut=self.highcut,
            fs=self.fps,
            order=self.filter_order
        )
        return bvp
