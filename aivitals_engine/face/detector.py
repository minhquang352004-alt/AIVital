from abc import ABC, abstractmethod
from typing import Optional, Tuple

import cv2
import numpy as np

from aivitals_engine.config.settings import FaceDetectorConfig


class BBoxSmoother:
    """
    Làm mịn tọa độ Bounding Box bằng Exponential Moving Average (EMA).

    Khắc phục hiện tượng giật rung tọa độ (jitter / flickering) của Face Detector,
    giúp vùng ROI trán và má đứng yên tương đối, tránh nhiễu quang học giả.

    Args:
        alpha:              Hệ số EMA — gần 1.0 phản ứng nhanh, gần 0.0 làm mịn mạnh hơn.
        max_missing_frames: Số frame mất mặt tối đa trước khi reset bộ nhớ đệm.
    """

    def __init__(self, alpha: float = 0.65, max_missing_frames: int = 10) -> None:
        self._alpha = float(alpha)
        self._max_missing = max_missing_frames
        self._smoothed: Optional[Tuple[float, ...]] = None
        self._missing_count: int = 0

    def reset(self) -> None:
        """Xóa bộ nhớ đệm — gọi khi bắt đầu session mới hoặc mất mặt quá lâu."""
        self._smoothed = None
        self._missing_count = 0

    def update(
        self, bbox: Optional[Tuple[int, int, int, int]]
    ) -> Optional[Tuple[int, int, int, int]]:
        """
        Cập nhật và trả về bbox đã được làm mịn.

        Args:
            bbox: (x, y, w, h) từ detector, hoặc None nếu không nhận diện được mặt.

        Returns:
            Bbox làm mịn (int, int, int, int), hoặc None nếu mất mặt quá lâu.
        """
        if bbox is None:
            return self._handle_missing_face()
        return self._apply_ema(bbox)

    # ──────────────────────────────────────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _handle_missing_face(self) -> Optional[Tuple[int, int, int, int]]:
        self._missing_count += 1
        if self._missing_count > self._max_missing:
            self._smoothed = None
        return self._to_int_tuple(self._smoothed)

    def _apply_ema(
        self, bbox: Tuple[int, int, int, int]
    ) -> Tuple[int, int, int, int]:
        self._missing_count = 0
        if self._smoothed is None:
            self._smoothed = tuple(float(v) for v in bbox)
        else:
            self._smoothed = tuple(
                self._alpha * float(new) + (1.0 - self._alpha) * float(prev)
                for new, prev in zip(bbox, self._smoothed)
            )
        return self._to_int_tuple(self._smoothed)  # type: ignore[return-value]

    @staticmethod
    def _to_int_tuple(
        values: Optional[Tuple[float, ...]]
    ) -> Optional[Tuple[int, int, int, int]]:
        if values is None:
            return None
        return tuple(int(round(v)) for v in values)  # type: ignore[return-value]


# ──────────────────────────────────────────────────────────────────────────────
# Abstract interface
# ──────────────────────────────────────────────────────────────────────────────

class BaseFaceDetector(ABC):
    """Interface thống nhất cho tất cả Face Detector."""

    @abstractmethod
    def detect(
        self, frame: np.ndarray
    ) -> Optional[Tuple[int, int, int, int]]:
        """
        Nhận diện khuôn mặt lớn nhất trong frame.

        Returns:
            (x, y, w, h) hoặc None nếu không tìm thấy.
        """

    def reset(self) -> None:
        """Reset trạng thái nội bộ nếu có (override khi cần)."""


# ──────────────────────────────────────────────────────────────────────────────
# Concrete implementation
# ──────────────────────────────────────────────────────────────────────────────

class SimpleFaceDetector(BaseFaceDetector):
    """
    Bộ phát hiện khuôn mặt dùng Haar Cascade (OpenCV) kèm BBoxSmoother EMA.

    Fallback về vùng trung tâm khung hình nếu cascade không nhận diện được mặt.
    """

    def __init__(
        self,
        enable_smoothing: bool = True,
        config: Optional[FaceDetectorConfig] = None,
    ) -> None:
        self._cfg = config if config is not None else FaceDetectorConfig()
        self._cascade = self._load_cascade()
        self._smoother = (
            BBoxSmoother(
                alpha=self._cfg.smoothing_alpha,
                max_missing_frames=self._cfg.max_missing_frames,
            )
            if enable_smoothing
            else None
        )

    def reset(self) -> None:
        if self._smoother is not None:
            self._smoother.reset()

    def detect(
        self, frame: np.ndarray
    ) -> Optional[Tuple[int, int, int, int]]:
        raw_bbox = self._detect_raw(frame)
        if self._smoother is not None:
            return self._smoother.update(raw_bbox)
        return raw_bbox

    # ──────────────────────────────────────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _load_cascade() -> Optional[cv2.CascadeClassifier]:
        """Tải Haar Cascade. Trả None nếu OpenCV không hỗ trợ."""
        has_cascade = (
            hasattr(cv2, "CascadeClassifier")
            and hasattr(cv2, "data")
            and hasattr(cv2.data, "haarcascades")
        )
        if not has_cascade:
            return None
        try:
            return cv2.CascadeClassifier(
                cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            )
        except Exception:
            return None

    def _detect_raw(
        self, frame: np.ndarray
    ) -> Optional[Tuple[int, int, int, int]]:
        """Chạy cascade detector. Trả về bbox lớn nhất hoặc fallback bbox."""
        if frame is None or frame.size == 0:
            return None

        if self._cascade is not None:
            bbox = self._run_cascade(frame)
            if bbox is not None:
                return bbox

        return self._fallback_bbox(frame)

    def _run_cascade(
        self, frame: np.ndarray
    ) -> Optional[Tuple[int, int, int, int]]:
        try:
            gray = (
                cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                if frame.ndim == 3
                else frame
            )
            faces = self._cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=4, minSize=(50, 50)
            )
            if len(faces) > 0:
                largest = max(faces, key=lambda b: b[2] * b[3])
                return tuple(int(v) for v in largest)  # type: ignore[return-value]
        except Exception:
            pass
        return None

    def _fallback_bbox(self, frame: np.ndarray) -> Tuple[int, int, int, int]:
        """Trả về vùng trung tâm khung hình khi cascade thất bại."""
        h, w = frame.shape[:2]
        cfg = self._cfg
        return (
            int(cfg.fallback_x_ratio * w),
            int(cfg.fallback_y_ratio * h),
            int(cfg.fallback_width_ratio * w),
            int(cfg.fallback_height_ratio * h),
        )
