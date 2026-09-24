import unittest
import numpy as np

from aivitals_engine.signal.sliding_buffer import SlidingWindowBuffer


class TestSlidingWindowBuffer(unittest.TestCase):
    """Kiểm thử cho signal/sliding_buffer.py."""

    def test_dc_component_retention(self):
        """Kiểm chứng get_resampled_window giữ nguyên thành phần DC sáng nền."""
        buf = SlidingWindowBuffer(window_sec=4.0, target_fps=30.0, min_sec=2.0)
        expected_dc = np.array([180.0, 120.0, 90.0])

        for i in range(90):
            t = i / 30.0
            noise = np.random.normal(0, 0.5, size=3)
            buf.push(expected_dc + noise, timestamp=t)

        self.assertTrue(buf.is_ready())
        resampled_rgb, fps = buf.get_resampled_window()

        self.assertEqual(resampled_rgb.shape[1], 3)
        self.assertAlmostEqual(fps, 30.0, delta=1.5)

        mean_rgb = np.mean(resampled_rgb, axis=0)
        for ch in range(3):
            self.assertAlmostEqual(mean_rgb[ch], expected_dc[ch], delta=2.0)

    def test_time_gap_handling(self):
        """Kiểm chứng tự động reset khi mất mặt/đứt đoạn thời gian > 0.5s."""
        buf = SlidingWindowBuffer(window_sec=4.0, target_fps=30.0, min_sec=1.0, time_gap_threshold=0.5)

        for i in range(30):
            buf.push([150, 100, 80], timestamp=i * 0.033)

        self.assertEqual(buf.size, 30)

        # Ngắt quãng 2.0s
        buf.push([150, 100, 80], timestamp=30 * 0.033 + 2.0)
        self.assertEqual(buf.size, 1, "Buffer phải tự động reset khi có time gap > 0.5s")

    def test_push_shape_validation(self):
        """Buffer phải từ chối các định dạng không đúng vector 3 kênh RGB."""
        buf = SlidingWindowBuffer()
        with self.assertRaises(ValueError):
            buf.push([1, 2])
        with self.assertRaises(ValueError):
            buf.push([1, 2, 3, 4])

    def test_artifact_detection_spike_rejection(self):
        """Kiểm tra cơ chế gạt bỏ frame đột biến (> 3.5 std)."""
        buf = SlidingWindowBuffer(artifact_threshold=3.5)

        for i in range(25):
            noise = np.random.normal(0, 0.2, 3)
            accepted = buf.push(np.array([160.0, 110.0, 85.0]) + noise, timestamp=i * 0.033)
            self.assertTrue(accepted)

        self.assertEqual(buf.artifact_count, 0)

        # Bơm 1 frame đột biến cực mạnh
        spike_frame = np.array([255.0, 255.0, 255.0])
        accepted_spike = buf.push(spike_frame, timestamp=25 * 0.033)

        self.assertFalse(accepted_spike)
        self.assertEqual(buf.artifact_count, 1)

    def test_fps_estimation_with_jitter(self):
        """Ước tính FPS thực tế ổn định ngay cả khi thời gian camera bị giật (jitter)."""
        buf = SlidingWindowBuffer(target_fps=30.0)
        ts = 0.0
        delays = [0.030, 0.036, 0.033, 0.034, 0.032, 0.035, 0.033]
        for d in delays * 5:
            ts += d
            buf.push([150, 100, 80], timestamp=ts)

        estimated_fps = buf.get_fps()
        self.assertGreater(estimated_fps, 28.0)
        self.assertLess(estimated_fps, 32.0)


if __name__ == "__main__":
    unittest.main()
