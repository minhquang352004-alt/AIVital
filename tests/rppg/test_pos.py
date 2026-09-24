import unittest
import numpy as np
from scipy import signal

from aivitals_engine.rppg.pos import POSMethod
from aivitals_engine.quality.sqi import calculate_bvp_quality


class TestPOSMethod(unittest.TestCase):
    """Kiểm thử thuật toán POS (Plane-Orthogonal-to-Skin) trong rppg/pos.py."""

    def setUp(self):
        self.fs = 30.0
        self.duration = 8.0
        self.N = int(self.fs * self.duration)
        self.t = np.linspace(0, self.duration, self.N, endpoint=False)

        heart_freq = 1.2  # 72 BPM
        pulse = np.sin(2 * np.pi * heart_freq * self.t)

        r_sig = 160.0 - 0.6 * pulse + np.random.normal(0, 0.05, self.N)
        g_sig = 110.0 - 1.8 * pulse + np.random.normal(0, 0.05, self.N)
        b_sig = 85.0 - 0.3 * pulse + np.random.normal(0, 0.05, self.N)
        drift = 4.0 * np.sin(2 * np.pi * 0.1 * self.t)
        self.synthetic_rgb = np.column_stack([r_sig + drift, g_sig + drift, b_sig + drift])

    def test_pos_accuracy_and_sqi(self):
        pos = POSMethod(fps=self.fs, lowcut=0.75, highcut=2.50)
        bvp = pos.process(self.synthetic_rgb)

        freqs, pxx = signal.periodogram(bvp, fs=self.fs, nfft=1024)
        mask = (freqs >= 0.75) & (freqs <= 2.50)
        peak_freq = freqs[mask][np.argmax(pxx[mask])]

        self.assertAlmostEqual(peak_freq, 1.2, delta=0.05)
        sqi = calculate_bvp_quality(bvp, fs=self.fs)
        self.assertGreater(sqi, 0.50)

    def test_pos_metadata(self):
        """Streaming API: update() + get_signal() → get_metadata() trả metadata hợp lệ."""
        pos = POSMethod(fps=self.fs)
        pos.update(self.synthetic_rgb)    # Đẩy toàn bộ dữ liệu vào streaming buffer
        pos.get_signal()                  # Tính BVP từ streaming buffer
        meta = pos.get_metadata()
        self.assertEqual(meta["method"], "POS")
        self.assertEqual(meta["signal_length"], self.N)


if __name__ == "__main__":
    unittest.main()
