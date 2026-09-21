import numpy as np
from .base import RPPGMethod
from aivitals_engine.signal.filter import butter_bandpass_filter, normalize_signal

class GREENMethod(RPPGMethod):
    """
    Thuật toán GREEN (Verkruysse et al., 2008).
    Trích xuất biến thiên hấp thụ mao mạch từ kênh xanh lá.
    """

    @property
    def name(self) -> str:
        return "GREEN"

    @property
    def version(self) -> str:
        return "1.0"

    def _compute_bvp(self, rgb_array: np.ndarray) -> np.ndarray:
        N = rgb_array.shape[0]
        if N < 9:
            return np.zeros(N)

        # Lấy kênh Green (index 1)
        green_signal = rgb_array[:, 1]

        # Chuẩn hóa tín hiệu (mean=0, std=1)
        norm_green = normalize_signal(green_signal)

        # Lọc dải thông nhịp tim sinh lý
        bvp = butter_bandpass_filter(norm_green, lowcut=self.lowcut, highcut=self.highcut, fs=self.fps, order=2)
        return bvp

