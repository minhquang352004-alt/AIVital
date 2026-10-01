from collections.abc import Mapping
from dataclasses import dataclass, field, replace

import numpy as np

from aivitals_engine.config.vitals_config import FrequencyBand, RespiratoryRateConfig
from aivitals_engine.contracts.bvp_window import BVPWindow
from aivitals_engine.contracts.result import AlgorithmInfo
from aivitals_engine.vitals.beats import BeatExtractor, BeatSeries
from aivitals_engine.vitals.failures import ComputationFailure
from aivitals_engine.vitals.preprocess import bandpass_filter, detrend_signal
from aivitals_engine.vitals.spectral import find_spectral_peak

RESPIRATORY_RATE_ALGORITHM = AlgorithmInfo(name="rr_modulation_fusion", version="0.1.0")
COMPONENT_AMPLITUDE = "riav"
COMPONENT_FREQUENCY = "rifv"
COMPONENT_INTENSITY = "riiv"
MIN_RESAMPLED_POINTS = 16


@dataclass(frozen=True)
class RespiratoryRateEstimate:
    brpm: float | None = None
    component_brpm: Mapping[str, float] = field(default_factory=dict)
    component_spread_brpm: float | None = None
    failure_reason: ComputationFailure | None = None


class RespiratoryRateEstimator:
    algorithm = RESPIRATORY_RATE_ALGORITHM

    def __init__(self, config: RespiratoryRateConfig | None = None) -> None:
        self._config = config or RespiratoryRateConfig()

    def estimate(self, window: BVPWindow, beats: BeatSeries | None) -> RespiratoryRateEstimate:
        if window.duration_seconds < self._config.min_window_seconds:
            return RespiratoryRateEstimate(failure_reason=ComputationFailure.WINDOW_TOO_SHORT)
        components = self._component_estimates(window, beats)
        if not components:
            return RespiratoryRateEstimate(failure_reason=ComputationFailure.NO_RESPIRATORY_COMPONENT)
        values = np.array(list(components.values()))
        spread = float(np.ptp(values))
        if spread > self._config.max_component_spread_brpm:
            return RespiratoryRateEstimate(
                component_brpm=components,
                component_spread_brpm=spread,
                failure_reason=ComputationFailure.RESPIRATORY_COMPONENTS_DISAGREE,
            )
        return RespiratoryRateEstimate(brpm=float(np.median(values)), component_brpm=components, component_spread_brpm=spread)

    def _component_estimates(self, window: BVPWindow, beats: BeatSeries | None) -> dict[str, float]:
        estimates: dict[str, float | None] = {}
        if beats is not None and beats.clean_interval_count >= self._config.min_beats_for_modulation:
            estimates[COMPONENT_AMPLITUDE] = self._rate_from_series(beats.peak_times_s, beats.peak_amplitudes)
            estimates[COMPONENT_FREQUENCY] = self._rate_from_series(beats.clean_ibi_times_s, beats.clean_ibi_ms)
        if window.raw_samples is not None:
            estimates[COMPONENT_INTENSITY] = self._rate_from_raw(window.raw_samples, window.sampling_rate_hz)
        return {name: value for name, value in estimates.items() if value is not None}

    def _rate_from_series(self, times_s: np.ndarray, values: np.ndarray) -> float | None:
        if times_s.size < self._config.min_beats_for_modulation:
            return None
        uniform_times = np.arange(times_s[0], times_s[-1], 1.0 / self._config.resample_hz)
        if uniform_times.size < MIN_RESAMPLED_POINTS:
            return None
        resampled = np.interp(uniform_times, times_s, values)
        return self._dominant_rate(detrend_signal(resampled), self._config.resample_hz)

    def _rate_from_raw(self, raw_samples: np.ndarray, sampling_rate_hz: float) -> float | None:
        filtered = bandpass_filter(detrend_signal(raw_samples), sampling_rate_hz, self._config.band)
        return self._dominant_rate(filtered, sampling_rate_hz)

    def _dominant_rate(self, samples: np.ndarray, sampling_rate_hz: float) -> float | None:
        peak = find_spectral_peak(
            samples,
            sampling_rate_hz,
            self._config.band,
            self._config.spectral_resolution_hz,
            self._config.snr_tolerance_hz,
        )
        return None if peak is None else peak.per_minute


def calculate_respiration_rate(
    bvp_signal: np.ndarray,
    fs: float = 30.0,
    low_cutoff_hz: float = 0.10,
    high_cutoff_hz: float = 0.50,
    raw_signal: np.ndarray | None = None,
) -> float:
    samples = np.asarray(bvp_signal, dtype=float).ravel()
    window = BVPWindow(
        samples=samples,
        sampling_rate_hz=fs,
        start_timestamp=0.0,
        method="LEGACY",
        method_version="1.0",
        raw_samples=None if raw_signal is None else np.asarray(raw_signal, dtype=float).ravel(),
    )
    config = replace(RespiratoryRateConfig(), band=FrequencyBand(low_cutoff_hz, high_cutoff_hz))
    beats = BeatExtractor().extract(samples, fs)
    estimate = RespiratoryRateEstimator(config).estimate(window, beats)
    return 0.0 if estimate.brpm is None else estimate.brpm
