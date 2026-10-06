"""
aivitals_engine/features/schema.py
====================================
Data contract: BVPFeatures — Frozen dataclass chứa toàn bộ đặc trưng
sinh lý trích xuất từ sóng BVP, dùng để bàn giao cho BP / Health Model.

Thiết kế (SOLID):
    S – Pure Data Transfer Object, không chứa logic tính toán.
    I – Interface xuất dữ liệu (to_dict / to_numpy / to_json)
        tách rời nhau; consumer chỉ dùng những gì cần.

Quy tắc đặt tên field:
    Hậu tố `_ms`    → mili giây
    Hậu tố `_hz`    → Hertz
    Hậu tố `_ratio` → tỷ lệ không thứ nguyên [0, ∞)
    Không hậu tố    → đơn vị tự nhiên hoặc adimensional

Quan trọng về thứ tự field:
    Thứ tự field quyết định chiều vector `to_numpy()`.
    SAU KHI handoff Khoa, KHÔNG được chèn field vào giữa.
    Thêm feature mới → APPEND ở cuối + bump _FEATURE_VECTOR_VERSION.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from typing import ClassVar

import numpy as np

_FEATURE_VECTOR_VERSION: str = "1.0"

# Các field metadata không được đưa vào vector to_numpy()
_METADATA_FIELDS: frozenset[str] = frozenset({"valid_beat_count", "window_duration_s", "fs"})


@dataclass(frozen=True)
class BVPFeatures:
    """
    Data contract: Các đặc trưng sinh lý trích xuất từ sóng BVP.

    Giá trị ``float("nan")`` có nghĩa là không thể tính được
    (tín hiệu quá ngắn / không tìm được nhịp / chia cho 0).
    Consumer (Khoa) cần impute hoặc drop NaN trước khi train mô hình.
    """

    # ── Metadata (không đưa vào vector to_numpy) ──────────────────────────────
    valid_beat_count: int   = 0
    """Số chu kỳ nhịp tim hợp lệ tìm được trong cửa sổ BVP."""
    window_duration_s: float = 0.0
    """Độ dài cửa sổ BVP đã xử lý (giây)."""
    fs: float               = 30.0
    """Tần số lấy mẫu BVP (Hz)."""

    # ── Group A: Morphology — Hình thái học sóng xung ─────────────────────────
    mean_rise_time_ms: float   = float("nan")
    """T_s trung bình: Thời gian từ chân sóng (onset) tới đỉnh tâm thu (ms)."""
    mean_decay_time_ms: float  = float("nan")
    """T_d trung bình: Thời gian từ đỉnh tâm thu tới chân sóng kế tiếp (ms)."""
    std_rise_time_ms: float    = float("nan")
    """Độ lệch chuẩn của T_s giữa các nhịp — đo độ ổn định thời gian co cơ tim."""
    mean_systolic_ratio: float = float("nan")
    """Tỷ lệ T_s / (T_s + T_d) — chỉ số độ cứng thành mạch proxy."""
    mean_pw25_ms: float        = float("nan")
    """Độ rộng xung trung bình tại 25% chiều cao đỉnh (ms)."""
    mean_pw50_ms: float        = float("nan")
    """Độ rộng xung trung bình tại 50% chiều cao đỉnh — Pulse Width 50 (ms)."""
    mean_pw75_ms: float        = float("nan")
    """Độ rộng xung trung bình tại 75% chiều cao đỉnh (ms)."""
    mean_area_ratio: float     = float("nan")
    """Tỷ lệ diện tích A_s / A_d (tâm thu / tâm trương) — proxy co bóp tim."""
    aix_proxy: float           = float("nan")
    """Augmentation Index proxy: (P2 - P1) / P1 từ đỉnh tâm trương thứ cấp."""
    apg_aging_index: float     = float("nan")
    """APG Aging Index: (b - c - d - e) / a từ đạo hàm bậc 2 — chỉ số lão hóa mạch."""

    # ── Group B: Amplitude — Biên độ xung ─────────────────────────────────────
    mean_pulse_amplitude: float = float("nan")
    """Chiều cao đỉnh xung trung bình (đơn vị tùy biến BVP — a.u.)."""
    pulse_amp_cv: float         = float("nan")
    """Hệ số biến thiên biên độ: σ/μ — đo sự đều đặn của sóng mạch."""
    notch_relative_amp: float   = float("nan")
    """Biên độ khuyết dicrotic / biên độ đỉnh tâm thu — đo sóng phản xạ mạch."""

    # ── Group C: Spectral — Tần số & Phổ ──────────────────────────────────────
    fundamental_freq_hz: float  = float("nan")
    """f0: Tần số nhịp tim cơ bản trong dải [0.75–2.5 Hz] (Hz)."""
    harmonic_ratio_h2: float    = float("nan")
    """Tỷ số năng lượng hài bậc 2 / hài bậc 1: P(2f0) / P(f0)."""
    harmonic_ratio_h3: float    = float("nan")
    """Tỷ số năng lượng hài bậc 3 / hài bậc 1: P(3f0) / P(f0)."""
    spectral_entropy: float     = float("nan")
    """Shannon entropy chuẩn hóa của phổ trong dải tim mạch — đo độ hỗn loạn."""
    in_band_power_ratio: float  = float("nan")
    """Tỷ lệ năng lượng trong dải [0.75–2.5 Hz] / tổng công suất Nyquist."""

    # ── Group D: Trend / Dynamics — Xu hướng & Thống kê ──────────────────────
    baseline_drift_slope: float = float("nan")
    """Độ dốc trôi đường nền BVP (a.u./giây) — phát hiện nhiễu hô hấp dài hạn."""
    bvp_skewness: float         = float("nan")
    """Độ lệch (Skewness) của phân phối biên độ BVP trong cửa sổ."""
    bvp_kurtosis: float         = float("nan")
    """Độ nhọn (Kurtosis) của phân phối biên độ BVP trong cửa sổ."""
    ibi_std_ms: float           = float("nan")
    """Độ lệch chuẩn IBI giữa các nhịp (ms) — xấp xỉ SDNN proxy."""
    ibi_mean_ms: float          = float("nan")
    """Trung bình IBI giữa các nhịp (ms) — xấp xỉ Mean RR."""

    # ── Class-level helpers (không phải instance field) ───────────────────────

    @classmethod
    def feature_names(cls) -> list[str]:
        """
        Danh sách tên đặc trưng theo đúng thứ tự to_numpy().

        Dùng để Khoa build DataFrame:
            pd.DataFrame(vectors, columns=BVPFeatures.feature_names())
        """
        return [f.name for f in fields(cls) if f.name not in _METADATA_FIELDS]

    @classmethod
    def feature_dim(cls) -> int:
        """Số chiều vector cố định — bất biến theo _FEATURE_VECTOR_VERSION."""
        return len(cls.feature_names())

    # ── Export interfaces (ISP: mỗi method phục vụ 1 consumer) ───────────────

    def to_dict(self) -> dict:
        """
        Python dict với key rõ ràng.

        Dùng cho: API log, debug, pandas DataFrame.
        NaN giữ nguyên là float('nan').
        """
        return asdict(self)

    def to_numpy(self) -> np.ndarray:
        """
        Vector float64 phẳng — input cho Scikit-Learn / PyTorch của Khoa.

        Thứ tự feature KHỚP CHÍNH XÁC với feature_names().
        Metadata fields (valid_beat_count, window_duration_s, fs) bị loại.
        NaN được giữ nguyên — Khoa impute trước khi train.

        Returns:
            np.ndarray shape (feature_dim(),) dtype float64.
        """
        raw = asdict(self)
        return np.array(
            [raw[name] for name in self.feature_names()],
            dtype=np.float64,
        )

    def to_json(self, indent: int = 2) -> str:
        """
        JSON string hợp lệ — dùng cho WebSocket / API response.

        NaN Python → null JSON (RFC 8259 compliant).
        Thêm field ``_schema_version`` để consumer kiểm tra tính tương thích.
        """
        raw = asdict(self)
        sanitized = {
            k: (None if isinstance(v, float) and (v != v) else v)
            for k, v in raw.items()
        }
        sanitized["_schema_version"] = _FEATURE_VECTOR_VERSION
        return json.dumps(sanitized, indent=indent, ensure_ascii=False)
