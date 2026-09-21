import unittest
import numpy as np

from aivitals_engine.signal.resample import resample_to_fixed_fps


class TestResample(unittest.TestCase):
    """Kiểm thử nội suy thời gian trong signal/resample.py."""

    def test_resample_to_fixed_fps(self):
        raw_ts = np.array([0.0, 0.04, 0.07, 0.11, 0.14, 0.18, 0.21])
        raw_data = np.array([[10, 20], [12, 22], [14, 24], [16, 26], [18, 28], [20, 30], [22, 32]])

        resampled = resample_to_fixed_fps(raw_ts, raw_data, target_fps=30.0)
        expected_len = int(np.round((raw_ts[-1] - raw_ts[0]) * 30.0))

        self.assertEqual(resampled.shape[0], expected_len)
        self.assertEqual(resampled.shape[1], 2)

    def test_short_timestamp_safe(self):
        """Mảng thời gian < 2 phần tử trả về nguyên trạng."""
        raw_ts = np.array([0.0])
        raw_data = np.array([[10, 20]])
        res = resample_to_fixed_fps(raw_ts, raw_data, target_fps=30.0)
        self.assertTrue(np.array_equal(raw_data, res))


if __name__ == "__main__":
    unittest.main()
