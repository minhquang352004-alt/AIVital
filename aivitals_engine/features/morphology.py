"""
aivitals_engine/features/morphology.py
======================================
Trích xuất đặc trưng hình thái học sóng xung (Group A).

Đặc trưng gồm:
    - mean_rise_time_ms:   Thời gian co tâm thu trung bình (ms)
    - mean_decay_time_ms:  Thời gian giãn tâm trương trung bình (ms)
    - std_rise_time_ms:    Độ lệch chuẩn thời gian co tâm thu (ms)
    - mean_systolic_ratio: Tỷ lệ T_s / (T_s + T_d)
    - mean_pw25_ms:        Độ rộng xung tại 25% chiều cao (ms)
    - mean_pw50_ms:        Độ rộng xung tại 50% chiều cao (ms)
    - mean_pw75_ms:        Độ rộng xung tại 75% chiều cao (ms)
    - mean_area_ratio:     Tỷ lệ diện tích A_s / A_d (tâm thu / tâm trương)
    - aix_proxy:           Augmentation Index proxy (đỉnh thứ cấp)
    - apg_aging_index:     (b - c - d - e) / a từ đạo hàm bậc 2 (APG)
"""
from __future__ import annotations

from typing import Any

import numpy as np
from scipy.signal import find_peaks

from aivitals_engine.features._base_extractor import PartialFeatureExtractor
from aivitals_engine.features._guards import nan_mean, safe_divide, safe_stat
from aivitals_engine.features.segmentation import SingleBeat

# Tương thích cả NumPy 1.x (np.trapz) và 2.x (np.trapezoid)
_trapz = getattr(np, "trapezoid", getattr(np, "trapz", None))


class MorphologyExtractor(PartialFeatureExtractor):
    """Trích xuất nhóm đặc trưng hình thái học (Group A)."""

    def extract(
        self,
        bvp: np.ndarray,
        fs: float,
        beats: list[SingleBeat],
    ) -> dict[str, Any]:
        """Trích xuất 10 đặc trưng hình thái học từ danh sách SingleBeat."""
        if len(beats) < self._cfg.min_valid_beats:
            return {}

        rise_times: list[float] = []
        decay_times: list[float] = []
        pw25_list: list[float] = []
        pw50_list: list[float] = []
        pw75_list: list[float] = []
        area_ratios: list[float] = []
        aix_proxies: list[float] = []
        aging_indices: list[float] = []

        for beat in beats:
            rise_times.append(beat.rise_time_ms)
            decay_times.append(beat.decay_time_ms)
            pw25_list.append(self._pulse_width(beat, 0.25))
            pw50_list.append(self._pulse_width(beat, 0.50))
            pw75_list.append(self._pulse_width(beat, 0.75))
            area_ratios.append(self._area_ratio(beat))
            aix_proxies.append(self._aix_proxy(beat))
            aging_indices.append(self._apg_aging_index(beat))

        rise = np.array(rise_times, dtype=np.float64)
        decay = np.array(decay_times, dtype=np.float64)
        total = rise + decay
        safe_total = np.where(total < self._cfg.epsilon, self._cfg.epsilon, total)
        systolic_ratios = rise / safe_total

        return {
            "mean_rise_time_ms":   safe_stat(rise, np.mean),
            "mean_decay_time_ms":  safe_stat(decay, np.mean),
            "std_rise_time_ms":    safe_stat(rise, np.std, min_len=2),
            "mean_systolic_ratio": safe_stat(systolic_ratios, np.mean),
            "mean_pw25_ms":        nan_mean(pw25_list),
            "mean_pw50_ms":        nan_mean(pw50_list),
            "mean_pw75_ms":        nan_mean(pw75_list),
            "mean_area_ratio":     nan_mean(area_ratios),
            "aix_proxy":           nan_mean(aix_proxies),
            "apg_aging_index":     nan_mean(aging_indices),
        }

    # ── Private calculation helpers ───────────────────────────────────────────

    def _pulse_width(self, beat: SingleBeat, level: float) -> float:
        """
        Tính độ rộng xung tại mức `level` ∈ (0, 1) chiều cao đỉnh.

        Đơn vị: mili giây (ms).
        """
        sig = beat.samples
        if sig.size < 3:
            return float("nan")
        max_val = np.nanmax(sig)
        threshold = level * max_val
        above = sig >= threshold
        if not np.any(above):
            return float("nan")
        indices = np.where(above)[0]
        width_samples = indices[-1] - indices[0]
        return float(width_samples / beat.fs * 1_000.0)

    def _area_ratio(self, beat: SingleBeat) -> float:
        """
        Tỷ lệ diện tích tâm thu / tâm trương (A_s / A_d).

        A_s: diện tích từ chân sóng (onset) đến đỉnh tâm thu.
        A_d: diện tích từ đỉnh tâm thu đến cuối chu kỳ.
        """
        local_peak = beat.peak_idx - beat.onset_idx
        if local_peak <= 0 or local_peak >= len(beat.samples) - 1:
            return float("nan")

        sig = beat.samples
        area_s = float(_trapz(sig[: local_peak + 1]))
        area_d = float(_trapz(sig[local_peak:]))
        return safe_divide(area_s, area_d, epsilon=self._cfg.epsilon)

    def _aix_proxy(self, beat: SingleBeat) -> float:
        """
        Augmentation Index proxy: (P2 - P1) / P1.

        P1: biên độ đỉnh tâm thu thứ nhất (systolic).
        P2: biên độ đỉnh tâm trương thứ hai (diastolic/reflected wave).
        Trả về NaN nếu không tìm thấy đỉnh thứ 2 rõ ràng.
        """
        local_peak = beat.peak_idx - beat.onset_idx
        if local_peak >= len(beat.samples) - 3:
            return float("nan")

        post_systolic = beat.samples[local_peak:]
        if post_systolic.size < 3:
            return float("nan")

        secondary_peaks, _ = find_peaks(
            post_systolic,
            prominence=self._cfg.aix_min_prominence,
        )
        if len(secondary_peaks) == 0:
            return float("nan")

        p1 = float(beat.samples[local_peak])
        p2 = float(post_systolic[secondary_peaks[0]])
        return safe_divide(p2 - p1, p1, epsilon=self._cfg.epsilon)

    def _apg_aging_index(self, beat: SingleBeat) -> float:
        """
        APG Aging Index: (b - c - d - e) / a từ đạo hàm bậc 2.

        a: sóng co cơ tâm thu ban đầu (đỉnh dương đầu tiên)
        b: sóng co cơ tâm thu muộn (đáy âm)
        c, d, e: các cực trị tiếp theo
        """
        apg = beat.apg
        if apg.size < 10:
            return float("nan")

        dx = np.diff(apg)
        extrema_indices = np.where((dx[:-1] * dx[1:]) < 0)[0] + 1

        if len(extrema_indices) < self._cfg.apg_min_extrema:
            return float("nan")

        a, b, c, d, e = [float(apg[extrema_indices[i]]) for i in range(5)]
        return safe_divide(b - c - d - e, a, epsilon=self._cfg.epsilon)
