from dataclasses import dataclass
from enum import Enum


class RPPGAlgorithm(str, Enum):
    GREEN = "GREEN"
    CHROM = "CHROM"
    POS   = "POS"


@dataclass
class SignalConfig:
    """Tham số xử lý tín hiệu rPPG."""

    fps:                     float = 30.0
    window_sec:              float = 8.0    # Cửa sổ phân tích (giây)
    sub_window_sec:          float = 1.6    # Cửa sổ con cho POS / CHROM
    min_window_sec:          float = 3.0    # Tối thiểu để bắt đầu tính toán
    detrend_lambda:          float = 100.0  # Hệ số Tarvainen smoothness priors
    low_cutoff_hz:           float = 0.75   # 45 BPM — nhịp tim tối thiểu lúc nghỉ
    high_cutoff_hz:          float = 2.50   # 150 BPM — nhịp tim tối đa lúc ngồi tĩnh
    filter_order:            int   = 1      # Bậc Butterworth (1-2 tránh méo dạng sóng)
    artifact_threshold:      float = 3.5    # Ngưỡng phát hiện đột biến (n × std)
    time_gap_threshold_sec:  float = 0.5    # Ngưỡng phát hiện đứt đoạn thời gian (giây)


@dataclass
class ROIConfig:
    """Tỷ lệ vùng quan tâm (ROI) tính theo kích thước Face Bounding Box."""

    crop_forehead: bool = True
    crop_cheeks:   bool = True

    # ── Vùng Trán ─────────────────────────────────────────────────────────────
    forehead_x_offset:      float = 0.25  # Lùi vào 25% từ cạnh trái BBox
    forehead_y_offset:      float = 0.08  # Lùi xuống 8% từ đỉnh BBox
    forehead_width_ratio:   float = 0.50  # Rộng 50% BBox
    forehead_height_ratio:  float = 0.18  # Cao 18% BBox

    # ── Vùng Má Trái (theo góc nhìn ảnh — bên phải người dùng) ───────────────
    left_cheek_x_offset:    float = 0.15
    left_cheek_y_offset:    float = 0.50
    left_cheek_width_ratio: float = 0.25
    left_cheek_height_ratio: float = 0.20

    # ── Vùng Má Phải (theo góc nhìn ảnh — bên trái người dùng) ───────────────
    right_cheek_x_offset:    float = 0.60
    right_cheek_y_offset:    float = 0.50
    right_cheek_width_ratio: float = 0.25
    right_cheek_height_ratio: float = 0.20

    # ── Fallback: toàn bộ vùng trung tâm mặt khi không tách sub-ROI ──────────
    fallback_x_offset:      float = 0.20
    fallback_y_offset:      float = 0.20
    fallback_width_ratio:   float = 0.60
    fallback_height_ratio:  float = 0.60


@dataclass
class FaceDetectorConfig:
    """Tham số Face Detector và BBoxSmoother."""

    smoothing_alpha:      float = 0.65  # Hệ số EMA cho BBoxSmoother
    max_missing_frames:   int   = 10    # Số frame mất mặt tối đa trước khi reset smoother

    # Fallback BBox (trung tâm 50% khung hình) khi cascade không nhận diện được
    fallback_x_ratio:     float = 0.25
    fallback_y_ratio:     float = 0.20
    fallback_width_ratio: float = 0.50
    fallback_height_ratio: float = 0.50
