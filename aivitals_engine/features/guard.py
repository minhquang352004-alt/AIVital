"""
aivitals_engine/features/guard.py
=================================
Cổng chất lượng (guard) cho việc trích xuất đặc trưng BVP (Tuần 7).

Mục đích: đảm bảo vector đặc trưng bàn giao cho Health Model chỉ được tạo ra từ
tín hiệu đủ tốt, và luôn kèm metadata để truy vết (SQI, method, version, fs,
số artifact, cảnh báo môi trường).

Module này KHÔNG thay đổi `BVPFeatures` (data contract đã bàn giao cho Khoa) và
không thay đổi `BVPFeatureExtractor.extract()`. Người dùng muốn có guard gọi
`BVPFeatureExtractor.extract_checked()`.

Lý do từ chối (``reasons``) — chuỗi ổn định, có thể dùng để log / thống kê:
    SIGNAL_TOO_SHORT   cửa sổ ngắn hơn `min_window_sec`
    SIGNAL_DEGENERATE  tín hiệu phẳng / toàn NaN
    NON_FINITE_SAMPLES tỷ lệ mẫu NaN/inf vượt `max_nonfinite_ratio`
    LOW_FS             tần số lấy mẫu thấp hơn `min_fs_hz`
    LOW_SQI            SQI thấp hơn `min_sqi`
    BLOCKING_WARNING   có cảnh báo tín hiệu mức BLOCK (vd. MOTION_HIGH)
    HIGH_ARTIFACT      số frame bị loại / tổng frame vượt `max_artifact_ratio`
    TOO_FEW_BEATS      số nhịp hợp lệ tìm được dưới `min_valid_beats`
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence

import numpy as np

from aivitals_engine.features._guards import is_degenerate
from aivitals_engine.features.schema import BVPFeatures
from aivitals_engine.quality.signal_warnings import has_blocking


@dataclass(frozen=True)
class FeatureGuardConfig:
    """Ngưỡng của guard. Mặc định dựa trên ngưỡng hiện có trong pipeline (SQI 0.4)."""
    min_window_sec:       float = 4.0
    min_fs_hz:            float = 15.0
    min_sqi:              float = 0.40
    max_nonfinite_ratio:  float = 0.0     # BVP đã lọc không được chứa NaN/inf
    max_artifact_ratio:   float = 0.25    # trùng ngưỡng HIGH_ARTIFACT của QualityGate
    min_valid_beats:      int   = 3
    epsilon:              float = 1e-9


@dataclass(frozen=True)
class FeatureValidity:
    """Kết luận của guard + metadata truy vết."""
    valid:   bool
    reasons: tuple = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GuardedFeatures:
    """
    Kết quả `extract_checked()`.

    ``features`` là None nếu tín hiệu không đạt (valid=False). Khi đó **không** có
    vector nào được tạo, tránh đưa số liệu rác vào mô hình.
    """
    features: Optional[BVPFeatures]
    validity: FeatureValidity

    @property
    def valid(self) -> bool:
        return self.validity.valid

    @property
    def reasons(self) -> tuple:
        return self.validity.reasons


def check_signal(
    bvp: np.ndarray,
    fs: float,
    *,
    sqi: Optional[float] = None,
    warnings: Optional[Sequence[str]] = None,
    artifact_ratio: Optional[float] = None,
    config: Optional[FeatureGuardConfig] = None,
) -> tuple:
    """
    Kiểm tra tín hiệu TRƯỚC khi trích xuất đặc trưng.

    Returns:
        tuple các mã lý do (rỗng nếu đạt).
    """
    cfg = config or FeatureGuardConfig()
    sig = np.asarray(bvp, dtype=np.float64).flatten()
    reasons: list = []

    if not np.isfinite(fs) or fs < cfg.min_fs_hz:
        reasons.append("LOW_FS")

    duration = (sig.size / fs) if (np.isfinite(fs) and fs > 0) else 0.0
    if duration < cfg.min_window_sec:
        reasons.append("SIGNAL_TOO_SHORT")

    if sig.size > 0:
        nonfinite_ratio = float(np.mean(~np.isfinite(sig)))
        if nonfinite_ratio > cfg.max_nonfinite_ratio:
            reasons.append("NON_FINITE_SAMPLES")
    if sig.size == 0 or is_degenerate(sig, min_samples=1, epsilon=cfg.epsilon):
        reasons.append("SIGNAL_DEGENERATE")

    if sqi is not None and sqi < cfg.min_sqi:
        reasons.append("LOW_SQI")
    if warnings and has_blocking(warnings):
        reasons.append("BLOCKING_WARNING")
    if artifact_ratio is not None and artifact_ratio > cfg.max_artifact_ratio:
        reasons.append("HIGH_ARTIFACT")

    return tuple(dict.fromkeys(reasons))
