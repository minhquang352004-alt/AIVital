import unittest
import numpy as np

from aivitals_engine.face.detector import BBoxSmoother, SimpleFaceDetector


class TestBBoxSmoother(unittest.TestCase):
    """Kiểm thử bộ làm mịn tọa độ khuôn mặt chống giật (EMA)."""

    def test_jitter_reduction(self):
        smoother = BBoxSmoother(alpha=0.3)
        np.random.seed(42)
        base_bbox = np.array([100, 100, 80, 80])

        raw_bboxes = []
        smoothed_bboxes = []

        for _ in range(50):
            noise = np.random.randint(-5, 6, size=4)
            jittered = tuple(base_bbox + noise)
            raw_bboxes.append(jittered)
            sm = smoother.update(jittered)
            smoothed_bboxes.append(sm)

        raw_var = np.var([b[0] for b in raw_bboxes])
        smoothed_var = np.var([b[0] for b in smoothed_bboxes])

        self.assertLess(smoothed_var, raw_var * 0.5, "Bộ làm mịn phải giảm phương sai giật > 50%")

    def test_smoother_reset(self):
        smoother = BBoxSmoother(alpha=0.5)
        # Sau khi cập nhật một bbox hợp lệ, smoother phải trả về giá trị
        result_before_reset = smoother.update((100, 100, 80, 80))
        self.assertIsNotNone(result_before_reset)
        # Sau reset, mất mặt ngay lập tức phải trả None
        smoother.reset()
        result_after_reset = smoother.update(None)
        self.assertIsNone(result_after_reset)


class TestSimpleFaceDetector(unittest.TestCase):
    """Kiểm thử SimpleFaceDetector và các trường hợp biên."""

    def test_detect_empty_frame(self):
        detector = SimpleFaceDetector()
        res_none = detector.detect(None)
        self.assertIsNone(res_none)

        res_empty = detector.detect(np.zeros((0, 0, 3), dtype=np.uint8))
        self.assertIsNone(res_empty)

    def test_detect_central_fallback(self):
        # Tạo ảnh xám không có mặt, detector phải fallback về vùng 50% trung tâm
        detector = SimpleFaceDetector()
        frame = np.full((400, 400, 3), 128, dtype=np.uint8)
        bbox = detector.detect(frame)
        self.assertIsNotNone(bbox)
        self.assertEqual(len(bbox), 4)


if __name__ == "__main__":
    unittest.main()
