import os
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

    def get_landmarks(self) -> Optional[np.ndarray]:
        """
        Trả về mảng 2D (N, 2) int32 tọa độ pixel (x, y) của các điểm mốc giải phẫu.
        Mặc định trả về None đối với các detector chỉ có Bounding Box (như Haar Cascade).
        """
        return None


# ──────────────────────────────────────────────────────────────────────────────
# Concrete implementation
# ──────────────────────────────────────────────────────────────────────────────

class HaarCascadeFaceDetector(BaseFaceDetector):
    """
    Bộ phát hiện khuôn mặt chuẩn hóa dùng OpenCV Haar Cascade (haarcascade_frontalface_default.xml)
    kết hợp với bộ lọc làm mịn tọa độ BBoxSmoother (EMA).

    Ưu tiên tải tệp mô hình haarcascade_frontalface_default.xml được đóng gói sẵn trong gói
    `aivitals_engine/face/models/` để đảm bảo độ tin cậy tuyệt đối trên mọi môi trường (kể cả
    khi OpenCV trên Windows/Linux không đính kèm tệp dữ liệu cascade).

    Args:
        enable_smoothing: Bật/tắt bộ lọc EMA làm mịn bounding box chống rung giật.
        config:           Cấu hình FaceDetectorConfig (smoothing_alpha, fallback ratios,...).
        allow_fallback:   Nếu True, trả về bounding box vùng trung tâm khi không nhận diện được mặt.
                          Nếu False, trả về None khi mất dấu khuôn mặt (chuẩn hóa kịch bản y tế).
        model_path:       Đường dẫn tùy chọn tới file XML cascade; nếu None sẽ tự tìm file chuẩn.
    """

    def __init__(
        self,
        enable_smoothing: bool = True,
        config: Optional[FaceDetectorConfig] = None,
        allow_fallback: bool = True,
        model_path: Optional[str] = None,
    ) -> None:
        self._cfg = config if config is not None else FaceDetectorConfig()
        self._allow_fallback = allow_fallback
        self._cascade = self._load_cascade(model_path)
        self._smoother = (
            BBoxSmoother(
                alpha=self._cfg.smoothing_alpha,
                max_missing_frames=self._cfg.max_missing_frames,
            )
            if enable_smoothing
            else None
        )

    def reset(self) -> None:
        """Reset trạng thái bộ làm mịn tọa độ."""
        if self._smoother is not None:
            self._smoother.reset()

    def detect(
        self, frame: np.ndarray
    ) -> Optional[Tuple[int, int, int, int]]:
        """
        Nhận diện khuôn mặt lớn nhất trong frame bằng Haar Cascade.

        Returns:
            (x, y, w, h) hoặc None nếu không phát hiện được mặt (và allow_fallback=False).
        """
        raw_bbox = self._detect_raw(frame)
        if self._smoother is not None:
            return self._smoother.update(raw_bbox)
        return raw_bbox

    # ──────────────────────────────────────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _load_cascade(custom_path: Optional[str] = None) -> Optional[cv2.CascadeClassifier]:
        """Tải Haar Cascade chuẩn. Ưu tiên file mô hình nội bộ, sau đó đến cv2.data."""
        if not hasattr(cv2, "CascadeClassifier"):
            return None

        # 0. Nếu người dùng chỉ định đường dẫn cụ thể
        if custom_path and os.path.exists(custom_path):
            try:
                clf = cv2.CascadeClassifier(custom_path)
                if not clf.empty():
                    return clf
            except Exception:
                pass

        # 1. Thử file nội bộ trong thư mục aivitals_engine/face/models/haarcascade_frontalface_default.xml
        pkg_dir = os.path.dirname(os.path.abspath(__file__))
        local_xml = os.path.join(pkg_dir, "models", "haarcascade_frontalface_default.xml")
        if os.path.exists(local_xml):
            try:
                clf = cv2.CascadeClassifier(local_xml)
                if not clf.empty():
                    return clf
            except Exception:
                pass

        # 2. Thử đường dẫn hệ thống từ cv2.data.haarcascades
        if hasattr(cv2, "data") and hasattr(cv2.data, "haarcascades"):
            sys_xml = os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml")
            if os.path.exists(sys_xml):
                try:
                    clf = cv2.CascadeClassifier(sys_xml)
                    if not clf.empty():
                        return clf
                except Exception:
                    pass

        return None

    def _detect_raw(
        self, frame: np.ndarray
    ) -> Optional[Tuple[int, int, int, int]]:
        """Chạy cascade detector. Trả về bbox lớn nhất hoặc fallback bbox (nếu cho phép)."""
        if frame is None or frame.size == 0:
            return None

        if self._cascade is not None:
            bbox = self._run_cascade(frame)
            if bbox is not None:
                return bbox

        if self._allow_fallback:
            return self._fallback_bbox(frame)
        return None

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
        """Trả về vùng trung tâm khung hình khi cascade thất bại và fallback được bật."""
        h, w = frame.shape[:2]
        cfg = self._cfg
        return (
            int(cfg.fallback_x_ratio * w),
            int(cfg.fallback_y_ratio * h),
            int(cfg.fallback_width_ratio * w),
            int(cfg.fallback_height_ratio * h),
        )


class MediaPipeFaceDetector(BaseFaceDetector):
    """
    Bộ phát hiện khuôn mặt và 468–478 điểm mốc 3D dùng Google MediaPipe Face Landmarker.

    - Tự động tính Bounding Box bao quanh mặt (x, y, w, h) tương thích 100% với Frontend.
    - Cung cấp tọa độ 468–478 điểm mốc giải phẫu qua method get_landmarks().
    - Tự động fallback về HaarCascadeFaceDetector nếu mediapipe chưa sẵn sàng hoặc model lỗi.
    """

    def __init__(
        self,
        enable_smoothing: bool = True,
        config: Optional[FaceDetectorConfig] = None,
    ) -> None:
        self._cfg = config if config is not None else FaceDetectorConfig()
        self._smoother = (
            BBoxSmoother(
                alpha=self._cfg.smoothing_alpha,
                max_missing_frames=self._cfg.max_missing_frames,
            )
            if enable_smoothing
            else None
        )
        self._current_landmarks: Optional[np.ndarray] = None
        self._fallback_detector: Optional[HaarCascadeFaceDetector] = None
        self._landmarker = self._init_landmarker()

    def _init_landmarker(self):
        """Khởi tạo MediaPipe Face Landmarker Task."""
        try:
            import mediapipe as mp
            from mediapipe.tasks import python
            from mediapipe.tasks.python import vision

            model_path = self._cfg.mediapipe_model_path
            if model_path is None or not os.path.exists(model_path):
                base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "models"))
                candidate = os.path.join(base_dir, "face_landmarker.task")
                if os.path.exists(candidate):
                    model_path = candidate

            if model_path is None or not os.path.exists(model_path):
                return None

            base_options = python.BaseOptions(model_asset_path=model_path)
            options = vision.FaceLandmarkerOptions(
                base_options=base_options,
                num_faces=1,
                min_face_detection_confidence=0.4,
                min_face_presence_confidence=0.4,
            )
            return vision.FaceLandmarker.create_from_options(options)
        except Exception:
            return None

    def detect(self, frame: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
        raw_bbox = self._detect_raw(frame)
        if self._smoother is not None:
            return self._smoother.update(raw_bbox)
        return raw_bbox

    def get_landmarks(self) -> Optional[np.ndarray]:
        """Trả về mảng (N, 2) int32 tọa độ pixel (x, y) trên frame hiện tại."""
        return self._current_landmarks

    def reset(self) -> None:
        self._current_landmarks = None
        if self._smoother is not None:
            self._smoother.reset()

    def _detect_raw(self, frame: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
        if frame is None or frame.size == 0:
            self._current_landmarks = None
            return None

        if self._landmarker is None:
            if self._fallback_detector is None:
                self._fallback_detector = HaarCascadeFaceDetector(enable_smoothing=False, config=self._cfg)
            self._current_landmarks = None
            return self._fallback_detector.detect(frame)

        try:
            import mediapipe as mp
            h, w = frame.shape[:2]
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB) if frame.ndim == 3 else frame
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            result = self._landmarker.detect(mp_image)

            if result and result.face_landmarks and len(result.face_landmarks) > 0:
                lms = result.face_landmarks[0]
                pts = np.array(
                    [[int(np.clip(lm.x * w, 0, w - 1)), int(np.clip(lm.y * h, 0, h - 1))] for lm in lms],
                    dtype=np.int32,
                )
                self._current_landmarks = pts

                min_x = int(np.min(pts[:, 0]))
                max_x = int(np.max(pts[:, 0]))
                min_y = int(np.min(pts[:, 1]))
                max_y = int(np.max(pts[:, 1]))
                return (min_x, min_y, max(1, max_x - min_x), max(1, max_y - min_y))

        except Exception:
            pass

        self._current_landmarks = None
        if self._fallback_detector is None:
            self._fallback_detector = HaarCascadeFaceDetector(enable_smoothing=False, config=self._cfg)
        return self._fallback_detector.detect(frame)


# Backward compatibility alias
SimpleFaceDetector = HaarCascadeFaceDetector


