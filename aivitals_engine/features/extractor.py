"""
aivitals_engine/features/extractor.py
======================================
BVPFeatureExtractor — Orchestrator (Facade) điều phối pipeline
trích xuất toàn bộ đặc trưng sinh lý từ sóng BVP 1D.

Thiết kế (SOLID):
    S – Chỉ điều phối luồng xử lý: phân đoạn nhịp → gọi các extractor → hợp nhất kết quả.
        Không chứa logic tính toán đặc trưng cụ thể.
    O – Mở rộng: Inject thêm PartialFeatureExtractor mới qua tham số `extractors`,
        không cần sửa mã nguồn class này.
    L – Mọi PartialFeatureExtractor đều tuân thủ hợp đồng chung (Base Class).
    I – Interface tối giản: `extract(bvp, fs) -> BVPFeatures`.
    D – Phụ thuộc vào interface PartialFeatureExtractor và BVPFeaturesConfig (DIP).

Cách dùng:
    >>> from aivitals_engine.features.extractor import BVPFeatureExtractor
    >>> extractor = BVPFeatureExtractor()
    >>> features = extractor.extract(bvp_signal, fs=30.0)
    >>> vector = features.to_numpy()    # (N_features,) float64 cho model ML của Khoa
    >>> data   = features.to_dict()     # Python dict cho API/log
    >>> json_s = features.to_json()     # JSON string chuẩn
"""
from __future__ import annotations

import logging
import time
from typing import Any, Mapping, Optional, Sequence

import numpy as np

from aivitals_engine.features._base_extractor import PartialFeatureExtractor
from aivitals_engine.features.amplitude import AmplitudeExtractor
from aivitals_engine.features.config import BVPFeaturesConfig
from aivitals_engine.features.guard import (
    FeatureGuardConfig,
    FeatureValidity,
    GuardedFeatures,
    check_signal,
)
from aivitals_engine.features.morphology import MorphologyExtractor
from aivitals_engine.features.schema import BVPFeatures
from aivitals_engine.features.segmentation import BeatSegmenter
from aivitals_engine.features.spectral import SpectralExtractor
from aivitals_engine.features.trend import TrendExtractor

_logger = logging.getLogger(__name__)

_DEFAULT_EXTRACTOR_CLASSES = (
    MorphologyExtractor,
    AmplitudeExtractor,
    SpectralExtractor,
    TrendExtractor,
)


class BVPFeatureExtractor:
    """
    Facade điều phối pipeline trích xuất đặc trưng sinh lý từ sóng BVP.

    Args:
        config:     Tham số cấu hình BVPFeaturesConfig (None → dùng mặc định).
        extractors: Danh sách PartialFeatureExtractor tùy biến (None → dùng 4 extractor mặc định).
    """

    def __init__(
        self,
        config: BVPFeaturesConfig | None = None,
        extractors: Sequence[PartialFeatureExtractor] | None = None,
    ) -> None:
        self._cfg: BVPFeaturesConfig = config or BVPFeaturesConfig()
        self._segmenter: BeatSegmenter = BeatSegmenter(self._cfg)
        self._extractors: list[PartialFeatureExtractor] = (
            [cls(self._cfg) for cls in _DEFAULT_EXTRACTOR_CLASSES]
            if extractors is None
            else list(extractors)
        )

    def extract(self, bvp: np.ndarray, fs: float = 30.0) -> BVPFeatures:
        """
        Trích xuất toàn bộ đặc trưng sinh lý từ mảng tín hiệu BVP 1D.

        Hàm an toàn: không raise exception khi tín hiệu ngắn, rỗng, phẳng,
        toàn NaN hoặc khi chia cho 0 (các field không tính được sẽ có giá trị NaN).

        Args:
            bvp: Mảng BVP 1D đã lọc sạch (float64).
            fs:  Tần số lấy mẫu thực tế của cửa sổ BVP (Hz).

        Returns:
            BVPFeatures — Data contract chứa toàn bộ đặc trưng.
        """
        t0 = time.perf_counter()
        sig = np.asarray(bvp, dtype=np.float64).flatten()

        # Phân đoạn các chu kỳ nhịp đơn lẻ
        beats = self._segmenter.segment(sig, fs)

        # Chạy từng extractor và gộp kết quả
        merged: dict = {}
        for ext in self._extractors:
            try:
                partial = ext.extract(sig, fs, beats)
                merged.update(partial)
            except Exception as e:
                _logger.warning("Lỗi trong extractor %s: %s", ext.__class__.__name__, e)

        # Gán metadata
        merged["valid_beat_count"]  = len(beats)
        merged["window_duration_s"] = float(sig.size / fs) if fs > 0 else 0.0
        merged["fs"]                = float(fs)

        elapsed_ms = (time.perf_counter() - t0) * 1_000.0
        if elapsed_ms > self._cfg.max_extraction_ms:
            _logger.debug(
                "BVPFeatureExtractor: %.2f ms > budget %.1f ms",
                elapsed_ms,
                self._cfg.max_extraction_ms,
            )

        return self._build_features(merged)

    def extract_checked(
        self,
        bvp: np.ndarray,
        fs: float = 30.0,
        *,
        sqi: Optional[float] = None,
        warnings: Optional[Sequence[str]] = None,
        artifact_ratio: Optional[float] = None,
        metadata: Optional[Mapping[str, Any]] = None,
        guard_config: Optional[FeatureGuardConfig] = None,
    ) -> GuardedFeatures:
        """
        Trích xuất đặc trưng CÓ cổng chất lượng (Tuần 7).

        Chỉ tạo `BVPFeatures` khi tín hiệu đạt guard (độ dài, fs, hữu hạn, SQI,
        cảnh báo BLOCK, artifact) và tìm đủ số nhịp hợp lệ. Nếu không đạt,
        ``features`` là None và ``reasons`` cho biết lý do.

        `extract()` giữ nguyên hành vi cũ (luôn trả BVPFeatures, field thiếu là NaN).

        Args:
            bvp, fs:        như `extract()`.
            sqi:            SQI của cửa sổ (None → bỏ qua kiểm tra).
            warnings:       Danh sách mã cảnh báo tín hiệu (FrameResult.warnings).
            artifact_ratio: Tỷ lệ frame bị loại trong buffer.
            metadata:       Thông tin truy vết thêm (method, version, ...) — được
                            sao chép vào `validity.metadata`.
            guard_config:   Ngưỡng tùy biến.
        """
        cfg = guard_config or FeatureGuardConfig()
        meta: dict = dict(metadata or {})
        meta.update({"fs": float(fs), "sqi": sqi, "artifact_ratio": artifact_ratio,
                     "signal_warnings": tuple(warnings or ())})

        reasons = list(check_signal(
            bvp, fs, sqi=sqi, warnings=warnings, artifact_ratio=artifact_ratio, config=cfg,
        ))
        if reasons:
            return GuardedFeatures(None, FeatureValidity(False, tuple(reasons), meta))

        features = self.extract(bvp, fs)
        meta["valid_beat_count"] = features.valid_beat_count
        if features.valid_beat_count < cfg.min_valid_beats:
            return GuardedFeatures(None, FeatureValidity(False, ("TOO_FEW_BEATS",), meta))
        return GuardedFeatures(features, FeatureValidity(True, (), meta))

    # ── Private builder ────────────────────────────────────────────────────────

    def _build_features(self, merged: dict) -> BVPFeatures:
        """Khởi tạo BVPFeatures đảm bảo tất cả field thiếu đều nhận NaN."""
        field_defaults = {
            f_name: float("nan")
            for f_name in BVPFeatures.feature_names()
        }
        field_defaults["valid_beat_count"]  = 0
        field_defaults["window_duration_s"] = 0.0
        field_defaults["fs"]                = 30.0

        # Ghi đè bằng các giá trị tính được
        field_defaults.update(merged)

        # Chỉ truyền các key hợp lệ trong schema
        schema_keys = set(BVPFeatures.__dataclass_fields__.keys())
        clean_kwargs = {k: v for k, v in field_defaults.items() if k in schema_keys}

        return BVPFeatures(**clean_kwargs)
