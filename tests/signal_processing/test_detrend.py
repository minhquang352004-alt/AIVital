import unittest
import numpy as np

from aivitals_engine.signal.detrend import smoothness_priors_detrend


class TestDetrend(unittest.TestCase):
    """Kiểm thử thuật toán Smoothness Priors Detrending trong signal/detrend.py."""

    def test_linear_drift_removal(self):
        """Khử sạch xu hướng trôi dạt tuyến tính mà vẫn giữ dao động tuần hoàn."""
        N = 200
        t = np.linspace(0, 6.0, N)
        pure_signal = np.sin(2 * np.pi * 1.5 * t)
        linear_drift = 3.0 * t
        noisy_signal = pure_signal + linear_drift

        detrended = smoothness_priors_detrend(noisy_signal, lambda_value=100.0)

        # Trung bình phải tiệm cận 0
        self.assertAlmostEqual(np.mean(detrended), 0.0, delta=0.2)
        # Giữ được biên độ dao động hình sin
        self.assertAlmostEqual(np.std(detrended), np.std(pure_signal), delta=0.3)

    def test_short_signal_safe(self):
        """Tín hiệu quá ngắn (< 3 mẫu) trả về nguyên trạng, không crash."""
        short_sig = np.array([1.0, 2.0])
        res = smoothness_priors_detrend(short_sig)
        self.assertTrue(np.array_equal(short_sig, res))


if __name__ == "__main__":
    unittest.main()
