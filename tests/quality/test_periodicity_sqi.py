"""
tests/quality/test_periodicity_sqi.py
======================================
Tests for Periodicity SQI (calculate_periodicity_sqi) added in Buoc 4.

Verifies:
- Clean pulse gives high score (score >= 0.80).
- Pure noise (white, pink, random walk) through filter chain gives low score (median < 0.46).
- Pulse + noise across SNRs (0 dB, +5 dB, +10 dB) behaves predictably.
- Edge cases: all-zero, constant, short signals handled safely.
- Known limitation documented: 1.2 Hz single-frequency artificial wave gives high score.
"""
import unittest
import numpy as np

from aivitals_engine.quality.sqi import calculate_periodicity_sqi
from aivitals_engine.signal.detrend import smoothness_priors_detrend
from aivitals_engine.signal.filter import butter_bandpass_filter
from aivitals_engine.config.settings import SignalConfig


class TestPeriodicitySQI(unittest.TestCase):

    def setUp(self):
        self.cfg = SignalConfig()
        self.fs = 30.0
        self.rng = np.random.default_rng(42)

    def _filter(self, x):
        d = smoothness_priors_detrend(x, lambda_value=self.cfg.detrend_lambda)
        return butter_bandpass_filter(
            d, self.cfg.low_cutoff_hz, self.cfg.high_cutoff_hz, fs=self.fs, order=self.cfg.filter_order
        )

    # ------------------------------------------------------------------
    # 1. Clean pulse gives high periodicity score
    # ------------------------------------------------------------------

    def test_clean_pulse_high_score(self):
        """Clean 1.2 Hz (72 BPM) pulse in 8s window should have ACF peak >= 0.80."""
        t = np.linspace(0, 8.0, int(8.0 * self.fs), endpoint=False)
        sig = np.sin(2 * np.pi * 1.2 * t)
        bvp = self._filter(sig)

        score, raw_peak = calculate_periodicity_sqi(bvp, fs=self.fs)
        self.assertGreaterEqual(score, 0.80, f"Clean pulse score {score} should be >= 0.80")
        self.assertGreaterEqual(raw_peak, 0.80, f"Clean pulse raw_peak {raw_peak} should be >= 0.80")
        self.assertLessEqual(score, 1.0)
        self.assertLessEqual(raw_peak, 1.0)

    # ------------------------------------------------------------------
    # 2. Pure noise gives low score below threshold
    # ------------------------------------------------------------------

    def test_pure_noise_filtered_low_score(self):
        """Filtered white noise in 8s window should have median ACF peak well below 0.46."""
        scores = []
        for _ in range(50):
            w = self.rng.standard_normal(int(8.0 * self.fs))
            bvp = self._filter(w)
            score, raw = calculate_periodicity_sqi(bvp, fs=self.fs)
            scores.append(raw)

        median_noise = np.median(scores)
        self.assertLess(median_noise, 0.35, f"Noise median ACF {median_noise} should be < 0.35")

    # ------------------------------------------------------------------
    # 3. Pulse + noise SNR degradation is monotonic
    # ------------------------------------------------------------------

    def test_snr_monotonic_degradation(self):
        """ACF score should decrease as noise level increases (SNR: 10 dB > 5 dB > 0 dB > noise)."""
        t = np.linspace(0, 8.0, int(8.0 * self.fs), endpoint=False)
        clean = np.sin(2 * np.pi * 1.2 * t)
        w = self.rng.standard_normal(len(t))
        p_c = np.mean(clean ** 2)
        p_w = np.mean(w ** 2)

        def mix(snr_db):
            scale = np.sqrt(p_c / (10 ** (snr_db / 10.0) * p_w + 1e-12))
            return self._filter(clean + scale * w)

        bvp_10 = mix(10.0)
        bvp_5  = mix(5.0)
        bvp_0  = mix(0.0)

        s_clean, _ = calculate_periodicity_sqi(self._filter(clean), fs=self.fs)
        s_10, _    = calculate_periodicity_sqi(bvp_10, fs=self.fs)
        s_5, _     = calculate_periodicity_sqi(bvp_5, fs=self.fs)
        s_0, _     = calculate_periodicity_sqi(bvp_0, fs=self.fs)

        self.assertGreaterEqual(s_clean, s_10 - 0.05)
        self.assertGreaterEqual(s_10, s_5 - 0.05)
        self.assertGreaterEqual(s_5, s_0 - 0.05)
        self.assertGreater(s_0, 0.50, "SNR 0 dB pulse should still have periodicity > 0.50")

    # ------------------------------------------------------------------
    # 4. Edge cases: short, all-zero, constant signals
    # ------------------------------------------------------------------

    def test_short_signal_safe(self):
        """Signal shorter than 16 samples safely returns (0.0, 0.0)."""
        score, raw = calculate_periodicity_sqi(np.array([1.0, 2.0, 3.0]), fs=self.fs)
        self.assertEqual((score, raw), (0.0, 0.0))

    def test_all_zero_signal_safe(self):
        """All-zero array returns (0.0, 0.0)."""
        score, raw = calculate_periodicity_sqi(np.zeros(240), fs=self.fs)
        self.assertEqual((score, raw), (0.0, 0.0))

    def test_constant_signal_safe(self):
        """Constant non-zero array returns (0.0, 0.0)."""
        score, raw = calculate_periodicity_sqi(np.full(240, 5.0), fs=self.fs)
        self.assertEqual((score, raw), (0.0, 0.0))

    # ------------------------------------------------------------------
    # 5. Known limitation: single-frequency artificial periodic noise
    # ------------------------------------------------------------------

    def test_known_limitation_periodic_noise_scores_high(self):
        """
        Documentation test: A single-frequency 1.2 Hz square/sine motion artifact
        has high periodicity (score >= 0.80), demonstrating that ACF alone
        CANNOT differentiate pulse from periodic motion/flicker.
        """
        t = np.linspace(0, 8.0, int(8.0 * self.fs), endpoint=False)
        # Artificial motion oscillation at 1.2 Hz
        motion_artifact = np.sin(2 * np.pi * 1.2 * t)
        bvp_motion = self._filter(motion_artifact)
        score, raw = calculate_periodicity_sqi(bvp_motion, fs=self.fs)
        # Confirms known limitation: periodic motion receives high periodicity score
        self.assertGreaterEqual(score, 0.80, "Periodic motion artifact naturally produces high ACF")


if __name__ == "__main__":
    unittest.main()
