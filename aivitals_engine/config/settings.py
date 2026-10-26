from dataclasses import dataclass
from enum import Enum
from typing import Optional


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

    # ── Edge Cases & Robustness (Tuần 7) ──────────────────────────────────────
    max_consecutive_artifacts: int   = 10     # Ngưỡng tự hồi phục khi ánh sáng đổi bước nhảy
    max_face_lost_sec:         float = 1.0    # Dung nạp mất mặt tạm thời (micro-dropout)
    min_luma_acceptable:       float = 40.0   # Ngưỡng tối thiểu ánh sáng môi trường
    max_luma_acceptable:       float = 225.0  # Ngưỡng tối đa chống cháy sáng / lóa đèn
    min_face_ratio:            float = 0.12   # Tỷ lệ chiều rộng khuôn mặt tối thiểu so với khung hình
    luma_smooth_frames:        int   = 7      # Số frame làm mượt (median) luma để tránh cảnh báo nhấp nháy
    light_window_sec:          float = 2.0    # Cửa sổ đánh giá độ ổn định ánh sáng (giây)
    light_unstable_cv:         float = 0.10   # Hệ số biến thiên luma (std/mean) vượt mức này → LIGHT_UNSTABLE
    motion_window_sec:         float = 1.0    # Cửa sổ đo biên độ chuyển động mặt (giây)
    motion_amp_threshold:      float = 0.12   # Biên độ dịch chuyển tâm mặt / bề rộng mặt vượt mức này → MOTION_HIGH
    bbox_jump_ratio:           float = 0.60   # Tâm mặt nhảy giữa 2 frame > ratio × bề rộng mặt → coi là đứt ROI
    min_fps_acceptable:        float = 20.0   # FPS thực tế tối thiểu (khuyến nghị trong ENGINE_BENCHMARK)
    min_frames_for_fps_check:  int   = 15     # Số frame tối thiểu trong buffer trước khi đánh giá LOW_FPS

    # ── SQI & Quality Gate (Tuần 4) ───────────────────────────────────────────
    periodicity_min_bpm:     float = 45.0   # Tần số nhịp tim tối thiểu để xét lag ACF (BPM)
    periodicity_max_bpm:     float = 150.0  # Tần số nhịp tim tối đa để xét lag ACF (BPM)
    periodicity_threshold:   float = 0.46   # UNCALIBRATED, chưa hiệu chỉnh trên dữ liệu thật (chặn dưới p99 FPR trên nhiễu trắng cửa sổ 8s)


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

    # ── Lọc màu da người (Skin Pixel Filter - Level 1) ───────────────────────
    enable_skin_filter:     bool  = True   # Bật lọc màu da YCrCb để loại bỏ tóc, râu, kính
    skin_cr_min:            int   = 133    # Ngưỡng dưới Cr
    skin_cr_max:            int   = 173    # Ngưỡng trên Cr
    skin_cb_min:            int   = 77     # Ngưỡng dưới Cb
    skin_cb_max:            int   = 127    # Ngưỡng trên Cb
    skin_y_min:             int   = 20     # Loại bỏ bóng quá tối và sợi tóc đen
    skin_y_max:             int   = 240    # Loại bỏ điểm lóa sáng
    min_skin_ratio:         float = 0.10   # Tỷ lệ pixel da tối thiểu để áp dụng lọc


@dataclass
class FaceDetectorConfig:
    """Tham số Face Detector và BBoxSmoother."""

    detector_backend:     str           = "mediapipe"  # "mediapipe" hoặc "cascade"
    mediapipe_model_path: Optional[str] = None         # Đường dẫn tới face_landmarker.task (None -> dùng mặc định)

    smoothing_alpha:      float = 0.65  # Hệ số EMA cho BBoxSmoother
    max_missing_frames:   int   = 10    # Số frame mất mặt tối đa trước khi reset smoother

    # Fallback BBox (trung tâm 50% khung hình) khi detector không nhận diện được
    fallback_x_ratio:     float = 0.25
    fallback_y_ratio:     float = 0.20
    fallback_width_ratio: float = 0.50
    fallback_height_ratio: float = 0.50

