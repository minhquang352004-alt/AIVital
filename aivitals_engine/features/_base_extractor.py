"""
aivitals_engine/features/_base_extractor.py
============================================
Interface cơ sở cho các partial feature extractor.

Thiết kế (SOLID):
    S – Mỗi subclass chịu trách nhiệm duy nhất một nhóm feature.
    O – Thêm nhóm feature mới = viết subclass mới kế thừa PartialFeatureExtractor,
        không sửa code orchestrator hay các extractor khác.
    I – Interface tối giản: chỉ một method `extract()`.
    D – Các extractor nhận BVPFeaturesConfig qua constructor (Dependency Injection).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import numpy as np

from aivitals_engine.features.config import BVPFeaturesConfig
from aivitals_engine.features.segmentation import SingleBeat


class PartialFeatureExtractor(ABC):
    """
    Abstract Base Class cho extractor từng nhóm đặc trưng.

    Mỗi subclass trích xuất một nhóm đặc trưng từ mảng BVP 1D
    và danh sách chu kỳ nhịp (SingleBeat) đã phân đoạn.
    """

    def __init__(self, config: BVPFeaturesConfig | None = None) -> None:
        self._cfg: BVPFeaturesConfig = config or BVPFeaturesConfig()

    @abstractmethod
    def extract(
        self,
        bvp: np.ndarray,
        fs: float,
        beats: list[SingleBeat],
    ) -> dict[str, Any]:
        """
        Trích xuất một nhóm đặc trưng.

        Args:
            bvp:   Mảng BVP 1D (đã lọc sạch, float64).
            fs:    Tần số lấy mẫu (Hz).
            beats: Danh sách SingleBeat đã phân đoạn (có thể rỗng).

        Returns:
            dict với key khớp chính xác tên field trong BVPFeatures.
            Field nào không tính được thì đặt giá trị float("nan").
        """
