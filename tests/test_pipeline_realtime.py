import unittest
import numpy as np

from aivitals_engine.pipeline_realtime import RealtimeRGBPipeline, FrameResult


class TestRealtimeRGBPipeline(unittest.TestCase):
    """Kiểm thử tích hợp cho pipeline_realtime.py."""

    def test_pipeline_buffering_to_ready(self):
        pipeline = RealtimeRGBPipeline(window_sec=3.0, min_sec=1.5, target_fps=30.0)

        # 1. Ảnh rỗng hoặc mất mặt
        res_empty = pipeline.process_frame(np.zeros((0, 0, 3), dtype=np.uint8))
        self.assertEqual(res_empty.status, "FACE_LOST")
        self.assertFalse(res_empty.is_ready)

        # 2. Khung hình da mặt giả lập 100x100 BGR
        frame = np.full((100, 100, 3), 128, dtype=np.uint8)

        # Giai đoạn 1: Buffer chưa đủ 1.5s
        result = None
        for i in range(30):
            result = pipeline.process_frame(frame, timestamp=i * 0.033)

        self.assertFalse(result.is_ready)
        self.assertEqual(result.status, "BUFFERING")
        self.assertIsNone(result.bvp_signal)

        # Giai đoạn 2: Bơm thêm đến > 1.5s
        for i in range(30, 65):
            result = pipeline.process_frame(frame, timestamp=i * 0.033)

        self.assertTrue(result.is_ready)
        self.assertIn(result.status, ["OK", "LOW_QUALITY"])
        self.assertIsNotNone(result.bvp_signal)
        self.assertGreater(len(result.bvp_signal), 0)
        self.assertGreaterEqual(result.quality_sqi, 0.0)


if __name__ == "__main__":
    unittest.main()
