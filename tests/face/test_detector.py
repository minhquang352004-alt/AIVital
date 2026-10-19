import unittest
import numpy as np

from aivitals_engine.face.detector import (
    BaseFaceDetector,
    BBoxSmoother,
    HaarCascadeFaceDetector,
    SimpleFaceDetector,
)


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


class TestHaarCascadeFaceDetector(unittest.TestCase):
    """Kiểm thử HaarCascadeFaceDetector với mô hình haarcascade_frontalface_default.xml."""

    def test_cascade_loaded_successfully(self):
        detector = HaarCascadeFaceDetector()
        self.assertIsNotNone(detector._cascade, "Cascade classifier không được None")
        self.assertFalse(detector._cascade.empty(), "Cascade classifier phải tải thành công tệp XML")

    def test_detect_empty_frame(self):
        detector = HaarCascadeFaceDetector()
        self.assertIsNone(detector.detect(None))
        self.assertIsNone(detector.detect(np.zeros((0, 0, 3), dtype=np.uint8)))

    def test_strict_mode_returns_none_on_blank_frame(self):
        # Khi allow_fallback=False, không được bịa ra bbox nếu không có mặt
        detector = HaarCascadeFaceDetector(allow_fallback=False)
        blank_frame = np.full((300, 300, 3), 128, dtype=np.uint8)
        bbox = detector.detect(blank_frame)
        self.assertIsNone(bbox, "Strict mode phải trả về None khi không phát hiện mặt")

    def test_fallback_mode_returns_central_bbox(self):
        # Khi allow_fallback=True, trả về bbox trung tâm cho synthetic frames
        detector = HaarCascadeFaceDetector(allow_fallback=True)
        blank_frame = np.full((400, 400, 3), 128, dtype=np.uint8)
        bbox = detector.detect(blank_frame)
        self.assertIsNotNone(bbox)
        self.assertEqual(len(bbox), 4)

    def test_detect_real_face_on_sample_video(self):
        import cv2, os
        sample_path = os.path.join("aivitals_engine", "samples", "vid.avi")
        if not os.path.exists(sample_path):
            self.skipTest("Sample video vid.avi không tồn tại")

        cap = cv2.VideoCapture(sample_path)
        ret, frame = cap.read()
        cap.release()
        self.assertTrue(ret, "Đọc frame đầu tiên thất bại")

        detector = HaarCascadeFaceDetector(allow_fallback=False)
        bbox = detector.detect(frame)
        self.assertIsNotNone(bbox, "Haar Cascade phải nhận diện được khuôn mặt trên vid.avi")
        x, y, w, h = bbox
        self.assertGreater(w, 50, "Độ rộng bbox khuôn mặt phải > 50px")
        self.assertGreater(h, 50, "Độ cao bbox khuôn mặt phải > 50px")

    def test_backward_compatibility_alias(self):
        self.assertIs(SimpleFaceDetector, HaarCascadeFaceDetector)


if __name__ == "__main__":
    unittest.main()

