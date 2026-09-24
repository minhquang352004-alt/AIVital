import numpy as np
from scipy import signal
from .base import RPPGMethod
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

        step = win_len // 2
        num_windows = (N - step) // step
        if num_windows < 1:
            return np.zeros(N)

        S = np.zeros(N)
        hann_win = signal.windows.hann(win_len)

        for i in range(num_windows):
            start = i * step
            end = start + win_len
            if end > N:
                break

            rgb_window = rgb_array[start:end, :]
            rgb_base = np.mean(rgb_window, axis=0)
            rgb_base[rgb_base == 0] = 1e-7

            # Chuẩn hóa sắc độ
            rgb_norm = rgb_window / rgb_base
            Xs = 3.0 * rgb_norm[:, 0] - 2.0 * rgb_norm[:, 1]
            Ys = 1.5 * rgb_norm[:, 0] + rgb_norm[:, 1] - 1.5 * rgb_norm[:, 2]

            # Lọc dải thông sắc độ
            Xf = butter_bandpass_filter(Xs, lowcut=self.lowcut, highcut=self.highcut, fs=self.fps, order=self.filter_order)
            Yf = butter_bandpass_filter(Ys, lowcut=self.lowcut, highcut=self.highcut, fs=self.fps, order=self.filter_order)


            std_y = np.std(Yf)
            alpha = (np.std(Xf) / std_y) if std_y > 1e-7 else 0.0

            # Cửa sổ Hanning và tích lũy chồng chập
            s_win = (Xf - alpha * Yf) * hann_win
            S[start:end] += s_win

        return S
