import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Optional

import numpy as np

from aivitals_engine.benchmark.team_methods import TEAM_METHODS, green_intensity
from aivitals_engine.contracts.bvp_window import BVPWindow
from aivitals_engine.contracts.result import VitalsResult
from aivitals_engine.features import BVPFeatureExtractor, BVPFeatures
from aivitals_engine.integration.frontend_mapper import to_measurement_result
from aivitals_engine.integration.vitals_service import VitalsService
from aivitals_engine.signal.sliding_buffer import SlidingWindowBuffer
from aivitals_engine.signal_pipeline_realtime import FrameResult, RealtimeSignalPipeline
from aivitals_engine.vitals.preprocess import detrend_signal

DROPPED_FRAME_STATUSES = frozenset({"FACE_LOST", "ARTIFACT"})
GATE_REJECTED = "REJECTED"


@dataclass(frozen=True)
class RealtimeVitalsConfig:
    long_window_sec: float = 60.0
    min_window_sec: float = 8.0
    update_interval_sec: float = 1.0
    target_fps: float = 30.0
    time_gap_threshold_sec: float = 0.5


@dataclass
class RealtimeVitalsUpdate:
    frame: FrameResult
    vitals: Optional[VitalsResult] = None
    window_seconds: float = 0.0
    bvp_features: Optional[BVPFeatures] = None

    @property
    def has_new_vitals(self) -> bool:
        return self.vitals is not None


class RealtimeVitalsEngine:
    def __init__(
        self,
        session_id: str,
        pipeline: Optional[RealtimeSignalPipeline] = None,
        service: Optional[VitalsService] = None,
        config: Optional[RealtimeVitalsConfig] = None,
    ) -> None:
        self.session_id = session_id
        self._config = config or RealtimeVitalsConfig()
        self._pipeline = pipeline or RealtimeSignalPipeline()
        self._service = service or VitalsService()
        self._feature_extractor = BVPFeatureExtractor()
        self._long_buffer = SlidingWindowBuffer(
            window_sec=self._config.long_window_sec,
            target_fps=self._config.target_fps,
            min_sec=self._config.min_window_sec,
            artifact_threshold=None,
            time_gap_threshold=self._config.time_gap_threshold_sec,
        )
        self._frame_flags: deque[tuple[float, bool]] = deque()
        self._last_compute_ts: Optional[float] = None
        self._latest: Optional[VitalsResult] = None
        self._latest_features: Optional[BVPFeatures] = None

    @property
    def latest_features(self) -> Optional[BVPFeatures]:
        return self._latest_features

    @property
    def latest_result(self) -> Optional[VitalsResult]:
        return self._latest

    def latest_measurement_result(self, measurement_id: str) -> dict[str, Any]:
        return to_measurement_result(self._latest, measurement_id)

    def reset(self) -> None:
        self._pipeline.reset()
        self._long_buffer.reset()
        self._frame_flags.clear()
        self._last_compute_ts = None
        self._latest = None
        self._latest_features = None
        self._service.reset_session(self.session_id)

    def process_frame(self, frame_bgr: np.ndarray, timestamp: Optional[float] = None) -> RealtimeVitalsUpdate:
        ts = float(timestamp) if timestamp is not None else time.perf_counter()
        frame = self._pipeline.process_frame(frame_bgr, ts)
        dropped = frame.status in DROPPED_FRAME_STATUSES or frame.raw_rgb is None
        self._remember_frame(ts, dropped)
        if not dropped:
            self._long_buffer.push(frame.raw_rgb, timestamp=ts)
        if not self._should_compute(frame, ts):
            return RealtimeVitalsUpdate(frame=frame)
        window = self.build_window(frame, ts)
        self._last_compute_ts = ts
        self._latest = self._service.compute(window, self.session_id)
        self._latest_features = self._feature_extractor.extract(window.samples, window.sampling_rate_hz)
        return RealtimeVitalsUpdate(
            frame=frame,
            vitals=self._latest,
            window_seconds=window.duration_seconds,
            bvp_features=self._latest_features,
        )

    def build_window(self, frame: FrameResult, ts: float) -> BVPWindow:
        rgb, fps = self._long_buffer.get_resampled_window()
        method = TEAM_METHODS[frame.method_name.upper()](fps=fps)
        samples = method.process(rgb)
        return BVPWindow(
            samples=samples,
            sampling_rate_hz=fps,
            start_timestamp=ts - samples.size / fps,
            method=frame.method_name,
            method_version=frame.method_version,
            signal_quality=float(np.clip(frame.quality_sqi, 0.0, 1.0)),
            missing_ratio=self.missing_ratio(),
            raw_samples=detrend_signal(green_intensity(rgb)),
        )

    def missing_ratio(self) -> float:
        if not self._frame_flags:
            return 0.0
        return float(np.mean([dropped for _, dropped in self._frame_flags]))

    def _remember_frame(self, ts: float, dropped: bool) -> None:
        self._frame_flags.append((ts, dropped))
        horizon = ts - self._config.long_window_sec
        while self._frame_flags and self._frame_flags[0][0] < horizon:
            self._frame_flags.popleft()

    def _should_compute(self, frame: FrameResult, ts: float) -> bool:
        if not frame.is_ready or not self._long_buffer.is_ready():
            return False
        if getattr(frame, "quality_state", None) == GATE_REJECTED:
            return False
        if frame.method_name.upper() not in TEAM_METHODS:
            return False
        if self._last_compute_ts is None:
            return True
        return ts - self._last_compute_ts >= self._config.update_interval_sec
