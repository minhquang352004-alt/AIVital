import numpy as np
from scipy import signal
from .base import RPPGMethod
from aivitals_engine.signal.detrend import smoothness_priors_detrend
from aivitals_engine.signal.filter import butter_bandpass_filter

class CHROMMethod(RPPGMethod):
    """
    Thuật toán CHROM (de Haan & Jeanne, IEEE TBME 2013).
    Dùng không gian sắc độ để triệt tiêu biến thiên ánh sáng môi trường.
    """

    @property
    def name(self) -> str:
        return "CHROM"

    @property
    def version(self) -> str:
        return "1.0"

    def _compute_bvp(self, rgb_array: np.ndarray) -> np.ndarray:
        N = rgb_array.shape[0]
        win_len = self.window_len
        if win_len % 2 != 0:
            win_len += 1

        if N < win_len:
            return np.zeros(N)

        step = max(1, win_len // 2)
        starts = list(range(0, N - win_len + 1, step))
        if starts[-1] != N - win_len:
            starts.append(N - win_len)

        S = np.zeros(N, dtype=np.float64)
        weights = np.zeros(N, dtype=np.float64)
        hann_win = np.maximum(signal.windows.hann(win_len), 0.05)

        for start in starts:
            end = start + win_len
            rgb_window = rgb_array[start:end, :]
            rgb_base = np.mean(rgb_window, axis=0)
            rgb_base[rgb_base == 0] = 1e-7

            # Chuẩn hóa sắc độ
            rgb_norm = rgb_window / rgb_base
            Xs = 3.0 * rgb_norm[:, 0] - 2.0 * rgb_norm[:, 1]
            Ys = 1.5 * rgb_norm[:, 0] + rgb_norm[:, 1] - 1.5 * rgb_norm[:, 2]

            Xf = Xs - np.mean(Xs)
            Yf = Ys - np.mean(Ys)

            std_y = np.std(Yf)
            alpha = (np.std(Xf) / std_y) if std_y > 1e-7 else 0.0

            # Cửa sổ Hanning và tích lũy chồng chập
            s_win = (Xf - alpha * Yf) * hann_win
            S[start:end] += s_win
            weights[start:end] += hann_win

        # Chuẩn hóa trọng số chồng chập (Overlap-Add Normalization)
        S = np.divide(S, weights, out=np.zeros_like(S), where=weights > 0)

        # Khử trôi + Lọc dải thông trên toàn bộ chuỗi dài N (tránh suy hao trên cửa sổ ngắn)
        bvp = smoothness_priors_detrend(S, lambda_value=self.detrend_lambda)
        bvp = butter_bandpass_filter(
            bvp,
            lowcut=self.lowcut,
            highcut=self.highcut,
            fs=self.fps,
            order=self.filter_order
        )
        return bvp
