"""
aivitals_engine/features/config.py
===================================
Cấu hình bất biến cho BVP Feature Extraction Pipeline.

Thiết kế (SOLID):
    S – Chỉ chứa tham số, không có logic tính toán.
    O – frozen=True → immutable, an toàn multithreading.
    D – Các extractor nhận BVPFeaturesConfig qua constructor,
        không hard-code hằng số bên trong.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class BVPFeaturesConfig:
    """Tham số cấu hình cho toàn bộ BVP Feature Pipeline."""

    # ── Beat detection ─────────────────────────────────────────────────────────
    min_bpm: float = 45.0
    """Nhịp tim tối thiểu sinh lý (BPM) — loại nhịp chậm bất thường."""
    max_bpm: float = 150.0
    """Nhịp tim tối đa khi ngồi tĩnh (BPM) — loại nhịp nhanh quá."""
    min_beat_prominence: float = 0.15
    """Đỉnh xung cần nổi bật ít nhất 15% dải biên độ tín hiệu."""
    gaussian_sigma_factor: float = 500.0
    """sigma = N / gaussian_sigma_factor — kiểm soát độ làm mịn khi tìm đỉnh."""

    # ── Pulse width levels ─────────────────────────────────────────────────────
    pw_levels: tuple = (0.25, 0.50, 0.75)
    """Các mức đo độ rộng xung: tại 25%, 50%, 75% chiều cao đỉnh."""

    # ── Spectral ───────────────────────────────────────────────────────────────
    fundamental_freq_low_hz: float = 0.75
    """Giới hạn dưới dải tim mạch (Hz) — tương đương 45 BPM."""
    fundamental_freq_high_hz: float = 2.50
    """Giới hạn trên dải tim mạch (Hz) — tương đương 150 BPM."""
    harmonic_snr_tolerance_hz: float = 0.10
    """Dung sai ±Hz khi lấy năng lượng quanh các hài."""
    spectral_nfft_min: int = 512
    """Kích thước FFT tối thiểu (để đảm bảo đủ độ phân giải tần số)."""

    # ── Safety / Epsilon guard ─────────────────────────────────────────────────
    epsilon: float = 1e-9
    """Hằng số an toàn ngăn chia cho 0 trong mọi phép tính."""
    min_valid_beats: int = 2
    """Cần tối thiểu N nhịp hợp lệ mới tính đặc trưng hình thái học."""
    min_signal_samples: int = 16
    """Cần tối thiểu N mẫu mới tính đặc trưng phổ."""

    # ── APG Aging Index ────────────────────────────────────────────────────────
    apg_min_extrema: int = 5
    """Số cực trị tối thiểu cần tìm được trên APG để tính Aging Index."""

    # ── AIx secondary peak ─────────────────────────────────────────────────────
    aix_min_prominence: float = 0.02
    """Độ nổi bật tối thiểu của đỉnh thứ cấp (diastolic) để tính AIx."""
    notch_min_prominence: float = 0.02
    """Độ nổi bật tối thiểu của khuyết dicrotic để ghi nhận."""

    # ── Performance ────────────────────────────────────────────────────────────
    max_extraction_ms: float = 3.0
    """Ngưỡng cảnh báo latency (ms) — log WARNING nếu vượt."""
