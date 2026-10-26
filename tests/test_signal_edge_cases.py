import unittest
import numpy as np

from aivitals_engine.face.detector import SimpleFaceDetector
from aivitals_engine.signal.sliding_buffer import SlidingWindowBuffer
from aivitals_engine.signal_pipeline_realtime import RealtimeSignalPipeline, FrameResult


class MockTinyFaceDetector(SimpleFaceDetector):
    """Detector giả lập trả về bbox nhỏ so với kích thước khung hình."""
    def detect(self, frame):
        # Trả về bbox rộng 30px (trên khung hình 640px -> ratio ~ 4.7% < 12%)
        return (100, 100, 30, 30)

    def get_landmarks(self):
        return None


class TestSignalEdgeCases(unittest.TestCase):
    """Bộ kiểm thử cho tình huống biên và cảnh báo môi trường (Week 7)."""

    def test_consecutive_artifacts_auto_recovery(self):
        """Kiểm chứng tự động thích nghi khi ánh sáng đổi bước nhảy liên tiếp."""
        buf = SlidingWindowBuffer(
            window_sec=4.0, target_fps=30.0, min_sec=1.0,
            artifact_threshold=3.5, max_consecutive_artifacts=5
        )

        # 1. Nạp baseline ổn định 25 frames
        base_rgb = np.array([120.0, 90.0, 80.0])
        for i in range(25):
            noise = np.random.normal(0, 0.1, 3)
            ok = buf.push(base_rgb + noise, timestamp=i * 0.033)
            self.assertTrue(ok)

        self.assertEqual(buf.artifact_count, 0)
        self.assertEqual(buf.size, 25)

        # 2. Bước nhảy ánh sáng mạnh (bật đèn): RGB nhảy vọt lên [210, 180, 170]
        jump_rgb = np.array([210.0, 180.0, 170.0])
        
        # 4 frames đầu: bị từ chối do là artifact so với baseline cũ
        for i in range(4):
            ts = (25 + i) * 0.033
            accepted = buf.push(jump_rgb, timestamp=ts)
            self.assertFalse(accepted, f"Frame {i+1} phải bị gạt bỏ")
        
        self.assertEqual(buf.artifact_count, 4)

        # Frame thứ 5: đạt ngưỡng max_consecutive_artifacts=5 -> auto-recovery kích hoạt!
        ts_recovery = 29 * 0.033
        accepted_recovery = buf.push(jump_rgb, timestamp=ts_recovery)
        self.assertTrue(accepted_recovery, "Frame thứ 5 phải được chấp nhận và tái lập baseline")

        # Frame thứ 6 trở đi: tiếp tục được chấp nhận với baseline mới
        ts_next = 30 * 0.033
        accepted_next = buf.push(jump_rgb + np.array([1.0, 0.0, -1.0]), timestamp=ts_next)
        self.assertTrue(accepted_next, "Frame thứ 6 phải được chấp nhận với baseline mới")
        self.assertGreaterEqual(buf.size, 2)

    def test_micro_face_lost_tolerance(self):
        """Kiểm chứng mất mặt ngắn hạn (micro-dropout <= 1.0s) không làm mất buffer."""
        pipeline = RealtimeSignalPipeline(window_sec=3.0, min_sec=1.0, target_fps=30.0)

        # 1. Nạp 35 frames da mặt bình thường -> pipeline sẵn sàng (is_ready = True)
        frame = np.full((100, 100, 3), 128, dtype=np.uint8)
        result = None
        for i in range(35):
            result = pipeline.process_frame(frame, timestamp=i * 0.033)

        self.assertTrue(result.is_ready)
        self.assertIn(result.status, ["OK", "LOW_QUALITY"])

        # 2. Giả lập mất mặt ngắn hạn trong 0.4s (12 frames)
        empty_frame = np.zeros((0, 0, 3), dtype=np.uint8)
        for i in range(12):
            ts = (35 + i) * 0.033
            res_lost = pipeline.process_frame(empty_frame, timestamp=ts)
            self.assertEqual(res_lost.status, "FACE_LOST")
            self.assertFalse(res_lost.is_ready)
            self.assertIn("FACE_NOT_FOUND", res_lost.warnings)

        # 3. Mặt xuất hiện lại ở frame 48 (tổng thời gian mất mặt ~ 0.4s <= max_face_lost_sec=1.0s)
        ts_resume = 48 * 0.033
        res_resume = pipeline.process_frame(frame, timestamp=ts_resume)
        
        # Buffer không bị reset về 0, pipeline sẵn sàng tiếp tục ngay!
        self.assertTrue(res_resume.is_ready, "Pipeline phải sẵn sàng ngay sau khi tìm lại mặt ngắn hạn")
        self.assertIn(res_resume.status, ["OK", "LOW_QUALITY"])

    def test_long_face_lost_triggers_reset(self):
        """Kiểm chứng mất mặt kéo dài (> 1.0s) phải reset buffer để tránh trôi tim."""
        pipeline = RealtimeSignalPipeline(window_sec=3.0, min_sec=1.0, target_fps=30.0)

        # 1. Nạp 35 frames da mặt -> ready
        frame = np.full((100, 100, 3), 128, dtype=np.uint8)
        for i in range(35):
            pipeline.process_frame(frame, timestamp=i * 0.033)

        self.assertTrue(pipeline.is_ready)

        # 2. Mất mặt trong 1.8s (> 1.0s)
        empty_frame = np.zeros((0, 0, 3), dtype=np.uint8)
        t_start_lost = 35 * 0.033
        # Frame đầu mất mặt
        pipeline.process_frame(empty_frame, timestamp=t_start_lost)
        # Frame sau 1.8s
        res_long_lost = pipeline.process_frame(empty_frame, timestamp=t_start_lost + 1.8)
        self.assertEqual(res_long_lost.status, "FACE_LOST")

        # 3. Mặt xuất hiện lại -> do đã mất mặt > 1.0s nên buffer đã bị reset
        res_after = pipeline.process_frame(frame, timestamp=t_start_lost + 1.85)
        self.assertFalse(res_after.is_ready, "Buffer phải được reset về BUFFERING sau khi mất mặt dài")
        self.assertEqual(res_after.status, "BUFFERING")

    def test_environmental_warnings_too_dark(self):
        """Kiểm tra cảnh báo TOO_DARK khi môi trường quá tối."""
        pipeline = RealtimeSignalPipeline()
        dark_frame = np.full((100, 100, 3), 15, dtype=np.uint8)  # BGR = 15 -> luma ~ 15 < 40

        res = pipeline.process_frame(dark_frame, timestamp=0.033)
        self.assertIn("TOO_DARK", res.warnings)
        self.assertLess(res.luma, 40.0)

    def test_environmental_warnings_too_bright(self):
        """Kiểm tra cảnh báo TOO_BRIGHT khi môi trường quá chói."""
        pipeline = RealtimeSignalPipeline()
        bright_frame = np.full((100, 100, 3), 245, dtype=np.uint8)  # BGR = 245 -> luma ~ 245 > 225

        res = pipeline.process_frame(bright_frame, timestamp=0.033)
        self.assertIn("TOO_BRIGHT", res.warnings)
        self.assertGreater(res.luma, 225.0)

    def test_face_too_small_warning(self):
        """Kiểm tra cảnh báo FACE_TOO_SMALL khi khuôn mặt quá xa camera."""
        detector = MockTinyFaceDetector()
        pipeline = RealtimeSignalPipeline(face_detector=detector)
        
        # Khung hình 640x480, detector trả về bbox rộng 30px (30/640 = 0.047 < 0.12)
        frame = np.full((480, 640, 3), 128, dtype=np.uint8)
        res = pipeline.process_frame(frame, timestamp=0.033)

        self.assertIn("FACE_TOO_SMALL", res.warnings)
        self.assertLess(res.face_width_ratio, 0.12)


if __name__ == "__main__":
    unittest.main()
