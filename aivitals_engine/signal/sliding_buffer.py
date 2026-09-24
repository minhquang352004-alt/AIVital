"""
sliding_buffer.py
=================
Bộ đệm trượt (Sliding Window Buffer) cho luồng RGB realtime.

Trách nhiệm duy nhất của class này (SRP):
    1. Lưu trữ chuỗi [timestamp, RGB] trong cửa sổ thời gian trượt.
    2. Phát hiện và từ chối frame dị thường (Artifact Detection + Time Gap Guard).

Việc resample dữ liệu về FPS đều được ủy thác cho `resample.py`.

Vị trí trong pipeline:
    ROIExtractor → SlidingWindowBuffer → get_resampled_window() → rPPG Method
"""

import time
from collections import deque
from typing import Optional, Tuple

import numpy as np

from .resample import resample_to_fixed_fps
from aivitals_engine.config.settings import SignalConfig


class SlidingWindowBuffer:
    """
    Bộ đệm trượt RGB cho luồng camera realtime.

    Args:
        window_sec:         Độ dài cửa sổ tối đa (giây).
        target_fps:         FPS mục tiêu để ước tính kích thước deque.
        min_sec:            Thời gian dữ liệu tối thiểu để coi buffer là sẵn sàng.
        artifact_threshold: Ngưỡng phát hiện đột biến (n × std). None để tắt.
        time_gap_threshold: Khoảng cách thời gian tối đa giữa 2 frame (giây).
                            Vượt ngưỡng → reset buffer tránh nội suy rác.
    """

    def __init__(
        self,
        window_sec:         float          = SignalConfig().window_sec,
        target_fps:         float          = SignalConfig().fps,
        min_sec:            float          = SignalConfig().min_window_sec,
        artifact_threshold: Optional[float] = SignalConfig().artifact_threshold,
        time_gap_threshold: float          = SignalConfig().time_gap_threshold_sec,
        # Kept for backward compatibility but unused (resampling is done externally)
        lowcut:             float          = SignalConfig().low_cutoff_hz,
        highcut:            float          = SignalConfig().high_cutoff_hz,
        bandpass_order:     int            = SignalConfig().filter_order,
        detrend_lambda:     float          = SignalConfig().detrend_lambda,
    ) -> None:
        self.window_sec         = float(window_sec)
        self.target_fps         = float(target_fps)
        self.min_sec            = float(min_sec)
        self.artifact_threshold = artifact_threshold
        self.time_gap_threshold = float(time_gap_threshold)

        max_frames = int(np.ceil(self.window_sec * self.target_fps))
        self._rgb_buffer:  deque = deque(maxlen=max_frames)
        self._timestamps:  deque = deque(maxlen=max_frames)
        self._artifact_count: int = 0

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

    def push(self, rgb: np.ndarray, timestamp: Optional[float] = None) -> bool:
        """
        Đẩy 1 frame RGB vào buffer.

        Args:
            rgb:       Vector [R, G, B] trung bình của ROI, shape (3,).
            timestamp: Thời điểm thực tế của frame (giây). None → perf_counter().

        Returns:
            True nếu frame được chấp nhận, False nếu bị loại do artifact.
        """
        rgb_arr = self._validate_rgb(rgb)
        ts = float(timestamp) if timestamp is not None else time.perf_counter()

        if self._is_time_gap(ts):
            self.reset()

        if self._is_artifact(rgb_arr):
            self._artifact_count += 1
            return False

        self._rgb_buffer.append(rgb_arr)
        self._timestamps.append(ts)
        return True

    def is_ready(self) -> bool:
        """True khi buffer đã tích lũy đủ `min_sec` giây dữ liệu."""
        if len(self._timestamps) < 2:
            return False
        return (self._timestamps[-1] - self._timestamps[0]) >= self.min_sec

    def get_fps(self) -> float:
        """FPS thực tế ước tính từ timestamp buffer (median để kháng outlier)."""
        if len(self._timestamps) < 2:
            return self.target_fps

        intervals = np.diff(np.array(self._timestamps))
        valid = intervals[intervals > 0]
        if len(valid) == 0:
            return self.target_fps

        mean_interval = float(np.median(valid))
        return float(np.clip(1.0 / mean_interval, 5.0, 120.0))

    def get_progress(self) -> float:
        """Tiến độ nạp đầy buffer so với window_sec [0.0 → 1.0]."""
        if len(self._timestamps) < 2:
            return 0.0
        duration = self._timestamps[-1] - self._timestamps[0]
        return float(np.clip(duration / self.window_sec, 0.0, 1.0))

    def get_raw_window(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Lấy cửa sổ RGB thô và timestamps (chưa qua xử lý).

        Returns:
            (rgb_raw shape (N,3), timestamps shape (N,))
        """
        return (
            np.array(self._rgb_buffer, dtype=np.float64),
            np.array(self._timestamps, dtype=np.float64),
        )

    def get_resampled_window(self) -> Tuple[np.ndarray, float]:
        """
        Lấy cửa sổ RGB đã nội suy về FPS cố định, **giữ nguyên thành phần DC**.

        DC (cường độ sáng nền) phải được bảo toàn để các thuật toán POS / CHROM
        có thể chuẩn hóa màu da: Cn = C(t) / μ_C.

        Returns:
            (rgb_resampled shape (M,3), effective_fps)

        Raises:
            RuntimeError: Nếu buffer chưa đủ dữ liệu.
        """
        if not self.is_ready():
            raise RuntimeError(
                "Buffer chưa đủ dữ liệu. Kiểm tra is_ready() trước khi gọi."
            )
        rgb_raw, timestamps = self.get_raw_window()
        effective_fps = self.get_fps()
        rgb_resampled = resample_to_fixed_fps(
            timestamps=timestamps,
            data=rgb_raw,
            target_fps=effective_fps,
        )
        return rgb_resampled, effective_fps

    def reset(self) -> None:
        """Xóa toàn bộ buffer và bộ đếm artifact."""
        self._rgb_buffer.clear()
        self._timestamps.clear()
        self._artifact_count = 0

    @property
    def size(self) -> int:
        """Số frame hiện có trong buffer."""
        return len(self._rgb_buffer)

    @property
    def artifact_count(self) -> int:
        """Số frame đã bị loại bỏ do artifact detection."""
        return self._artifact_count

    # ──────────────────────────────────────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _validate_rgb(rgb: np.ndarray) -> np.ndarray:
        arr = np.asarray(rgb, dtype=np.float64).flatten()
        if arr.shape[0] != 3:
            raise ValueError(
                f"RGB không hợp lệ: shape {arr.shape}. Cần (3,)."
            )
        return arr

    def _is_time_gap(self, ts: float) -> bool:
        """True nếu khoảng cách thời gian với frame trước vượt ngưỡng."""
        if len(self._timestamps) == 0:
            return False
        return (ts - self._timestamps[-1]) > self.time_gap_threshold

    def _is_artifact(self, rgb_new: np.ndarray) -> bool:
        """
        Phát hiện frame đột biến bằng kiểm định 3-Sigma trên từng kênh RGB.

        Một frame bị coi là artifact nếu ≥ 2/3 kênh lệch quá `artifact_threshold × std`
        so với phân bố buffer hiện tại.

        Lý do dùng ngưỡng 2/3 thay vì bất kỳ kênh nào:
        - Ánh sáng thay đổi đột ngột ảnh hưởng cả 3 kênh cùng lúc.
        - Bắt được: đèn chớp, bóng đổ, quay đầu nhanh.
        - Tránh false positive khi chỉ 1 kênh dao động nhẹ.
        """
        if self.artifact_threshold is None or len(self._rgb_buffer) < 10:
            return False

        buf = np.array(self._rgb_buffer, dtype=np.float64)
        mean = np.mean(buf, axis=0)
        std  = np.where(np.std(buf, axis=0) < 1e-6, 1e-6, np.std(buf, axis=0))

        n_outlier_channels = int(np.sum(np.abs(rgb_new - mean) / std > self.artifact_threshold))
        return n_outlier_channels >= 2
