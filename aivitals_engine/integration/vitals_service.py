from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock

from aivitals_engine.config.vitals_config import VitalsConfig
from aivitals_engine.contracts.bvp_window import BVPWindow
from aivitals_engine.contracts.result import AlgorithmInfo, ResultStatus, VitalCode, VitalsResult, VitalValue
from aivitals_engine.integration.result_builder import (
    build_measurement_window,
    build_vital_value,
    build_vitals_result,
    utc_now,
)
from aivitals_engine.validation.candidate import ValidationContext, ValidationOutcome, VitalCandidate
from aivitals_engine.validation.vital_validator import VitalValidator
from aivitals_engine.vitals.beats import BeatExtractor, BeatSeries
from aivitals_engine.vitals.confidence import (
    ConfidenceInputs,
    compute_confidence,
    derive_hrv_confidence,
    derive_respiratory_confidence,
    snr_to_score,
    stability_score,
)
from aivitals_engine.vitals.hr import HeartRateEstimate, HeartRateEstimator
from aivitals_engine.vitals.hrv import HRVEstimate, HRVEstimator
from aivitals_engine.vitals.rr import RespiratoryRateEstimate, RespiratoryRateEstimator
from aivitals_engine.vitals.tracker import TemporalTracker, TrackerConfig


@dataclass
class SessionTrackers:
    heart_rate: TemporalTracker
    respiratory_rate: TemporalTracker
    lock: Lock = field(default_factory=Lock)


def context_from_tracker(tracker: TemporalTracker) -> ValidationContext:
    last = tracker.last_accepted
    if last is None:
        return ValidationContext(recent_values=tracker.recent_values)
    return ValidationContext(previous_timestamp=last[0], previous_value=last[1], recent_values=tracker.recent_values)


def hrv_values(estimate: HRVEstimate) -> dict[VitalCode, float | None]:
    return {
        VitalCode.HRV_RMSSD: estimate.rmssd_ms,
        VitalCode.HRV_SDNN: estimate.sdnn_ms,
        VitalCode.HRV_MEAN_IBI: estimate.mean_ibi_ms,
    }


class VitalsService:
    def __init__(
        self,
        config: VitalsConfig | None = None,
        validator: VitalValidator | None = None,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._config = config or VitalsConfig()
        self._validator = validator or VitalValidator(self._config.validation)
        self._clock = clock
        self._heart_rate = HeartRateEstimator(self._config.heart_rate, self._config.beats)
        self._beat_extractor = BeatExtractor(self._config.beats)
        self._hrv = HRVEstimator(self._config.hrv)
        self._respiratory_rate = RespiratoryRateEstimator(self._config.respiratory_rate)
        self._sessions: dict[str, SessionTrackers] = {}
        self._sessions_lock = Lock()

    def compute(self, window: BVPWindow, session_id: str) -> VitalsResult:
        trackers = self._session(session_id)
        with trackers.lock:
            heart_rate_vital, estimate = self._heart_rate_vital(window, trackers.heart_rate)
            beats = self._full_window_beats(window, estimate)
            hrv_vitals = self._hrv_vitals(window, beats, estimate.snr_db, heart_rate_vital.confidence)
            respiratory_vital = self._respiratory_vital(window, beats, heart_rate_vital.confidence, trackers.respiratory_rate)
        vitals = [heart_rate_vital, *hrv_vitals, respiratory_vital]
        return build_vitals_result(session_id, window, vitals, created_at=self._clock())

    def reset_session(self, session_id: str) -> bool:
        with self._sessions_lock:
            return self._sessions.pop(session_id, None) is not None

    def active_sessions(self) -> list[str]:
        with self._sessions_lock:
            return sorted(self._sessions)

    def _session(self, session_id: str) -> SessionTrackers:
        with self._sessions_lock:
            if session_id not in self._sessions:
                tracker_config = TrackerConfig(
                    history_size=self._config.tracker_history_size,
                    smoothing_alpha=self._config.tracker_smoothing_alpha,
                )
                self._sessions[session_id] = SessionTrackers(TemporalTracker(tracker_config), TemporalTracker(tracker_config))
            return self._sessions[session_id]

    def _heart_rate_vital(self, window: BVPWindow, tracker: TemporalTracker) -> tuple[VitalValue, HeartRateEstimate]:
        estimate = self._heart_rate.estimate(window)
        candidate = VitalCandidate(
            code=VitalCode.HEART_RATE,
            value=estimate.bpm,
            timestamp=window.end_timestamp,
            confidence=self._heart_rate_confidence(window, estimate, tracker),
            window_duration_seconds=estimate.analysed_seconds,
            signal_quality=window.signal_quality,
            missing_ratio=window.missing_ratio,
            failure_reason=estimate.failure_reason,
            roi_values=self._roi_heart_rates(window),
        )
        outcome = self._validator.validate(candidate, context_from_tracker(tracker))
        reported = self._track(tracker, candidate, outcome)
        quality = self._signal_quality_score(window, estimate.snr_db)
        segment_start = window.end_timestamp - estimate.analysed_seconds
        measurement_window = build_measurement_window(segment_start, window.end_timestamp)
        vital = build_vital_value(candidate, outcome, reported, quality, measurement_window, HeartRateEstimator.algorithm)
        return vital, estimate

    def _heart_rate_confidence(self, window: BVPWindow, estimate: HeartRateEstimate, tracker: TemporalTracker) -> float:
        if estimate.bpm is None:
            return 0.0
        inputs = ConfidenceInputs(
            snr_db=estimate.snr_db,
            signal_quality=window.signal_quality,
            method_agreement=estimate.method_agreement,
            temporal_stability=stability_score(
                [*tracker.recent_values, estimate.bpm], self._config.confidence.stability_tolerance_bpm
            ),
            missing_ratio=window.missing_ratio,
        )
        return compute_confidence(inputs, self._config.confidence)

    def _signal_quality_score(self, window: BVPWindow, snr_db: float | None) -> float:
        if window.signal_quality is not None:
            return window.signal_quality
        if snr_db is None:
            return 0.0
        return snr_to_score(snr_db, self._config.confidence)

    def _roi_heart_rates(self, window: BVPWindow) -> tuple[float, ...]:
        segment = window.tail(self._config.heart_rate.analysis_window_seconds)
        estimates = (
            self._heart_rate.estimate_spectral_bpm(samples, segment.sampling_rate_hz)
            for samples in segment.roi_samples.values()
        )
        return tuple(value for value in estimates if value is not None)

    @staticmethod
    def _track(tracker: TemporalTracker, candidate: VitalCandidate, outcome: ValidationOutcome) -> float | None:
        if candidate.value is None or outcome.status is ResultStatus.INVALID:
            return None
        tracked = tracker.update(candidate.value, candidate.timestamp)
        if outcome.status is ResultStatus.OK and not tracked.is_outlier:
            return tracked.smoothed
        return candidate.value

    def _full_window_beats(self, window: BVPWindow, estimate: HeartRateEstimate) -> BeatSeries | None:
        if estimate.bpm is None:
            return None
        return self._beat_extractor.extract(window.samples, window.sampling_rate_hz)

    def _hrv_vitals(
        self, window: BVPWindow, beats: BeatSeries | None, pulse_snr_db: float | None, heart_rate_confidence: float
    ) -> list[VitalValue]:
        estimate = self._hrv.estimate(beats, window.duration_seconds, pulse_snr_db)
        confidence = derive_hrv_confidence(heart_rate_confidence, estimate, self._config.hrv)
        measurement_window = build_measurement_window(window.start_timestamp, window.end_timestamp)
        return [
            self._validated_vital(window, code, value, confidence, estimate.failure_reason, measurement_window, HRVEstimator.algorithm)
            for code, value in hrv_values(estimate).items()
        ]

    def _respiratory_vital(
        self, window: BVPWindow, beats: BeatSeries | None, heart_rate_confidence: float, tracker: TemporalTracker
    ) -> VitalValue:
        estimate: RespiratoryRateEstimate = self._respiratory_rate.estimate(window, beats)
        confidence = derive_respiratory_confidence(
            heart_rate_confidence, estimate, self._config.respiratory_rate.max_component_spread_brpm
        )
        measurement_window = build_measurement_window(window.start_timestamp, window.end_timestamp)
        return self._validated_vital(
            window,
            VitalCode.RESPIRATORY_RATE,
            estimate.brpm,
            confidence,
            estimate.failure_reason,
            measurement_window,
            RespiratoryRateEstimator.algorithm,
            tracker,
        )

    def _validated_vital(
        self,
        window: BVPWindow,
        code: VitalCode,
        value: float | None,
        confidence: float,
        failure_reason: str | None,
        measurement_window,
        algorithm: AlgorithmInfo,
        tracker: TemporalTracker | None = None,
    ) -> VitalValue:
        candidate = VitalCandidate(
            code=code,
            value=value,
            timestamp=window.end_timestamp,
            confidence=confidence,
            window_duration_seconds=window.duration_seconds,
            signal_quality=window.signal_quality,
            missing_ratio=window.missing_ratio,
            failure_reason=failure_reason,
        )
        context = context_from_tracker(tracker) if tracker is not None else ValidationContext()
        outcome = self._validator.validate(candidate, context)
        reported = self._track(tracker, candidate, outcome) if tracker is not None else value
        quality = window.signal_quality if window.signal_quality is not None else confidence
        return build_vital_value(candidate, outcome, reported, quality, measurement_window, algorithm)
