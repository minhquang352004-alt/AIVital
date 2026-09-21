import unittest
import numpy as np
from scipy import signal

from aivitals_engine.signal.filter import butter_bandpass_filter, normalize_signal


class TestFilter(unittest.TestCase):
    """Kiểm thử bộ lọc số và chuẩn hóa trong signal/filter.py."""

    def test_butter_bandpass_filter_attenuation(self):
        """Kiểm chứng triệt tiêu tần số ngoài dải [0.75 - 2.5 Hz]."""
        fs = 30.0
        N = 300
        t = np.linspace(0, 10.0, N, endpoint=False)

        target_wave = np.sin(2 * np.pi * 1.2 * t)
        high_noise = 2.0 * np.sin(2 * np.pi * 10.0 * t)
        combined = target_wave + high_noise

        filtered = butter_bandpass_filter(combined, lowcut=0.75, highcut=2.50, fs=fs, order=2)

        freqs, pxx = signal.periodogram(filtered, fs=fs, nfft=512)
        idx_10hz = np.argmin(np.abs(freqs - 10.0))
        idx_target = np.argmin(np.abs(freqs - 1.2))

        self.assertLess(pxx[idx_10hz], pxx[idx_target] * 0.01, "Nhiễu 10 Hz phải bị triệt tiêu > 99%")

    def test_normalize_signal_zscore(self):
        """Kiểm tra chuẩn hóa Z-score (mean=0, std=1) và ca tín hiệu phẳng."""
        data = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
        norm = normalize_signal(data)
        self.assertAlmostEqual(np.mean(norm), 0.0, delta=1e-6)
        self.assertAlmostEqual(np.std(norm), 1.0, delta=1e-6)

        # Ca tín hiệu phẳng hoàn toàn (std = 0)
        flat = np.full(20, 5.0)
        flat_norm = normalize_signal(flat)
        self.assertTrue(np.all(flat_norm == 0.0))


if __name__ == "__main__":
    unittest.main()
