"""
AIVitals Models Interface
Khung giao diện trừu tượng (Base Interface) cho các mô hình Deep Learning rPPG (V2).
Kế thừa RPPGMethod để cắm chung vào cùng một Pipeline với POS/CHROM/GREEN.
Tham chiếu kiến trúc từ rPPG-Toolbox/neural_methods/model/
"""

from abc import abstractmethod
from typing import Optional
import numpy as np
from aivitals_engine.rppg.base import RPPGMethod


class BaseNeuralRPPGModel(RPPGMethod):
    """
    Interface cơ sở cho các mô hình mạng nơ-ron học sâu (PhysNet, DeepPhys, TS-CAN, ...).
    Kế thừa RPPGMethod để dùng chung toàn bộ interface:
    - name, version
    - reset(), update()
    - get_signal(), get_quality(), get_metadata()
    """

    def __init__(self, fps: float = 30.0, weights_path: Optional[str] = None):
        super().__init__(fps=fps)
        self.weights_path = weights_path
        if weights_path:
            self.load_weights(weights_path)

    @property
    @abstractmethod
    def name(self) -> str:
        """Tên mô hình Deep Learning (ví dụ: 'DeepPhys', 'PhysNet')"""
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        """Phiên bản model (ví dụ: '2.0')"""
        pass

    @abstractmethod
    def load_weights(self, weights_path: str) -> None:
        """Tải trọng số mô hình đã được huấn luyện (.pth, .onnx, .pt)."""
        pass

    @abstractmethod
    def predict(self, input_data: np.ndarray) -> np.ndarray:
        """
        Dự đoán sóng BVP từ dữ liệu đầu vào.

        Args:
            input_data: Mảng tensor hình ảnh (T, H, W, 3) hoặc mảng RGB (T, 3)

        Returns:
            Tín hiệu BVP 1D (T,)
        """
        pass

    def _compute_bvp(self, rgb_array: np.ndarray) -> np.ndarray:
        """Chuyển tiếp buffer sang hàm predict của mạng nơ-ron"""
        return self.predict(rgb_array)
