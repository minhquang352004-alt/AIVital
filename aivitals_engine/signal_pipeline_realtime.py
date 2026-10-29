"""
signal_pipeline_realtime.py
===========================
Orchestrator kết nối toàn bộ luồng xử lý tín hiệu rPPG thời gian thực:

    Frame → FaceDetector → ROIExtractor → SlidingWindowBuffer
          → Resampling → rPPGMethod (POS/CHROM/GREEN) → BVP + SQI → FrameResult

Cách dùng:
    >>> from aivitals_engine.signal_pipeline_realtime import RealtimeSignalPipeline
    >>> pipeline = RealtimeSignalPipeline()
    >>> result   = pipeline.process_frame(frame)
    >>> if result.is_ready:
    ...     bvp = result.bvp_signal   # sóng mạch 1D bàn giao cho Khoa (HR/HRV) và Quang (biểu đồ)
"""

import time
from collections import deque
from dataclasses import dataclass
from typing import Optional, Tuple, Union

import numpy as np

from aivitals_engine.config.settings import (
    FaceDetectorConfig,
    ROIConfig,
    SignalConfig,
)
from aivitals_engine.face.detector import (
    BaseFaceDetector,
    HaarCascadeFaceDetector,
    MediaPipeFaceDetector,
    SimpleFaceDetector,
)
from aivitals_engine.quality.signal_warnings import SignalWarning, has_blocking
from aivitals_engine.quality.sqi import calculate_bvp_quality
from aivitals_engine.roi.extractor import ROIExtractor, SubROIResult
from aivitals_engine.rppg.base import RPPGMethod
from aivitals_engine.rppg.chrom import CHROMMethod
from aivitals_engine.rppg.green import GREENMethod
from aivitals_engine.rppg.pos import POSMethod
from aivitals_engine.signal.sliding_buffer import SlidingWindowBuffer


# ──────────────────────────────────────────────────────────────────────────────
# Data contract — đầu ra mỗi frame
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class FrameResult:
    """
    Kết quả xử lý 1 frame từ RealtimeSignalPipeline.

    Attributes:
        is_ready:       True khi buffer đủ dữ liệu và bvp_signal hợp lệ.
        status:         Trạng thái pipeline:
                        - ``"BUFFERING"``   : đang tích lũy, chưa đủ window.
                        - ``"FACE_LOST"``   : không nhận diện được mặt.
                        - ``"ARTIFACT"``    : frame bị loại do đột biến.
                        - ``"LOW_QUALITY"`` : BVP sẵn sàng nhưng SQI < 0.4.
                        - ``"OK"``          : BVP sẵn sàng, SQI ≥ 0.4.
        bvp_signal:     Sóng mạch 1D đã lọc sạch → Khoa (HR/HRV) + Quang (đồ thị).
        quality_sqi:    SQI [0.0 → 1.0] → Quang (đèn báo tín hiệu).
        resampled_rgb:  RGB đã resample (giữ DC), shape (N, 3).
        fps:            FPS thực tế từ buffer.
        progress:       Tiến độ nạp buffer [0.0 → 1.0] → Quang (thanh chờ).
        raw_rgb:        Vector RGB thô frame này (3,).
        bbox:           Bounding box mặt đã làm mịn (x, y, w, h) → Quang (khung camera).
        frame_count:    Tổng frame đã xử lý từ khi khởi tạo.
        artifact_count: Tổng frame bị loại do artifact detection.
        method_name:    Tên thuật toán rPPG đang dùng: "GREEN", "CHROM", hoặc "POS".
        method_version: Phiên bản thuật toán, ví dụ "1.0".
        warnings:       Mã cảnh báo tín hiệu/môi trường của frame này (xem
                        quality/signal_warnings.py và docs/ROBUSTNESS.md), ví dụ
                        "TOO_DARK", "MOTION_HIGH", "LOW_FPS", "TIME_GAP".
        luma:           Luma khuôn mặt đã làm mượt (0-255); 0.0 nếu chưa đo được.
        face_width_ratio: Bề rộng mặt / bề rộng frame.
        face_lost_duration_sec: Thời gian mất mặt liên tục (chỉ khác 0 khi FACE_LOST).
    """
    is_ready:       bool                 = False
    status:         str                  = "BUFFERING"
    bvp_signal:     Optional[np.ndarray] = None
    quality_sqi:    float                = 0.0
    resampled_rgb:  Optional[np.ndarray] = None
    fps:            float                = 30.0
    progress:       float                = 0.0
    raw_rgb:        Optional[np.ndarray] = None
    bbox:           Optional[tuple]      = None
    landmarks:      Optional[np.ndarray] = None
    frame_count:    int                  = 0
    artifact_count: int                  = 0
    method_name:    str                  = "POS"
    method_version: str                  = "1.0"

    # Quality Gate (Week 4/5/6/7)
    quality_metrics: dict = None
    quality_state:  str = None
    quality_reasons: list = None

    # Cảnh báo môi trường & Tình huống biên (Week 7)
    warnings: list = None
    luma: float = 0.0
    face_width_ratio: float = 0.0
    face_lost_duration_sec: float = 0.0



# ──────────────────────────────────────────────────────────────────────────────
# Pipeline chính
# ──────────────────────────────────────────────────────────────────────────────

class RealtimeSignalPipeline:
    """
    Pipeline xử lý tín hiệu realtime: Frame → Face → ROI → Buffer → rPPG → BVP + SQI.

    Mỗi lần gọi `process_frame()` xử lý đúng 1 frame và trả về `FrameResult`.

    Khởi tạo với method tùy chọn:
        pipeline = RealtimeSignalPipeline(method="CHROM")
        pipeline = RealtimeSignalPipeline(method="GREEN")

    Hoặc switch method sau khi đã tạo (reset buffer tự động):
        pipeline.set_method("POS")
    """

    _SQI_THRESHOLD = 0.40  # Ngưỡng phân biệt OK / LOW_QUALITY

    def __init__(
        self,
        window_sec:         Optional[float]            = None,
        min_sec:            Optional[float]            = None,
        target_fps:         Optional[float]            = None,
        lowcut:             Optional[float]            = None,
        highcut:            Optional[float]            = None,
        artifact_threshold: Optional[float]            = None,
        face_detector:      Optional[BaseFaceDetector] = None,
        roi_extractor:      Optional[ROIExtractor]     = None,
        rppg_method:        Optional[RPPGMethod]       = None,
        method:             Union[str, RPPGMethod]     = "POS",
        config:             Optional[SignalConfig]     = None,
        face_config:        Optional[FaceDetectorConfig] = None,
        roi_config:         Optional[ROIConfig]        = None,
    ) -> None:
        """
        Args:
            method: Tên thuật toán ("GREEN", "CHROM", "POS") hoặc instance RPPGMethod.
                    Bị ghi đè bởi `rppg_method` nếu `rppg_method` được truyền vào.
        """
        self._cfg = config if config is not None else SignalConfig()
        self._face_cfg = face_config if face_config is not None else FaceDetectorConfig()
        self._roi_cfg = roi_config if roi_config is not None else ROIConfig()

        self._face_detector: BaseFaceDetector = (
            face_detector if face_detector is not None else self._build_face_detector(self._face_cfg)
        )
        self._roi_extractor: ROIExtractor = (
            roi_extractor if roi_extractor is not None
            else ROIExtractor(config=self._roi_cfg)
        )
        self._buffer: SlidingWindowBuffer = SlidingWindowBuffer(
            window_sec         = window_sec         if window_sec         is not None else self._cfg.window_sec,
            target_fps         = target_fps         if target_fps         is not None else self._cfg.fps,
            min_sec            = min_sec            if min_sec            is not None else self._cfg.min_window_sec,
            artifact_threshold = artifact_threshold if artifact_threshold is not None else self._cfg.artifact_threshold,
            # Để dung nạp mất mặt tạm thời (max_face_lost_sec) mà không reset buffer,
            # ngưỡng đứt timestamp phải >= thời gian mất mặt cho phép.
            time_gap_threshold = max(self._cfg.time_gap_threshold_sec, self._cfg.max_face_lost_sec),
            max_consecutive_artifacts = self._cfg.max_consecutive_artifacts,
        )
        self._lowcut  = lowcut  if lowcut  is not None else self._cfg.low_cutoff_hz
        self._highcut = highcut if highcut is not None else self._cfg.high_cutoff_hz
        self._target_fps = target_fps if target_fps is not None else self._cfg.fps

        from collections import deque
        from aivitals_engine.quality.gate import QualityGate
        self._bbox_buffer = deque(maxlen=self._buffer._rgb_buffer.maxlen)
        self._quality_gate = QualityGate()
        self._last_sqi_calc_time: Optional[float] = None
        self._cached_metrics = {}

        # Tracking tình huống biên mất mặt tạm thời (Week 7)
        self._last_face_detected_ts: Optional[float] = None
        self._face_lost_start_ts: Optional[float] = None
        # Lịch sử môi trường (Week 7): luma, ổn định ánh sáng, chuyển động mặt
        self._last_warnings: list = []   # cảnh báo của frame gần nhất (dùng cho guard đặc trưng)
        self._luma_recent:  deque = deque(maxlen=max(1, int(self._cfg.luma_smooth_frames)))
        self._luma_history: deque = deque()   # (ts, luma) trong light_window_sec
        self._motion_history: deque = deque()  # (ts, cx, cy, w) trong motion_window_sec

        # rppg_method (legacy) takes precedence over method (new param)
        if rppg_method is not None:
            self._rppg_method: RPPGMethod = rppg_method
        else:
            self._rppg_method = self._build_rppg_method(method)

        self._frame_count: int = 0

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

    def set_method(self, method: Union[str, RPPGMethod]) -> None:
        """
        Switch thuật toán rPPG đang dùng và reset toàn bộ pipeline.

        Args:
            method: Tên thuật toán ("GREEN", "CHROM", "POS") hoặc instance RPPGMethod.

        Raises:
            ValueError: Nếu tên thuật toán không hợp lệ.

        Ví dụ:
            pipeline.set_method("CHROM")
            pipeline.set_method(GREENMethod(fps=30))
        """
        self._rppg_method = self._build_rppg_method(method)
        self.reset()


    def process_frame(
        self,
        frame:     np.ndarray,
        timestamp: Optional[float] = None,
    ) -> FrameResult:
        """Xử lý 1 frame BGR từ camera và cập nhật pipeline tín hiệu."""
        self._frame_count += 1
        ts = timestamp if timestamp is not None else time.perf_counter()

        frame = self._sanitize_frame(frame)
        bbox = None if frame is None else self._detect_face(frame)
        if bbox is None:
            if self._face_lost_start_ts is None:
                self._face_lost_start_ts = ts
            lost_duration = ts - self._face_lost_start_ts
            if lost_duration > self._cfg.max_face_lost_sec:
                self._reset_signal_state()
            return self._result_face_lost(
                face_lost_duration_sec=lost_duration,
                warnings=[SignalWarning.FACE_NOT_FOUND.value]
            )

        # Mặt tìm thấy lại -> reset mốc mất mặt
        self._face_lost_start_ts = None
        self._last_face_detected_ts = ts

        # Điều kiện môi trường tức thời (kích thước mặt, ánh sáng, chuyển động)
        warnings: list = []
        frame_h, frame_w = frame.shape[:2]
        x, y, w, h = bbox
        face_width_ratio = float(w) / float(frame_w) if frame_w > 0 and w is not None else 0.0
        if 0.0 < face_width_ratio < self._cfg.min_face_ratio:
            warnings.append(SignalWarning.FACE_TOO_SMALL.value)

        luma = self._update_light(ts, self._measure_luma(frame, bbox))
        if luma > 0.0:
            if luma < self._cfg.min_luma_acceptable:
                warnings.append(SignalWarning.TOO_DARK.value)
            elif luma > self._cfg.max_luma_acceptable:
                warnings.append(SignalWarning.TOO_BRIGHT.value)
        if self._is_light_unstable():
            warnings.append(SignalWarning.LIGHT_UNSTABLE.value)

        motion_high, bbox_jumped = self._update_motion(ts, bbox)
        if bbox_jumped:
            # ROI nhảy đột ngột -> dữ liệu cũ không còn cùng vị trí, bắt đầu lại cửa sổ
            self._buffer.reset()
            self._invalidate_quality_cache()
        if motion_high:
            warnings.append(SignalWarning.MOTION_HIGH.value)

        landmarks = self._face_detector.get_landmarks()

        rgb      = self._extract_rgb(frame, bbox, landmarks=landmarks)
        sub_rgbs = self._extract_sub_roi_rgbs(frame, bbox, landmarks=landmarks)  # per-region (new)

        gap_before, adapt_before = self._buffer.gap_reset_count, self._buffer.adapt_count
        pushed = self._push_to_buffer(rgb, ts, sub_rgbs=sub_rgbs, bbox=bbox)
        if self._buffer.gap_reset_count > gap_before:
            warnings.append(SignalWarning.TIME_GAP.value)
            self._invalidate_quality_cache()
        if self._buffer.adapt_count > adapt_before:
            # Baseline mới sau bước nhảy ánh sáng: SQI/quality cũ không còn đúng
            self._invalidate_quality_cache()

        if (self._buffer.size >= self._cfg.min_frames_for_fps_check
                and self._buffer.get_fps() < self._cfg.min_fps_acceptable):
            warnings.append(SignalWarning.LOW_FPS.value)

        self._last_warnings = warnings

        if not pushed:
            return self._result_artifact(
                rgb, bbox, landmarks=landmarks,
                warnings=warnings, luma=luma, face_width_ratio=face_width_ratio
            )

        if not self._buffer.is_ready():
            return self._result_buffering(
                rgb, bbox, landmarks=landmarks,
                warnings=warnings, luma=luma, face_width_ratio=face_width_ratio
            )

        rgb_resampled, effective_fps = self._buffer.get_resampled_window()
        bvp = self._run_rppg(rgb_resampled, effective_fps)
        sqi = self._score_quality(bvp, effective_fps)

        # Advanced SQI calculation (throttle to ~1s theo timestamp logic ts)
        if (
            self._last_sqi_calc_time is None
            or (ts - self._last_sqi_calc_time) >= 1.0
            or ts < self._last_sqi_calc_time
        ):
            from aivitals_engine.quality.sqi import calculate_periodicity_sqi, calculate_cross_roi_sqi
            from aivitals_engine.quality.motion import calculate_motion_sqi
            
            # Periodicity
            periodicity, _ = calculate_periodicity_sqi(
                bvp,
                effective_fps,
                min_bpm=self._cfg.periodicity_min_bpm,
                max_bpm=self._cfg.periodicity_max_bpm,
            )
            
            # Cross-ROI
            sub_raw = self._buffer.get_sub_roi_raw_window()
            sub_rgbs_dict = {
                'forehead': sub_raw[0],
                'left_cheek': sub_raw[1],
                'right_cheek': sub_raw[2]
            }
            cross_roi = calculate_cross_roi_sqi(sub_rgbs_dict, effective_fps)
            
            # Motion
            bbox_window = self._buffer.get_bbox_window()
            motion = calculate_motion_sqi(bbox_window, effective_fps)
            
            # Artifact ratio
            total_frames = self._buffer.size + self._buffer.artifact_count
            artifact_ratio = self._buffer.artifact_count / total_frames if total_frames > 0 else 0.0
            
            metrics = {
                'window_len': len(bvp),
                'min_window_len': self._cfg.min_window_sec * effective_fps,
                'snr': sqi,
                'periodicity': periodicity,
                'r_mean': cross_roi.get('r_mean', 1.0),
                'motion_score': motion.get('motion_score', 0.0),
                'artifact_ratio': artifact_ratio
            }
            
            state, reasons = self._quality_gate.evaluate(metrics, ts)
            
            self._cached_metrics = {
                'metrics': metrics,
                'state': state.value,
                'reasons': [r.value for r in reasons]
            }
            self._last_sqi_calc_time = ts

        c_metrics = self._cached_metrics.get('metrics', {})
        c_state = self._cached_metrics.get('state', "ACCEPTED")
        c_reasons = self._cached_metrics.get('reasons', [])

        return self._result_ok(
            bvp, sqi, effective_fps, rgb_resampled, rgb, bbox,
            c_metrics, c_state, c_reasons, landmarks=landmarks,
            warnings=warnings, luma=luma, face_width_ratio=face_width_ratio
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Private — robustness helpers (Week 7)
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _sanitize_frame(frame) -> Optional[np.ndarray]:
        """
        Chuẩn hóa frame đầu vào: trả None nếu không dùng được.
        - None / rỗng / không phải ndarray → None
        - Ảnh xám (H, W) hoặc (H, W, 1) → nhân thành 3 kênh
        - Số kênh khác 1 hoặc 3 (kể cả BGRA 4 kênh) → bỏ kênh alpha hoặc None
        - dtype khác uint8 → clip về [0, 255] rồi ép uint8
        """
        if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
            return None
        if frame.ndim == 2:
            frame = np.stack([frame] * 3, axis=-1)
        elif frame.ndim == 3:
            ch = frame.shape[2]
            if ch == 1:
                frame = np.repeat(frame, 3, axis=2)
            elif ch == 4:
                frame = frame[:, :, :3]
            elif ch != 3:
                return None
        else:
            return None
        if frame.dtype != np.uint8:
            frame = np.clip(np.nan_to_num(frame, nan=0.0, posinf=255.0, neginf=0.0), 0, 255).astype(np.uint8)
        return frame

    @staticmethod
    def _measure_luma(frame: np.ndarray, bbox: tuple, step: int = 4) -> float:
        """Luma trung bình vùng mặt (subsample mỗi `step` pixel để giảm chi phí). 0.0 nếu không đo được."""
        frame_h, frame_w = frame.shape[:2]
        x, y, w, h = bbox
        x1, y1 = max(0, int(x)), max(0, int(y))
        x2, y2 = min(frame_w, int(x + w)), min(frame_h, int(y + h))
        if x2 <= x1 or y2 <= y1:
            return 0.0
        crop = frame[y1:y2:step, x1:x2:step, ::-1]   # BGR → RGB
        if crop.size == 0:
            return 0.0
        from aivitals_engine.quality.face_quality import measure_frame_lighting
        luma, _ = measure_frame_lighting(crop)
        return luma

    def _update_light(self, ts: float, raw_luma: float) -> float:
        """Cập nhật lịch sử ánh sáng; trả luma đã làm mượt (median) để cảnh báo không nhấp nháy."""
        if raw_luma <= 0.0:
            return 0.0
        self._luma_recent.append(raw_luma)
        self._luma_history.append((ts, raw_luma))
        horizon = ts - self._cfg.light_window_sec
        while self._luma_history and self._luma_history[0][0] < horizon:
            self._luma_history.popleft()
        return float(np.median(self._luma_recent))

    def _is_light_unstable(self) -> bool:
        """True nếu luma dao động mạnh (flicker / bật tắt đèn) trong light_window_sec."""
        if len(self._luma_history) < 10:
            return False
        ts_arr = [t for t, _ in self._luma_history]
        if ts_arr[-1] - ts_arr[0] < 0.5 * self._cfg.light_window_sec:
            return False
        vals = np.array([v for _, v in self._luma_history], dtype=np.float64)
        mean = float(vals.mean())
        if mean <= 1e-6:
            return False
        return float(vals.std() / mean) > self._cfg.light_unstable_cv

    def _update_motion(self, ts: float, bbox: tuple) -> Tuple[bool, bool]:
        """
        Cập nhật lịch sử tâm mặt.

        Returns:
            (motion_high, bbox_jumped)
            - motion_high: biên độ dịch chuyển tâm mặt / bề rộng mặt trong motion_window_sec
              vượt `motion_amp_threshold`.
            - bbox_jumped: tâm mặt nhảy > `bbox_jump_ratio` × bề rộng mặt so với frame trước.
        """
        x, y, w, h = bbox
        w = float(w)
        if w <= 0:
            return False, False
        cx, cy = x + w / 2.0, y + float(h) / 2.0

        jumped = False
        if self._motion_history:
            _, pcx, pcy, pw = self._motion_history[-1]
            if np.hypot(cx - pcx, cy - pcy) > self._cfg.bbox_jump_ratio * max(pw, w):
                jumped = True
                self._motion_history.clear()

        self._motion_history.append((ts, cx, cy, w))
        horizon = ts - self._cfg.motion_window_sec
        while self._motion_history and self._motion_history[0][0] < horizon:
            self._motion_history.popleft()

        if jumped:
            return True, True
        if len(self._motion_history) < 5:
            return False, False
        arr = np.array(self._motion_history, dtype=np.float64)
        amp = max(np.ptp(arr[:, 1]), np.ptp(arr[:, 2])) / max(float(arr[:, 3].mean()), 1e-6)
        return bool(amp > self._cfg.motion_amp_threshold), False

    def _invalidate_quality_cache(self) -> None:
        """Bỏ SQI/quality đã cache để lần sau tính lại từ buffer mới."""
        self._cached_metrics = {}
        self._last_sqi_calc_time = None

    def _reset_signal_state(self) -> None:
        """Reset buffer và toàn bộ trạng thái suy ra từ nó (dùng khi mất mặt quá lâu)."""
        self._buffer.reset()
        self._invalidate_quality_cache()
        self._motion_history.clear()


    def reset(self) -> None:
        """Reset toàn bộ pipeline về trạng thái ban đầu."""
        self._buffer.reset()
        self._face_detector.reset()
        self._rppg_method.reset()
        self._frame_count = 0
        self._last_face_detected_ts = None
        self._face_lost_start_ts = None
        self._last_sqi_calc_time = None
        self._cached_metrics = {}
        self._luma_recent.clear()
        self._luma_history.clear()
        self._motion_history.clear()
        self._last_warnings = []

    # ──────────────────────────────────────────────────────────────────────────
    # Properties tiện ích
    # ──────────────────────────────────────────────────────────────────────────

    @property
    def buffer_size(self) -> int:
        return self._buffer.size

    @property
    def estimated_fps(self) -> float:
        return self._buffer.get_fps()

    @property
    def progress(self) -> float:
        return self._buffer.get_progress()

    @property
    def is_ready(self) -> bool:
        return self._buffer.is_ready()

    @property
    def current_method(self) -> str:
        """Tên thuật toán rPPG đang được dùng: "GREEN", "CHROM", hoặc "POS"."""
        return self._rppg_method.name

    def get_sub_roi_window(
        self,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Return per-region raw RGB windows currently held in the buffer.

        Returns the same triple as SlidingWindowBuffer.get_sub_roi_raw_window():
        (forehead, left_cheek, right_cheek), each shape (N, 3).
        N equals buffer.size when sub-ROIs have been pushed consistently.
        Shape (0, 3) if no sub-ROI data has been collected yet.
        """
        return self._buffer.get_sub_roi_raw_window()

    def extract_features(self):
        """
        Trích xuất đặc trưng sinh lý BVP (BVPFeatures) từ cửa sổ hiện tại.
        Trả về None nếu buffer chưa đủ dữ liệu (chưa ready).
        """
        if not self._buffer.is_ready():
            return None
        rgb_resampled, effective_fps = self._buffer.get_resampled_window()
        bvp = self._run_rppg(rgb_resampled, effective_fps)
        from aivitals_engine.features import BVPFeatureExtractor
        return BVPFeatureExtractor().extract(bvp, effective_fps)

    def extract_features_checked(self):
        """
        Như `extract_features()` nhưng có cổng chất lượng (Tuần 7).

        Trả về `GuardedFeatures`:
            - ``features``: BVPFeatures nếu tín hiệu đạt guard, ngược lại None.
            - ``reasons`` : mã lý do bị từ chối (vd. "LOW_SQI", "BLOCKING_WARNING").
            - ``validity.metadata``: method, version, fs, sqi, artifact_ratio, cảnh báo.
        Trả None nếu buffer chưa sẵn sàng (cùng quy ước với `extract_features()`).
        """
        if not self._buffer.is_ready():
            return None
        rgb_resampled, effective_fps = self._buffer.get_resampled_window()
        bvp = self._run_rppg(rgb_resampled, effective_fps)
        sqi = self._score_quality(bvp, effective_fps)
        total = self._buffer.size + self._buffer.artifact_count
        artifact_ratio = self._buffer.artifact_count / total if total > 0 else 0.0
        from aivitals_engine.features import BVPFeatureExtractor
        return BVPFeatureExtractor().extract_checked(
            bvp, effective_fps,
            sqi=sqi,
            warnings=self._last_warnings,
            artifact_ratio=artifact_ratio,
            metadata={"method": self._rppg_method.name,
                      "method_version": self._rppg_method.version},
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Private — factory và helper
    # ──────────────────────────────────────────────────────────────────────────

    def _build_rppg_method(self, method: Union[str, RPPGMethod]) -> RPPGMethod:
        """
        Factory tạo RPPGMethod từ tên chuỗi hoặc trả lại instance trực tiếp.

        Args:
            method: "GREEN", "CHROM", "POS" (case-insensitive) hoặc RPPGMethod instance.

        Returns:
            RPPGMethod được khởi tạo với config hiện tại.

        Raises:
            ValueError: Nếu tên không thuộc GREEN / CHROM / POS.
        """
        if isinstance(method, RPPGMethod):
            return method

        name = str(method).upper()
        kwargs = dict(
            fps           = self._target_fps,
            window_sec    = self._cfg.sub_window_sec,
            lowcut        = self._lowcut,
            highcut       = self._highcut,
            detrend_lambda = self._cfg.detrend_lambda,
        )
        if name == "POS":
            return POSMethod(**kwargs)
        if name == "CHROM":
            return CHROMMethod(**kwargs)
        if name == "GREEN":
            return GREENMethod(**kwargs)
        raise ValueError(
            f"Thuật toán '{method}' không hợp lệ. Chọn 'GREEN', 'CHROM', hoặc 'POS'."
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Private — mỗi method làm đúng 1 bước trong pipeline
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _build_face_detector(cfg: FaceDetectorConfig) -> BaseFaceDetector:
        if cfg.detector_backend == "mediapipe":
            return MediaPipeFaceDetector(config=cfg)
        return HaarCascadeFaceDetector(config=cfg)

    def _detect_face(self, frame: np.ndarray) -> Optional[tuple]:
        return self._face_detector.detect(frame)

    def _extract_rgb(
        self,
        frame: np.ndarray,
        bbox: tuple,
        landmarks: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        return self._roi_extractor.extract_mean_rgb(frame, bbox, landmarks=landmarks)

    def _extract_sub_roi_rgbs(
        self,
        frame: np.ndarray,
        bbox: tuple,
        landmarks: Optional[np.ndarray] = None,
    ) -> SubROIResult:
        """Return per-region RGB vectors (forehead, left_cheek, right_cheek)."""
        return self._roi_extractor.extract_sub_roi_rgbs(frame, bbox, landmarks=landmarks)

    def _push_to_buffer(
        self,
        rgb:      np.ndarray,
        ts:       float,
        sub_rgbs: Optional[SubROIResult] = None,
        bbox:     Optional[tuple] = None,
    ) -> bool:
        return self._buffer.push(rgb, timestamp=ts, sub_rgbs=sub_rgbs, bbox=bbox)

    def _run_rppg(self, rgb_resampled: np.ndarray, effective_fps: float) -> np.ndarray:
        self._rppg_method.fps = effective_fps
        return self._rppg_method.process(rgb_resampled)

    def _score_quality(self, bvp: np.ndarray, fps: float) -> float:
        return calculate_bvp_quality(
            bvp,
            fs=fps,
            low_cutoff=self._lowcut,
            high_cutoff=self._highcut,
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Private — tạo FrameResult cho từng trường hợp
    # ──────────────────────────────────────────────────────────────────────────

    def _result_face_lost(
        self,
        face_lost_duration_sec: float = 0.0,
        warnings:               Optional[list] = None,
    ) -> FrameResult:
        return FrameResult(
            is_ready               = False,
            status                 = "FACE_LOST",
            fps                    = self._buffer.get_fps(),
            progress               = self._buffer.get_progress(),
            frame_count            = self._frame_count,
            artifact_count         = self._buffer.artifact_count,
            method_name            = self._rppg_method.name,
            method_version         = self._rppg_method.version,
            face_lost_duration_sec = face_lost_duration_sec,
            warnings               = warnings if warnings is not None else ["FACE_NOT_FOUND"],
        )

    def _result_artifact(
        self,
        rgb:              np.ndarray,
        bbox:             tuple,
        landmarks:        Optional[np.ndarray] = None,
        warnings:         Optional[list] = None,
        luma:             float = 0.0,
        face_width_ratio: float = 0.0,
    ) -> FrameResult:
        warns = list(warnings) if warnings is not None else []
        if SignalWarning.ARTIFACT_DETECTED.value not in warns:
            warns.append(SignalWarning.ARTIFACT_DETECTED.value)
        return FrameResult(
            is_ready         = False,
            status           = "ARTIFACT",
            fps              = self._buffer.get_fps(),
            progress         = self._buffer.get_progress(),
            raw_rgb          = rgb,
            bbox             = bbox,
            landmarks        = landmarks,
            frame_count      = self._frame_count,
            artifact_count   = self._buffer.artifact_count,
            method_name      = self._rppg_method.name,
            method_version   = self._rppg_method.version,
            warnings         = warns,
            luma             = luma,
            face_width_ratio = face_width_ratio,
        )

    def _result_buffering(
        self,
        rgb:              np.ndarray,
        bbox:             tuple,
        landmarks:        Optional[np.ndarray] = None,
        warnings:         Optional[list] = None,
        luma:             float = 0.0,
        face_width_ratio: float = 0.0,
    ) -> FrameResult:
        return FrameResult(
            is_ready         = False,
            status           = "BUFFERING",
            fps              = self._buffer.get_fps(),
            progress         = self._buffer.get_progress(),
            raw_rgb          = rgb,
            bbox             = bbox,
            landmarks        = landmarks,
            frame_count      = self._frame_count,
            artifact_count   = self._buffer.artifact_count,
            method_name      = self._rppg_method.name,
            method_version   = self._rppg_method.version,
            warnings         = warnings if warnings is not None else [],
            luma             = luma,
            face_width_ratio = face_width_ratio,
        )

    def _result_ok(
        self,
        bvp:              np.ndarray,
        sqi:              float,
        effective_fps:    float,
        rgb_resampled:    np.ndarray,
        raw_rgb:          np.ndarray,
        bbox:             tuple,
        quality_metrics:  dict = None,
        quality_state:    str = None,
        quality_reasons:  list = None,
        landmarks:        Optional[np.ndarray] = None,
        warnings:         Optional[list] = None,
        luma:             float = 0.0,
        face_width_ratio: float = 0.0,
    ) -> FrameResult:
        all_warnings = list(warnings) if warnings is not None else []
        if quality_reasons:
            for r in quality_reasons:
                if r not in all_warnings:
                    all_warnings.append(r)
        # Cảnh báo mức BLOCK (vd. MOTION_HIGH) hoặc QualityGate REJECTED hạ trạng thái xuống LOW_QUALITY
        status = (
            "OK"
            if (
                sqi >= self._SQI_THRESHOLD
                and not has_blocking(all_warnings)
                and quality_state != "REJECTED"
            )
            else "LOW_QUALITY"
        )
        return FrameResult(
            is_ready         = True,
            status           = status,
            bvp_signal       = bvp,
            quality_sqi      = sqi,
            resampled_rgb    = rgb_resampled,
            fps              = effective_fps,
            progress         = self._buffer.get_progress(),
            raw_rgb          = raw_rgb,
            bbox             = bbox,
            landmarks        = landmarks,
            frame_count      = self._frame_count,
            artifact_count   = self._buffer.artifact_count,
            method_name      = self._rppg_method.name,
            method_version   = self._rppg_method.version,
            quality_metrics  = quality_metrics,
            quality_state    = quality_state,
            quality_reasons  = quality_reasons,
            warnings         = all_warnings,
            luma             = luma,
            face_width_ratio = face_width_ratio,
        )
