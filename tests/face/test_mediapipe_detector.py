"""
tests/face/test_mediapipe_detector.py
=====================================
Kiểm thử bộ phát hiện khuôn mặt và trích xuất điểm mốc MediaPipe (Level 2).
"""
import unittest
from unittest.mock import MagicMock
import numpy as np

from aivitals_engine.config.settings import FaceDetectorConfig
from aivitals_engine.face.detector import (
    BaseFaceDetector,
    MediaPipeFaceDetector,
    SimpleFaceDetector,
)


class TestMediaPipeDetector(unittest.TestCase):
    """Kiểm thử MediaPipeFaceDetector và cơ chế Fallback."""

    def test_base_detector_default_landmarks_none(self):
        """Interface BaseFaceDetector mặc định trả về None cho landmarks."""
        simple = SimpleFaceDetector()
        self.assertIsNone(simple.get_landmarks())

    def test_detector_initialization(self):
        """Khởi tạo MediaPipeFaceDetector thành công, landmarks ban đầu là None."""
        detector = MediaPipeFaceDetector()
        self.assertIsNone(detector.get_landmarks())

    def test_detect_none_or_empty_frame(self):
        """Frame rỗng hoặc None trả về None và không báo lỗi."""
        detector = MediaPipeFaceDetector()
        self.assertIsNone(detector.detect(None))
        self.assertIsNone(detector.get_landmarks())

        empty = np.zeros((0, 0, 3), dtype=np.uint8)
        self.assertIsNone(detector.detect(empty))
        self.assertIsNone(detector.get_landmarks())

    def test_fallback_when_model_missing(self):
        """Khi đường dẫn model không tồn tại, tự động fallback về SimpleFaceDetector."""
        cfg = FaceDetectorConfig(
            detector_backend="mediapipe",
            mediapipe_model_path="nonexistent_path/fake_model.task",
        )
        detector = MediaPipeFaceDetector(config=cfg)
        frame = np.full((300, 300, 3), 128, dtype=np.uint8)
        bbox = detector.detect(frame)
        # Fallback về SimpleFaceDetector -> trả về central bbox
        self.assertIsNotNone(bbox)
        self.assertEqual(len(bbox), 4)
        self.assertIsNone(detector.get_landmarks())

    def test_reset_clears_landmarks(self):
        """Gọi reset() phải xóa trạng thái landmarks hiện tại."""
        detector = MediaPipeFaceDetector()
        detector._current_landmarks = np.zeros((468, 2), dtype=np.int32)
        detector.reset()
        self.assertIsNone(detector.get_landmarks())

    def test_detection_with_mocked_landmarker(self):
        """Kiểm thử tính toán BBox và lưu trữ 468 điểm mốc khi FaceLandmarker trả kết quả."""
        detector = MediaPipeFaceDetector()

        # Tạo mock result từ MediaPipe FaceLandmarker
        mock_landmarker = MagicMock()
        mock_result = MagicMock()
        
        # 468 landmarks normalized [0, 1]
        mock_lms = []
        for i in range(468):
            lm = MagicMock()
            lm.x = 0.2 + (i % 20) * 0.01  # Trong khoảng [0.2, 0.4]
            lm.y = 0.3 + (i // 20) * 0.01 # Trong khoảng [0.3, 0.53]
            mock_lms.append(lm)

        mock_result.face_landmarks = [mock_lms]
        mock_landmarker.detect.return_value = mock_result
        detector._landmarker = mock_landmarker

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        bbox = detector.detect(frame)

        self.assertIsNotNone(bbox)
        self.assertEqual(len(bbox), 4)
        x, y, w, h = bbox
        self.assertGreater(w, 0)
        self.assertGreater(h, 0)

        landmarks = detector.get_landmarks()
        self.assertIsNotNone(landmarks)
        self.assertEqual(landmarks.shape, (468, 2))
        self.assertEqual(landmarks.dtype, np.int32)

        # Kiểm tra tọa độ nằm trong frame
        self.assertTrue(np.all(landmarks[:, 0] >= 0))
        self.assertTrue(np.all(landmarks[:, 0] < 640))
        self.assertTrue(np.all(landmarks[:, 1] >= 0))
        self.assertTrue(np.all(landmarks[:, 1] < 480))


if __name__ == "__main__":
    unittest.main()
