from dataclasses import dataclass

import numpy as np
from scipy.ndimage import median_filter
from scipy.signal import find_peaks

from aivitals_engine.config.vitals_config import BeatDetectionConfig
from aivitals_engine.vitals.preprocess import prepare_pulse_signal
from aivitals_engine.vitals.spectral import find_spectral_peak

EPSILON = 1e-12
BEAT_SPECTRAL_RESOLUTION_HZ = 0.01
BEAT_SNR_TOLERANCE_HZ = 0.1


@dataclass(frozen=True)
class BeatSeries:
    peak_times_s: np.ndarray
    peak_amplitudes: np.ndarray
    ibi_ms: np.ndarray
    ibi_times_s: np.ndarray
    valid_mask: np.ndarray

    @property
    def clean_ibi_ms(self) -> np.ndarray:
        return self.ibi_ms[self.valid_mask]

    @property
    def clean_ibi_times_s(self) -> np.ndarray:
        return self.ibi_times_s[self.valid_mask]

    @property
    def clean_interval_count(self) -> int:
        return int(np.count_nonzero(self.valid_mask))

    @property
    def artifact_ratio(self) -> float:
        if self.ibi_ms.size == 0:
            return 1.0
        return 1.0 - self.clean_interval_count / self.ibi_ms.size


def refine_peak_positions(samples: np.ndarray, indices: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    positions = indices.astype(float)
    amplitudes = samples[indices].astype(float)
    interior = (indices > 0) & (indices < samples.size - 1)
    inner = indices[interior]
    left, center, right = samples[inner - 1], samples[inner], samples[inner + 1]
    denominator = left - 2.0 * center + right
    offsets = np.zeros(inner.size, dtype=float)
    safe = np.abs(denominator) > EPSILON
    offsets[safe] = 0.5 * (left[safe] - right[safe]) / denominator[safe]
    offsets = np.clip(offsets, -0.5, 0.5)
    positions[interior] += offsets
    amplitudes[interior] = center - 0.25 * (left - right) * offsets
    return positions, amplitudes


def successive_differences(ibi_ms: np.ndarray, valid_mask: np.ndarray) -> np.ndarray:
    if ibi_ms.size < 2:
        return np.zeros(0, dtype=float)
    adjacent_valid = valid_mask[1:] & valid_mask[:-1]
    return np.diff(ibi_ms)[adjacent_valid]


class BeatExtractor:
    def __init__(self, config: BeatDetectionConfig | None = None) -> None:
        self._config = config or BeatDetectionConfig()

    def extract(self, samples: np.ndarray, sampling_rate_hz: float) -> BeatSeries:
        prepared = prepare_pulse_signal(samples, sampling_rate_hz, self._config.pulse_band)
        return self.extract_from_prepared(prepared, sampling_rate_hz)

    def extract_from_prepared(self, prepared: np.ndarray, sampling_rate_hz: float) -> BeatSeries:
        min_distance = self._minimum_peak_distance(prepared, sampling_rate_hz)
        indices, _ = find_peaks(prepared, distance=min_distance, prominence=self._config.min_prominence)
        positions, amplitudes = refine_peak_positions(prepared, indices)
        peak_times = positions / sampling_rate_hz
        ibi_ms = np.diff(peak_times) * 1000.0
        return BeatSeries(
            peak_times_s=peak_times,
            peak_amplitudes=amplitudes,
            ibi_ms=ibi_ms,
            ibi_times_s=peak_times[1:],
            valid_mask=self._mark_valid_intervals(ibi_ms),
        )

    def _minimum_peak_distance(self, prepared: np.ndarray, sampling_rate_hz: float) -> int:
        shortest_period = sampling_rate_hz * 60.0 / self._config.max_bpm
        peak = find_spectral_peak(
            prepared,
            sampling_rate_hz,
            self._config.pulse_band,
            BEAT_SPECTRAL_RESOLUTION_HZ,
            BEAT_SNR_TOLERANCE_HZ,
            self._config.subharmonic_power_ratio,
        )
        if peak is None:
            return max(1, int(shortest_period))
        expected_period = sampling_rate_hz / peak.frequency_hz
        return max(1, int(max(shortest_period, self._config.expected_period_fraction * expected_period)))

    def _mark_valid_intervals(self, ibi_ms: np.ndarray) -> np.ndarray:
        if ibi_ms.size == 0:
            return np.zeros(0, dtype=bool)
        in_range = (ibi_ms >= self._config.min_ibi_ms) & (ibi_ms <= self._config.max_ibi_ms)
        kernel = min(self._config.local_median_kernel, ibi_ms.size)
        local_median = median_filter(ibi_ms, size=kernel, mode="nearest")
        near_local = np.abs(ibi_ms - local_median) <= self._config.local_median_tolerance * local_median
        return in_range & near_local
