"""
aivitals_engine/features/trend.py
=================================
Trích xuất đặc trưng xu hướng và thống kê động của BVP (Group D).

Đặc trưng gồm:
    - baseline_drift_slope: Độ dốc trôi đường nền BVP (a.u./giây)
    - bvp_skewness:         Độ lệch (Skewness) phân phối biên độ BVP
    - bvp_kurtosis:         Độ nhọn (Kurtosis) phân phối biên độ BVP
    - ibi_std_ms:           Độ lệch chuẩn chuỗi IBI (ms) — xấp xỉ SDNN
    - ibi_mean_ms:          Trung bình chuỗi IBI (ms) — xấp xỉ Mean RR
"""
from __future__ import annotations

from typing import Any

import numpy as np

from aivitals_engine.features._base_extractor import PartialFeatureExtractor
from aivitals_engine.features._guards import safe_stat
from aivitals_engine.features.segmentation import SingleBeat


class TrendExtractor(PartialFeatureExtractor):
    """Trích xuất nhóm đặc trưng xu hướng và thống kê động (Group D)."""

    def extract(
        self,
        bvp: np.ndarray,
        fs: float,
        beats: list[SingleBeat],
    ) -> dict[str, Any]:
        """Trích xuất 5 đặc trưng xu hướng và IBI từ tín hiệu BVP."""
        sig = np.asarray(bvp, dtype=np.float64).flatten()
        if sig.size < 2:
            return {}

        n = sig.size
        sig_std = float(np.std(sig))
        if sig_std < self._cfg.epsilon:
            slope = 0.0
            sk = 0.0
            kt = 0.0
        else:
            t_dev = (np.arange(n, dtype=np.float64) - (n - 1) / 2.0) / fs
            denom = float(np.sum(t_dev ** 2))
            diff = sig - np.mean(sig)
            slope = float(np.sum(t_dev * diff) / denom) if denom > self._cfg.epsilon else float("nan")
            m2 = float(np.mean(diff ** 2))
            m3 = float(np.mean(diff ** 3))
            m4 = float(np.mean(diff ** 4))
            sk = float(m3 / (m2 ** 1.5)) if m2 > self._cfg.epsilon else float("nan")
            kt = float(m4 / (m2 ** 2) - 3.0) if m2 > self._cfg.epsilon else float("nan")

        # Thống kê IBI từ danh sách chu kỳ nhịp đã phân đoạn
        if len(beats) >= 2:
            ibis = np.array([b.duration_ms for b in beats], dtype=np.float64)
            ibi_std  = safe_stat(ibis, np.std, min_len=2)
            ibi_mean = safe_stat(ibis, np.mean, min_len=1)
        else:
            ibi_std  = float("nan")
            ibi_mean = float("nan")

        return {
            "baseline_drift_slope": slope,
            "bvp_skewness":         sk,
            "bvp_kurtosis":         kt,
            "ibi_std_ms":           ibi_std,
            "ibi_mean_ms":          ibi_mean,
        }
