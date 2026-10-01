from dataclasses import dataclass

import numpy as np

from aivitals_engine.config.vitals_config import HRVConfig
from aivitals_engine.contracts.result import AlgorithmInfo
from aivitals_engine.vitals.beats import BeatExtractor, BeatSeries, successive_differences
from aivitals_engine.vitals.failures import ComputationFailure

HRV_ALGORITHM = AlgorithmInfo(name="hrv_time_domain", version="0.2.0")
MIN_SUCCESSIVE_DIFFERENCES = 2


@dataclass(frozen=True)
class HRVEstimate:
    rmssd_ms: float | None = None
    sdnn_ms: float | None = None
    mean_ibi_ms: float | None = None
    clean_interval_count: int = 0
    artifact_ratio: float = 1.0
    pulse_snr_db: float | None = None
    failure_reason: ComputationFailure | None = None

    @property
    def is_available(self) -> bool:
        return self.rmssd_ms is not None


class HRVEstimator:
    algorithm = HRV_ALGORITHM

    def __init__(self, config: HRVConfig | None = None) -> None:
        self._config = config or HRVConfig()

    def estimate(
        self, beats: BeatSeries | None, window_duration_seconds: float, pulse_snr_db: float | None
    ) -> HRVEstimate:
        if window_duration_seconds < self._config.min_window_seconds:
            return HRVEstimate(pulse_snr_db=pulse_snr_db, failure_reason=ComputationFailure.WINDOW_TOO_SHORT)
        if pulse_snr_db is None or pulse_snr_db < self._config.min_pulse_snr_db:
            return HRVEstimate(pulse_snr_db=pulse_snr_db, failure_reason=ComputationFailure.LOW_SIGNAL_TO_NOISE)
        if beats is None:
            return HRVEstimate(pulse_snr_db=pulse_snr_db, failure_reason=ComputationFailure.INSUFFICIENT_BEATS)
        failure = self._check_beat_quality(beats)
        if failure is not None:
            return HRVEstimate(
                clean_interval_count=beats.clean_interval_count,
                artifact_ratio=beats.artifact_ratio,
                pulse_snr_db=pulse_snr_db,
                failure_reason=failure,
            )
        return self._compute(beats, pulse_snr_db)

    def _check_beat_quality(self, beats: BeatSeries) -> ComputationFailure | None:
        if beats.clean_interval_count < self._config.min_clean_intervals:
            return ComputationFailure.INSUFFICIENT_BEATS
        if beats.artifact_ratio > self._config.max_artifact_ratio:
            return ComputationFailure.EXCESSIVE_ARTIFACTS
        if successive_differences(beats.ibi_ms, beats.valid_mask).size < MIN_SUCCESSIVE_DIFFERENCES:
            return ComputationFailure.INSUFFICIENT_BEATS
        return None

    def _compute(self, beats: BeatSeries, pulse_snr_db: float) -> HRVEstimate:
        clean_ibi = beats.clean_ibi_ms
        differences = successive_differences(beats.ibi_ms, beats.valid_mask)
        return HRVEstimate(
            rmssd_ms=float(np.sqrt(np.mean(differences**2))),
            sdnn_ms=float(np.std(clean_ibi, ddof=1)),
            mean_ibi_ms=float(np.mean(clean_ibi)),
            clean_interval_count=beats.clean_interval_count,
            artifact_ratio=beats.artifact_ratio,
            pulse_snr_db=pulse_snr_db,
        )


PNN50_THRESHOLD_MS = 50.0
MIN_LEGACY_INTERVALS = 3
UNAVAILABLE_HRV = {"sdnn": float("nan"), "rmssd": float("nan"), "pnn50": float("nan"), "mean_ibi": float("nan")}


def extract_rr_intervals(bvp_signal: np.ndarray, fs: float = 30.0) -> np.ndarray:
    beats = BeatExtractor().extract(np.asarray(bvp_signal, dtype=float).ravel(), fs)
    return beats.clean_ibi_ms


def calculate_hrv_metrics(rr_intervals_ms: np.ndarray) -> dict[str, float]:
    intervals = np.asarray(rr_intervals_ms, dtype=float).ravel()
    if intervals.size < MIN_LEGACY_INTERVALS:
        return dict(UNAVAILABLE_HRV)
    differences = np.diff(intervals)
    return {
        "sdnn": float(np.std(intervals, ddof=1)),
        "rmssd": float(np.sqrt(np.mean(differences**2))),
        "pnn50": float(100.0 * np.mean(np.abs(differences) > PNN50_THRESHOLD_MS)),
        "mean_ibi": float(np.mean(intervals)),
    }


def calculate_hrv_from_bvp(bvp_signal: np.ndarray, fs: float = 30.0) -> dict[str, float]:
    return calculate_hrv_metrics(extract_rr_intervals(bvp_signal, fs))
