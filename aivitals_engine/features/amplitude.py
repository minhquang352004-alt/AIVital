"""
aivitals_engine/features/amplitude.py
=====================================
Trích xuất đặc trưng biên độ xung BVP (Group B).

Đặc trưng gồm:
    - mean_pulse_amplitude: Chiều cao xung trung bình (đơn vị BVP thô)
    - pulse_amp_cv:         Hệ số biến thiên biên độ σ/μ
    - notch_relative_amp:   Biên độ khuyết dicrotic tương đối so với đỉnh
"""
from __future__ import annotations

from typing import Any

import numpy as np
from scipy.signal import find_peaks

from aivitals_engine.features._base_extractor import PartialFeatureExtractor
from aivitals_engine.features._guards import nan_mean, safe_divide, safe_stat
from aivitals_engine.features.segmentation import SingleBeat


class AmplitudeExtractor(PartialFeatureExtractor):
    """Trích xuất nhóm đặc trưng biên độ xung (Group B)."""

    def extract(
        self,
        bvp: np.ndarray,
        fs: float,
        beats: list[SingleBeat],
    ) -> dict[str, Any]:
        """Trích xuất 3 đặc trưng biên độ từ danh sách SingleBeat."""
        if not beats:
            return {}

        amplitudes = np.array(
            [b.raw_peak_amplitude - b.raw_onset_amplitude for b in beats],
            dtype=np.float64,
        )

        mean_amp = safe_stat(amplitudes, np.mean)
        std_amp  = safe_stat(amplitudes, np.std, min_len=2)
        cv       = safe_divide(std_amp, mean_amp, epsilon=self._cfg.epsilon)

        notch_rel_amps = [self._notch_relative_amplitude(b) for b in beats]

        return {
            "mean_pulse_amplitude": mean_amp,
            "pulse_amp_cv":         cv,
            "notch_relative_amp":   nan_mean(notch_rel_amps),
        }

    # ── Private helper ────────────────────────────────────────────────────────

    def _notch_relative_amplitude(self, beat: SingleBeat) -> float:
        """
        Độ cao tương đối của khuyết dicrotic so với đỉnh tâm thu.

        Tìm điểm cực tiểu (trough) đầu tiên nằm sau đỉnh tâm thu.
        """
        local_peak = beat.peak_idx - beat.onset_idx
        if local_peak >= len(beat.samples) - 3:
            return float("nan")

        post_systolic = beat.samples[local_peak:]
        if post_systolic.size < 3:
            return float("nan")

        # Khuyết dicrotic là cực tiểu cục bộ → cực đại của -post_systolic
        troughs, _ = find_peaks(
            -post_systolic,
            prominence=self._cfg.notch_min_prominence,
        )
        if len(troughs) == 0:
            return float("nan")

        notch_val = float(post_systolic[troughs[0]])
        peak_val  = float(beat.samples[local_peak])
        return safe_divide(notch_val, peak_val, epsilon=self._cfg.epsilon)
