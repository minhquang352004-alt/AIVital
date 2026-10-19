"""
tests/roi/test_polygon_roi.py
=============================
Kiểm thử trích xuất ROI theo Đa giác mốc giải phẫu 3D (Level 2).
"""
import unittest
import numpy as np

from aivitals_engine.config.settings import FaceDetectorConfig, ROIConfig
from aivitals_engine.face.detector import BaseFaceDetector
from aivitals_engine.face.landmarks import (
    FOREHEAD_LANDMARKS,
    LEFT_CHEEK_LANDMARKS,
    RIGHT_CHEEK_LANDMARKS,
)
from aivitals_engine.roi.extractor import ROIExtractor, SubROIResult
from aivitals_engine.signal_pipeline_realtime import RealtimeSignalPipeline


class MockLandmarkDetector(BaseFaceDetector):
    """Detector giả lập trả về BBox và 468 mốc tọa độ pixel cố định."""

    def __init__(self, landmarks: np.ndarray, bbox=(100, 100, 200, 200)):
        self._landmarks = landmarks
        self._bbox = bbox

    def detect(self, frame):
        return self._bbox

    def get_landmarks(self):
        return self._landmarks


class TestPolygonROIExtraction(unittest.TestCase):
    """Kiểm thử thuật toán trích xuất đa giác convex hull trên mốc MediaPipe."""

    def setUp(self):
        # Tạo mảng landmarks 468 điểm mặc định nằm trong khoảng [100, 250]
        self.landmarks = np.zeros((468, 2), dtype=np.int32)
        # Gán tọa độ hợp lệ cho forehead [120..180, 50..90]
        for idx in FOREHEAD_LANDMARKS:
            self.landmarks[idx] = [150 + (idx % 20) * 2, 60 + (idx % 10) * 2]
        # Gán tọa độ hợp lệ cho left cheek [110..140, 120..150]
        for idx in LEFT_CHEEK_LANDMARKS:
            self.landmarks[idx] = [120 + (idx % 10) * 2, 130 + (idx % 10) * 2]
        # Gán tọa độ hợp lệ cho right cheek [170..200, 120..150]
        for idx in RIGHT_CHEEK_LANDMARKS:
            self.landmarks[idx] = [180 + (idx % 10) * 2, 130 + (idx % 10) * 2]

        self.extractor = ROIExtractor(config=ROIConfig(enable_skin_filter=False))

    def test_crop_polygon_pixels_boundary_cases(self):
        """None frame hoặc ít hơn 3 điểm mốc phải trả về None."""
        pts = np.array([[10, 10], [20, 20]], dtype=np.int32)
        frame = np.zeros((200, 200, 3), dtype=np.uint8)

        self.assertIsNone(self.extractor._crop_polygon_pixels(None, pts))
        self.assertIsNone(self.extractor._crop_polygon_pixels(frame, None))
        self.assertIsNone(self.extractor._crop_polygon_pixels(frame, pts))

    def test_crop_polygon_pixels_synthetic_color(self):
        """Cắt đa giác từ frame có màu đồng nhất BGR=[10, 20, 30] phải trả về pixel đúng màu."""
        frame = np.zeros((200, 200, 3), dtype=np.uint8)
        frame[:] = [10, 20, 30]

        # Tam giác nằm hoàn toàn trong frame
        triangle = np.array([[50, 50], [80, 50], [65, 80]], dtype=np.int32)
        pixels = self.extractor._crop_polygon_pixels(frame, triangle)

        self.assertIsNotNone(pixels)
        self.assertGreater(len(pixels), 0)
        # BGR=[10, 20, 30]
        mean_bgr = np.mean(pixels, axis=0)
        np.testing.assert_allclose(mean_bgr, [10.0, 20.0, 30.0], atol=1e-3)

    def test_extract_mean_rgb_with_landmarks(self):
        """extract_mean_rgb ưu tiên sử dụng landmarks và trả về mảng shape (3,) RGB float64."""
        # Frame màu thuần túy BGR = [50, 100, 150] => RGB = [150, 100, 50]
        frame = np.zeros((300, 300, 3), dtype=np.uint8)
        frame[:, :] = [50, 100, 150]

        mean_rgb = self.extractor.extract_mean_rgb(frame, bbox=(50, 50, 200, 200), landmarks=self.landmarks)
        self.assertEqual(mean_rgb.shape, (3,))
        self.assertEqual(mean_rgb.dtype, np.float64)
        np.testing.assert_allclose(mean_rgb, [150.0, 100.0, 50.0], atol=1e-3)

    def test_extract_mean_rgb_fallback_when_landmarks_none(self):
        """Khi landmarks=None, extract_mean_rgb sử dụng bbox chữ nhật như Level 1 / Baseline."""
        frame = np.zeros((300, 300, 3), dtype=np.uint8)
        frame[:, :] = [40, 80, 120]  # RGB = [120, 80, 40]

        mean_rgb = self.extractor.extract_mean_rgb(frame, bbox=(50, 50, 100, 100), landmarks=None)
        np.testing.assert_allclose(mean_rgb, [120.0, 80.0, 40.0], atol=1e-3)

    def test_extract_sub_roi_rgbs_with_landmarks(self):
        """extract_sub_roi_rgbs trả về SubROIResult với pixel_counts tương ứng từng vùng đa giác."""
        frame = np.zeros((300, 300, 3), dtype=np.uint8)
        frame[:] = [60, 120, 180]

        res = self.extractor.extract_sub_roi_rgbs(frame, bbox=(50, 50, 200, 200), landmarks=self.landmarks)
        self.assertIsInstance(res, SubROIResult)
        self.assertGreater(res.pixel_counts["forehead"], 0)
        self.assertGreater(res.pixel_counts["left_cheek"], 0)
        self.assertGreater(res.pixel_counts["right_cheek"], 0)
        np.testing.assert_allclose(res.forehead, [180.0, 120.0, 60.0], atol=1e-3)

    def test_pipeline_integration_with_landmarks(self):
        """RealtimeSignalPipeline truyền landmarks xuyên suốt luồng và gán vào FrameResult."""
        mock_detector = MockLandmarkDetector(landmarks=self.landmarks, bbox=(50, 50, 200, 200))
        pipeline = RealtimeSignalPipeline(
            face_detector=mock_detector,
            roi_config=ROIConfig(enable_skin_filter=False),
        )

        frame = np.zeros((300, 300, 3), dtype=np.uint8)
        frame[:] = [50, 100, 150]

        result = pipeline.process_frame(frame, timestamp=0.0)
        self.assertIsNotNone(result.landmarks)
        self.assertEqual(result.landmarks.shape, (468, 2))
        self.assertEqual(result.bbox, (50, 50, 200, 200))
        np.testing.assert_allclose(result.raw_rgb, [150.0, 100.0, 50.0], atol=1e-3)


if __name__ == "__main__":
    unittest.main()
