from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import numpy as np

from aivitals_engine.config.settings import SignalConfig
from aivitals_engine.quality.sqi import calculate_bvp_quality


class RPPGMethod(ABC):
    """
    Interface thống nhất cho các thuật toán rPPG (GREEN, CHROM, POS).

    Hỗ trợ 2 use case độc lập:
    ┌─────────────────────────────────────────────────────────────────┐
    │  Batch API (pipeline)   : process(rgb_array) → bvp             │
    │  Streaming API (Khoa)   : update() → get_signal() → get_quality│
    └─────────────────────────────────────────────────────────────────┘

    Subclass chỉ cần implement:
        - name      (property)
        - version   (property)
        - _compute_bvp(rgb_array) → np.ndarray
    """

    def __init__(
        self,
        fps:            float            = 30.0,
        window_sec:     Optional[float]  = None,
        lowcut:         Optional[float]  = None,
        highcut:        Optional[float]  = None,
        detrend_lambda: Optional[float]  = None,
        config:         Optional[SignalConfig] = None,
    ) -> None:
        cfg = config if config is not None else SignalConfig()

        self.fps            = float(fps)
        self.window_sec     = float(window_sec     if window_sec     is not None else cfg.sub_window_sec)
        self.window_len     = max(9, int(np.ceil(self.window_sec * self.fps)))
        self.lowcut         = float(lowcut         if lowcut         is not None else cfg.low_cutoff_hz)
        self.highcut        = float(highcut        if highcut        is not None else cfg.high_cutoff_hz)
        self.detrend_lambda = float(detrend_lambda if detrend_lambda is not None else cfg.detrend_lambda)
        self.filter_order   = int(cfg.filter_order)

        # ── Streaming API internal state ──────────────────────────────────────
        self._stream_buffer: List[np.ndarray] = []
        self._latest_bvp:    np.ndarray       = np.array([])
        self._latest_quality: float           = 0.0

    # ──────────────────────────────────────────────────────────────────────────
    # Abstract contract — subclass phải implement
    # ──────────────────────────────────────────────────────────────────────────

    @property
    @abstractmethod
    def name(self) -> str:
        """Tên phương thức: 'GREEN', 'CHROM', hoặc 'POS'."""

    @property
    @abstractmethod
    def version(self) -> str:
        """Phiên bản thuật toán, ví dụ: '1.0'."""

    @abstractmethod
    def _compute_bvp(self, rgb_array: np.ndarray) -> np.ndarray:
        """
        Lõi thuật toán: chuyển đổi mảng RGB → sóng BVP 1D.

        Args:
            rgb_array: np.ndarray shape (N, 3), DC đã được giữ nguyên.

        Returns:
            np.ndarray shape (N,) — sóng mạch đã qua detrend + bandpass.
        """

    # ──────────────────────────────────────────────────────────────────────────
    # Batch API — dùng trong signal_pipeline_realtime
    # ──────────────────────────────────────────────────────────────────────────

    def process(self, rgb_array: np.ndarray) -> np.ndarray:
        """
        Batch processing: nhận mảng RGB đã tích lũy sẵn, trả về BVP trực tiếp.

        Hàm này là pure function — không thay đổi trạng thái streaming buffer.

        Args:
            rgb_array: np.ndarray shape (N, 3).

        Returns:
            np.ndarray shape (N,) — sóng BVP đã lọc sạch.
        """
        arr = np.asarray(rgb_array, dtype=np.float64)
        if arr.ndim == 1 and arr.shape[0] == 3:
            arr = arr.reshape(1, 3)
        if arr.ndim != 2 or arr.shape[1] != 3:
            raise ValueError(
                f"rgb_array không hợp lệ: shape {arr.shape}. Cần (N, 3)."
            )
        return self._compute_bvp(arr)

    # ──────────────────────────────────────────────────────────────────────────
    # Streaming API — dùng cho tích hợp frame-by-frame (Khoa / vitals team)
    # ──────────────────────────────────────────────────────────────────────────

    def update(self, rgb: np.ndarray) -> None:
        """
        Đẩy mẫu RGB vào streaming buffer.

        Args:
            rgb: Một mẫu (3,) hoặc nhiều mẫu (K, 3).
        """
        arr = np.asarray(rgb, dtype=np.float64)
        if arr.ndim == 1 and arr.shape[0] == 3:
            self._stream_buffer.append(arr)
        elif arr.ndim == 2 and arr.shape[1] == 3:
            self._stream_buffer.extend(arr)
        else:
            raise ValueError(
                f"Định dạng RGB không hợp lệ: shape {arr.shape}. Cần (3,) hoặc (K, 3)."
            )

    def get_signal(self) -> np.ndarray:
        """
        Trích xuất tín hiệu BVP từ streaming buffer hiện tại.

        Returns:
            np.ndarray shape (N,). Zeros nếu buffer chưa đủ window_len mẫu.
        """
        n = len(self._stream_buffer)
        if n < self.window_len:
            self._latest_bvp = np.zeros(n)
            return self._latest_bvp

        arr = np.asarray(self._stream_buffer)
        self._latest_bvp = self._compute_bvp(arr)
        return self._latest_bvp

    def get_quality(self) -> float:
        """
        SQI của tín hiệu BVP hiện tại [0.0 → 1.0].
        Tự động gọi get_signal() nếu chưa có kết quả.
        """
        if len(self._latest_bvp) == 0:
            self.get_signal()
        self._latest_quality = calculate_bvp_quality(self._latest_bvp, fs=self.fps)
        return self._latest_quality

    def get_metadata(self) -> Dict[str, Any]:
        """Metadata chuẩn của lần chạy rPPG gần nhất."""
        if len(self._latest_bvp) == 0:
            self.get_signal()
        return {
            "method":        self.name,
            "version":       self.version,
            "sampling_rate": int(round(self.fps)),
            "signal_length": len(self._latest_bvp),
            "quality":       self.get_quality(),
        }

    def reset(self) -> None:
        """Reset streaming buffer và kết quả cached."""
        self._stream_buffer.clear()
        self._latest_bvp     = np.array([])
        self._latest_quality = 0.0
