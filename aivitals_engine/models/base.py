"""
AIVitals Models Interface
Khung giao diện trừu tượng (Base Interface) cho các mô hình Deep Learning rPPG (V2).
Tham chiếu kiến trúc từ rPPG-Toolbox/neural_methods/model/
"""

from abc import ABC, abstractmethod
import numpy as np


class BaseNeuralRPPGModel(ABC):
    """
    Interface cơ sở cho các mô hình mạng nơ-ron học sâu (PhysNet, DeepPhys, TS-CAN, ...).
    Được chuẩn bị sẵn cho giai đoạn V2 khi tích hợp PyTorch / ONNX Runtime.
    """

    @abstractmethod
    def load_weights(self, weights_path: str) -> None:
        """Tải trọng số mô hình đã được huấn luyện."""
        pass

    @abstractmethod
    def predict(self, frames: np.ndarray) -> np.ndarray:
        """
        Dự đoán sóng BVP từ chuỗi video frame.

        Args:
            frames: Mảng tensor hình ảnh (T, H, W, 3) hoặc (B, C, T, H, W)

        Returns:
            Tín hiệu BVP 1D (T,)
        """
        pass
