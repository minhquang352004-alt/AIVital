from abc import ABC, abstractmethod
from typing import Dict, Any, List
import numpy as np
from aivitals_engine.quality.sqi import calculate_bvp_quality

class RPPGMethod(ABC):
    """
    Interface thống nhất cho các thuật toán rPPG (GREEN, CHROM, POS).
    Đảm bảo trích xuất sóng BVP, tính toán chất lượng và metadata mà không phụ thuộc module bên ngoài.
    """

    def __init__(self, fps: float = 30.0, window_sec: float = 1.6):
        self.fps = float(fps)
        self.window_sec = float(window_sec)
        self.window_len = max(9, int(np.ceil(window_sec * fps)))
        self._rgb_buffer: List[np.ndarray] = []
        self._latest_bvp: np.ndarray = np.array([])
        self._latest_quality: float = 0.0

    @property
    @abstractmethod
    def name(self) -> str:
        """Tên phương thức ('GREEN', 'CHROM', 'POS')"""
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        """Phiên bản thuật toán ('1.0')"""
        pass

    def reset(self) -> None:
        """Reset sạch bộ nhớ và buffer"""
        self._rgb_buffer.clear()
        self._latest_bvp = np.array([])
        self._latest_quality = 0.0

    def update(self, rgb: np.ndarray) -> None:
        """
        Đưa mẫu RGB vào buffer.
        Hỗ trợ 1 mẫu 1D (3,) hoặc mảng nhiều mẫu 2D (K, 3).
        """
        arr = np.asarray(rgb, dtype=np.float64)
        if arr.ndim == 1 and arr.shape[0] == 3:
            self._rgb_buffer.append(arr)
        elif arr.ndim == 2 and arr.shape[1] == 3:
            for row in arr:
                self._rgb_buffer.append(row)
        else:
            raise ValueError(f"Định dạng RGB không hợp lệ: shape {arr.shape}. Cần (3,) hoặc (K, 3).")

    @abstractmethod
    def _compute_bvp(self, rgb_array: np.ndarray) -> np.ndarray:
        """Thuật toán biến đổi RGB buffer -> BVP signal"""
        pass

    def get_signal(self) -> np.ndarray:
        """
        Trích xuất và trả về tín hiệu BVP 1D (N,).
        """
        if len(self._rgb_buffer) < self.window_len:
            self._latest_bvp = np.zeros(len(self._rgb_buffer))
            return self._latest_bvp

        arr = np.asarray(self._rgb_buffer)
        self._latest_bvp = self._compute_bvp(arr)
        return self._latest_bvp

    def get_quality(self) -> float:
        """
        Chỉ số chất lượng tín hiệu BVP (0.0 đến 1.0).
        """
        if len(self._latest_bvp) == 0:
            self.get_signal()
        self._latest_quality = calculate_bvp_quality(self._latest_bvp, fs=self.fps)
        return self._latest_quality

    def get_metadata(self) -> Dict[str, Any]:
        """
        Metadata chuẩn của lần chạy rPPG.
        """
        if len(self._latest_bvp) == 0:
            self.get_signal()
        quality = self.get_quality()

        return {
            "method": self.name,
            "version": self.version,
            "sampling_rate": int(round(self.fps)),
            "signal_length": len(self._latest_bvp),
            "quality": quality
        }

    def process(self, rgb_array: np.ndarray) -> np.ndarray:
        """Hàm tiện ích chạy trực tiếp trên mảng RGB đã có sẵn"""
        self.reset()
        self.update(rgb_array)
        return self.get_signal()
