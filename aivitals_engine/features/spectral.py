"""
aivitals_engine/features/spectral.py
====================================
Trích xuất đặc trưng trong miền tần số và phổ BVP (Group C).

Đặc trưng gồm:
    - fundamental_freq_hz:  Tần số nhịp đập cơ bản f0 [0.75–2.5 Hz]
    - harmonic_ratio_h2:    Tỷ số năng lượng hài bậc 2 / hài bậc 1: P(2f0)/P(f0)
    - harmonic_ratio_h3:    Tỷ số năng lượng hài bậc 3 / hài bậc 1: P(3f0)/P(f0)
    - spectral_entropy:     Shannon entropy chuẩn hóa của phổ trong dải [0, 1]
    - in_band_power_ratio:  Tỷ lệ năng lượng trong dải / tổng năng lượng phổ
"""
from __future__ import annotations

from typing import Any

import numpy as np
from scipy.signal import periodogram

from aivitals_engine.features._base_extractor import PartialFeatureExtractor
from aivitals_engine.features._guards import safe_divide
from aivitals_engine.features.segmentation import SingleBeat


class SpectralExtractor(PartialFeatureExtractor):
    """Trích xuất nhóm đặc trưng phổ tần số (Group C)."""

    def extract(
        self,
        bvp: np.ndarray,
        fs: float,
        beats: list[SingleBeat],
    ) -> dict[str, Any]:
        """Trích xuất 5 đặc trưng phổ từ tín hiệu BVP."""
        sig = np.asarray(bvp, dtype=np.float64).flatten()
        if sig.size < self._cfg.min_signal_samples:
            return {}

        cfg = self._cfg
        nfft = max(cfg.spectral_nfft_min, 2 ** int(np.ceil(np.log2(sig.size))))
        freqs, pxx = periodogram(sig, fs=fs, nfft=nfft, detrend=False)

        low = cfg.fundamental_freq_low_hz
        high = cfg.fundamental_freq_high_hz
        band = (freqs >= low) & (freqs <= high)
        if not np.any(band):
            return {}

        f0  = self._fundamental_frequency(freqs, pxx, band)
        hr2 = self._harmonic_power_ratio(freqs, pxx, f0, harmonic_order=2)
        hr3 = self._harmonic_power_ratio(freqs, pxx, f0, harmonic_order=3)
        ent = self._spectral_entropy(pxx, band)
        ibp = self._in_band_power_ratio(pxx, band)

        return {
            "fundamental_freq_hz": f0,
            "harmonic_ratio_h2":   hr2,
            "harmonic_ratio_h3":   hr3,
            "spectral_entropy":    ent,
            "in_band_power_ratio": ibp,
        }

    # ── Private spectral calculation helpers ──────────────────────────────────

    def _fundamental_frequency(
        self,
        freqs: np.ndarray,
        pxx: np.ndarray,
        band: np.ndarray,
    ) -> float:
        """Tần số có mật độ công suất phổ lớn nhất trong dải tim mạch."""
        band_freqs = freqs[band]
        band_pxx = pxx[band]
        max_idx = int(np.argmax(band_pxx))
        return float(band_freqs[max_idx])

    def _harmonic_power_ratio(
        self,
        freqs: np.ndarray,
        pxx: np.ndarray,
        f0: float,
        harmonic_order: int,
    ) -> float:
        """
        Tỷ số công suất giữa hài bậc N (N*f0) và hài cơ bản f0.

        P(N*f0) / P(f0) được tích phân trong dải ±harmonic_snr_tolerance_hz.
        """
        tol = self._cfg.harmonic_snr_tolerance_hz
        fn = harmonic_order * f0
        fn_mask = (freqs >= fn - tol) & (freqs <= fn + tol)
        f0_mask = (freqs >= f0 - tol) & (freqs <= f0 + tol)

        p_fn = float(np.sum(pxx[fn_mask]))
        p_f0 = float(np.sum(pxx[f0_mask]))
        return safe_divide(p_fn, p_f0, epsilon=self._cfg.epsilon)

    def _spectral_entropy(self, pxx: np.ndarray, band: np.ndarray) -> float:
        """
        Shannon entropy chuẩn hóa của phổ trong dải [0, 1].

        Entropy cao (~1.0) → phổ phẳng, tín hiệu nhiễu/hỗn loạn.
        Entropy thấp (~0.0) → phổ tập trung vào một vài đỉnh rõ nét.
        """
        p_band = pxx[band].copy()
        total_power = float(np.sum(p_band))
        if total_power < self._cfg.epsilon:
            return float("nan")

        prob = p_band / total_power
        valid_prob = prob[prob > 0]
        if valid_prob.size == 0:
            return float("nan")

        entropy = -float(np.sum(valid_prob * np.log(valid_prob)))
        max_entropy = np.log(len(p_band)) if len(p_band) > 1 else 1.0
        normalized_entropy = safe_divide(entropy, float(max_entropy), epsilon=self._cfg.epsilon)
        return float(np.clip(normalized_entropy, 0.0, 1.0))

    def _in_band_power_ratio(self, pxx: np.ndarray, band: np.ndarray) -> float:
        """Tỷ lệ năng lượng dải tim mạch / tổng năng lượng toàn dải Nyquist."""
        band_power  = float(np.sum(pxx[band]))
        total_power = float(np.sum(pxx))
        ratio = safe_divide(band_power, total_power, epsilon=self._cfg.epsilon)
        return float(np.clip(ratio, 0.0, 1.0)) if not np.isnan(ratio) else float("nan")
