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

        H = np.zeros(N)
        projection_matrix = np.array([[0.0, 1.0, -1.0], [-2.0, 1.0, 1.0]])

        for n in range(N):
            m = n - l
            if m >= 0:
                sub_rgb = rgb_array[m:n, :]
                mean_rgb = np.mean(sub_rgb, axis=0)
                mean_rgb[mean_rgb == 0] = 1e-7

                # Chuẩn hóa thời gian
                Cn = (sub_rgb / mean_rgb).T  # (3, l)

                # Phép chiếu trực giao
                S = np.matmul(projection_matrix, Cn)  # (2, l)

                # Kết hợp thích ứng
                std_s0 = np.std(S[0, :])
                std_s1 = np.std(S[1, :])
                alpha = (std_s0 / std_s1) if std_s1 > 1e-7 else 0.0

                h = S[0, :] + alpha * S[1, :]
                h = h - np.mean(h)
                H[m:n] += h

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

