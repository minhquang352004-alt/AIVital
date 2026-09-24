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
from dataclasses import dataclass
from typing import Optional, Tuple, Union

import numpy as np

from aivitals_engine.config.settings import SignalConfig
from aivitals_engine.face.detector import BaseFaceDetector, SimpleFaceDetector
from aivitals_engine.quality.sqi import calculate_bvp_quality
from aivitals_engine.roi.extractor import ROIExtractor
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
    frame_count:    int                  = 0
    artifact_count: int                  = 0
    method_name:    str                  = "POS"
    method_version: str                  = "1.0"


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
    ) -> None:
        """
        Args:
            method: Tên thuật toán ("GREEN", "CHROM", "POS") hoặc instance RPPGMethod.
                    Bị ghi đè bởi `rppg_method` nếu `rppg_method` được truyền vào.
        """
        self._cfg = config if config is not None else SignalConfig()

        self._face_detector: BaseFaceDetector = (
            face_detector if face_detector is not None else SimpleFaceDetector()
        )
        self._roi_extractor: ROIExtractor = (
            roi_extractor if roi_extractor is not None
            else ROIExtractor()
        )
        self._buffer: SlidingWindowBuffer = SlidingWindowBuffer(
            window_sec         = window_sec         if window_sec         is not None else self._cfg.window_sec,
            target_fps         = target_fps         if target_fps         is not None else self._cfg.fps,
            min_sec            = min_sec            if min_sec            is not None else self._cfg.min_window_sec,
            artifact_threshold = artifact_threshold if artifact_threshold is not None else self._cfg.artifact_threshold,
            time_gap_threshold = self._cfg.time_gap_threshold_sec,
        )
        self._lowcut  = lowcut  if lowcut  is not None else self._cfg.low_cutoff_hz
        self._highcut = highcut if highcut is not None else self._cfg.high_cutoff_hz
        self._target_fps = target_fps if target_fps is not None else self._cfg.fps

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

        bbox = self._detect_face(frame)
        if bbox is None:
            return self._result_face_lost()

        rgb = self._extract_rgb(frame, bbox)

        if not self._push_to_buffer(rgb, ts):
            return self._result_artifact(rgb, bbox)

        if not self._buffer.is_ready():
            return self._result_buffering(rgb, bbox)

        rgb_resampled, effective_fps = self._buffer.get_resampled_window()
        bvp = self._run_rppg(rgb_resampled, effective_fps)
        sqi = self._score_quality(bvp, effective_fps)

        return self._result_ok(bvp, sqi, effective_fps, rgb_resampled, rgb, bbox)

    def reset(self) -> None:
        """Reset toàn bộ pipeline về trạng thái ban đầu."""
        self._buffer.reset()
        self._face_detector.reset()
        self._rppg_method.reset()
        self._frame_count = 0

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

    def _detect_face(self, frame: np.ndarray) -> Optional[tuple]:
        return self._face_detector.detect(frame)

    def _extract_rgb(self, frame: np.ndarray, bbox: tuple) -> np.ndarray:
        return self._roi_extractor.extract_mean_rgb(frame, bbox)

    def _push_to_buffer(self, rgb: np.ndarray, ts: float) -> bool:
        return self._buffer.push(rgb, timestamp=ts)

    def _run_rppg(self, rgb_resampled: np.ndarray, effective_fps: float) -> np.ndarray:
        self._rppg_method.fps = effective_fps
        return self._rppg_method.process(rgb_resampled)

    def _score_quality(self, bvp: np.ndarray, fps: float) -> float:
        return calculate_bvp_quality(bvp, fs=fps)

    # ──────────────────────────────────────────────────────────────────────────
    # Private — tạo FrameResult cho từng trường hợp
    # ──────────────────────────────────────────────────────────────────────────

    def _result_face_lost(self) -> FrameResult:
        return FrameResult(
            is_ready       = False,
            status         = "FACE_LOST",
            fps            = self._buffer.get_fps(),
            progress       = self._buffer.get_progress(),
            frame_count    = self._frame_count,
            artifact_count = self._buffer.artifact_count,
            method_name    = self._rppg_method.name,
            method_version = self._rppg_method.version,
        )

    def _result_artifact(self, rgb: np.ndarray, bbox: tuple) -> FrameResult:
        return FrameResult(
            is_ready       = False,
            status         = "ARTIFACT",
            fps            = self._buffer.get_fps(),
            progress       = self._buffer.get_progress(),
            raw_rgb        = rgb,
            bbox           = bbox,
            frame_count    = self._frame_count,
            artifact_count = self._buffer.artifact_count,
            method_name    = self._rppg_method.name,
            method_version = self._rppg_method.version,
        )

    def _result_buffering(self, rgb: np.ndarray, bbox: tuple) -> FrameResult:
        return FrameResult(
            is_ready       = False,
            status         = "BUFFERING",
            fps            = self._buffer.get_fps(),
            progress       = self._buffer.get_progress(),
            raw_rgb        = rgb,
            bbox           = bbox,
            frame_count    = self._frame_count,
            artifact_count = self._buffer.artifact_count,
            method_name    = self._rppg_method.name,
            method_version = self._rppg_method.version,
        )

    def _result_ok(
        self,
        bvp:           np.ndarray,
        sqi:           float,
        effective_fps: float,
        rgb_resampled: np.ndarray,
        raw_rgb:       np.ndarray,
        bbox:          tuple,
    ) -> FrameResult:
        status = "OK" if sqi >= self._SQI_THRESHOLD else "LOW_QUALITY"
        meta   = self._rppg_method.get_metadata()
        return FrameResult(
            is_ready       = True,
            status         = status,
            bvp_signal     = bvp,
            quality_sqi    = sqi,
            resampled_rgb  = rgb_resampled,
            fps            = effective_fps,
            progress       = self._buffer.get_progress(),
            raw_rgb        = raw_rgb,
            bbox           = bbox,
            frame_count    = self._frame_count,
            artifact_count = self._buffer.artifact_count,
            method_name    = meta["method"],
            method_version = meta["version"],
        )

