"""
aivitals_engine/features/segmentation.py
==========================================
Beat Segmentation — Tách sóng BVP 1D thành danh sách các chu kỳ nhịp đơn lẻ.

Thiết kế (SOLID):
    S – BeatSegmenter chỉ chịu trách nhiệm xác định ranh giới nhịp.
        Không tính bất kỳ đặc trưng nào.
    O – Mở rộng bằng subclass; không sửa class này để thêm loại nhịp mới.
    L – SingleBeat là frozen dataclass — contract không thể bị override phá vỡ.
    D – Nhận BVPFeaturesConfig qua constructor, không hard-code hằng số.

Pipeline nội bộ:
    bvp_1d
      → smooth (gaussian)
      → find_peaks (systolic)
      → find_onsets (valleys giữa đỉnh)
      → filter_by_physiology (IBI trong [min_bpm, max_bpm])
      → normalize_each_beat (min-max → [0, 1])
      → List[SingleBeat]
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property

import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks

from aivitals_engine.features.config import BVPFeaturesConfig
from aivitals_engine.features._guards import is_degenerate


# ── Value object: một chu kỳ nhịp đơn lẻ ──────────────────────────────────────

@dataclass(frozen=True)
class SingleBeat:
    """
    Một chu kỳ nhịp tim đơn lẻ đã phân đoạn và chuẩn hóa.

    ``samples``: Đoạn BVP chuẩn hóa về [0, 1].
    Các index (onset_idx, peak_idx, end_idx) là vị trí tuyệt đối trong tín hiệu gốc.
    """
    samples: np.ndarray
    """Mảng BVP 1D đã chuẩn hóa [0, 1] của chu kỳ này."""
    onset_idx: int
    """Vị trí chân sóng (foot/valley) trong tín hiệu gốc."""
    peak_idx: int
    """Vị trí đỉnh tâm thu trong tín hiệu gốc."""
    end_idx: int
    """Vị trí cuối chu kỳ (= onset của nhịp kế tiếp) trong tín hiệu gốc."""
    fs: float
    """Tần số lấy mẫu (Hz)."""
    raw_peak_amplitude: float
    """Biên độ đỉnh tâm thu thô (chưa chuẩn hóa, đơn vị BVP gốc)."""
    raw_onset_amplitude: float
    """Biên độ chân sóng thô (chưa chuẩn hóa, đơn vị BVP gốc)."""

    # ── Derived timing properties ──────────────────────────────────────────────

    @property
    def duration_ms(self) -> float:
        """Tổng thời gian chu kỳ nhịp (ms) = IBI."""
        return (self.end_idx - self.onset_idx) / self.fs * 1_000.0

    @property
    def rise_time_ms(self) -> float:
        """T_s: Thời gian co tâm thu onset → systolic peak (ms)."""
        return (self.peak_idx - self.onset_idx) / self.fs * 1_000.0

    @property
    def decay_time_ms(self) -> float:
        """T_d: Thời gian giãn tâm trương systolic peak → end (ms)."""
        return (self.end_idx - self.peak_idx) / self.fs * 1_000.0

    # ── Derivative signals ─────────────────────────────────────────────────────

    @cached_property
    def vpg(self) -> np.ndarray:
        """
        Velocity Plethysmogram — đạo hàm bậc 1 của samples.

        Dùng để xác định các điểm gấp khúc chính xác hơn trên sóng xung.
        """
        return np.gradient(self.samples.astype(np.float64))

    @cached_property
    def apg(self) -> np.ndarray:
        """
        Acceleration Plethysmogram — đạo hàm bậc 2 của samples.

        Các cực trị a,b,c,d,e của APG được dùng tính APG Aging Index.
        """
        return np.gradient(self.vpg)


# ── Beat Segmenter ─────────────────────────────────────────────────────────────

class BeatSegmenter:
    """
    Phân đoạn sóng BVP 1D thành danh sách SingleBeat.

    Thuật toán:
        1. Làm mịn nhẹ BVP (Gaussian) để triệt tiêu đỉnh giả do nhiễu.
        2. Tìm đỉnh tâm thu bằng scipy find_peaks với min_distance ~ max_bpm
           và min_prominence tỷ lệ theo biên độ tín hiệu.
        3. Tìm chân sóng (onsets): cực tiểu giữa mỗi cặp đỉnh liên tiếp.
        4. Lọc nhịp theo sinh lý: IBI phải nằm trong [min_bpm, max_bpm].
        5. Chuẩn hóa min-max từng đoạn về [0, 1].
    """

    def __init__(self, config: BVPFeaturesConfig | None = None) -> None:
        self._cfg = config or BVPFeaturesConfig()

    def segment(self, bvp: np.ndarray, fs: float) -> list[SingleBeat]:
        """
        Phân đoạn tín hiệu BVP thành danh sách chu kỳ nhịp.

        Args:
            bvp: Mảng BVP 1D đã lọc sạch (float64).
            fs:  Tần số lấy mẫu (Hz).

        Returns:
            List[SingleBeat] hợp lệ. Rỗng nếu không tìm được nhịp hợp lệ.
        """
        sig = self._sanitize(bvp)
        if sig is None:
            return []

        smoothed = self._smooth(sig)
        peaks = self._find_peaks(smoothed, fs)
        if len(peaks) < 2:
            return []

        onsets = self._find_onsets(smoothed, peaks)
        return self._build_beats(sig, onsets, peaks, fs)

    # ── Private helpers ────────────────────────────────────────────────────────

    def _sanitize(self, bvp: np.ndarray) -> np.ndarray | None:
        """Chuyển về float64, kiểm tra điều kiện tối thiểu. Trả None nếu degenerate."""
        sig = np.asarray(bvp, dtype=np.float64).flatten()
        # NaN/Inf → 0 để tránh crash downstream; nếu toàn NaN/Inf → degenerate
        finite_mask = np.isfinite(sig)
        if not finite_mask.any():
            return None
        sig = np.where(finite_mask, sig, 0.0)
        min_len = int(fs_proxy := max(1.0, sig.size)) * 0  # dummy
        min_len = int(60.0 / self._cfg.max_bpm * 2)  # 2 nhịp tối thiểu tính bằng sample
        # Không biết fs ở đây, tạm dùng: cần ít nhất 2 chu kỳ theo max_bpm
        # fs sẽ được dùng trong segment(), tuy nhiên min samples rough check:
        if is_degenerate(sig, min_samples=10, epsilon=self._cfg.epsilon):
            return None
        return sig

    def _smooth(self, sig: np.ndarray) -> np.ndarray:
        """Gaussian smoothing nhẹ; sigma tỷ lệ với độ dài tín hiệu."""
        sigma = max(0.5, sig.size / self._cfg.gaussian_sigma_factor)
        return gaussian_filter1d(sig, sigma=sigma)

    def _find_peaks(self, sig: np.ndarray, fs: float) -> np.ndarray:
        """Tìm đỉnh tâm thu với ràng buộc sinh lý về khoảng cách và độ nổi bật."""
        min_distance = max(1, int(fs * 60.0 / self._cfg.max_bpm))
        sig_range = sig.max() - sig.min()
        min_prom = self._cfg.min_beat_prominence * sig_range if sig_range > self._cfg.epsilon else 0.0
        peaks, _ = find_peaks(sig, distance=min_distance, prominence=min_prom)
        return peaks

    def _find_onsets(self, sig: np.ndarray, peaks: np.ndarray) -> np.ndarray:
        """
        Tìm chân sóng: cực tiểu giữa mỗi cặp đỉnh liên tiếp.

        Onset đầu tiên: cực tiểu trong [0, peaks[0]].
        Onset giữa hai đỉnh i, i+1: cực tiểu trong [peaks[i], peaks[i+1]].
        """
        onsets: list[int] = []

        # Onset trước đỉnh đầu tiên
        pre_segment = sig[: peaks[0] + 1]
        onsets.append(int(np.argmin(pre_segment)))

        # Onsets giữa các cặp đỉnh liên tiếp
        for i in range(len(peaks) - 1):
            segment = sig[peaks[i] : peaks[i + 1] + 1]
            onsets.append(peaks[i] + int(np.argmin(segment)))

        return np.array(onsets, dtype=np.intp)

    def _build_beats(
        self,
        raw: np.ndarray,
        onsets: np.ndarray,
        peaks: np.ndarray,
        fs: float,
    ) -> list[SingleBeat]:
        """
        Lắp ráp từng SingleBeat, lọc nhịp bất sinh lý và chuẩn hóa.
        """
        cfg = self._cfg
        min_ibi_s = 60.0 / cfg.max_bpm
        max_ibi_s = 60.0 / cfg.min_bpm
        beats: list[SingleBeat] = []

        for i, (onset, peak) in enumerate(zip(onsets, peaks)):
            # End = onset của nhịp kế tiếp, hoặc cuối tín hiệu
            end = int(onsets[i + 1]) if i + 1 < len(onsets) else len(raw) - 1

            # Kiểm tra hình học cơ bản
            if end <= onset or peak <= onset or peak >= end:
                continue

            # Kiểm tra IBI sinh lý
            ibi_s = (end - onset) / fs
            if not (min_ibi_s <= ibi_s <= max_ibi_s):
                continue

            # Cắt và chuẩn hóa min-max về [0, 1]
            segment = raw[onset : end + 1].copy()
            seg_min = segment.min()
            seg_max = segment.max()
            amplitude = seg_max - seg_min
            if amplitude > cfg.epsilon:
                normalized = (segment - seg_min) / amplitude
            else:
                normalized = np.zeros_like(segment)

            beats.append(
                SingleBeat(
                    samples=normalized,
                    onset_idx=int(onset),
                    peak_idx=int(peak),
                    end_idx=end,
                    fs=fs,
                    raw_peak_amplitude=float(raw[peak]),
                    raw_onset_amplitude=float(raw[onset]),
                )
            )
        return beats
