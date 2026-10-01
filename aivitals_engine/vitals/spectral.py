from dataclasses import dataclass

import numpy as np

from aivitals_engine.config.vitals_config import FrequencyBand

EPSILON = 1e-12
MAIN_LOBE_FACTOR = 2.0
MIN_SAMPLES_FOR_SPECTRUM = 8
MIN_SNR_DB = -30.0
MAX_SNR_DB = 30.0


@dataclass(frozen=True)
class SpectralPeak:
    frequency_hz: float
    snr_db: float

    @property
    def per_minute(self) -> float:
        return self.frequency_hz * 60.0


def compute_power_spectrum(
    samples: np.ndarray, sampling_rate_hz: float, resolution_hz: float
) -> tuple[np.ndarray, np.ndarray]:
    sample_count = samples.size
    required_length = max(sample_count, sampling_rate_hz / resolution_hz)
    fft_length = int(2 ** np.ceil(np.log2(required_length)))
    tapered = (samples - np.mean(samples)) * np.hanning(sample_count)
    power = np.abs(np.fft.rfft(tapered, n=fft_length)) ** 2
    frequencies = np.fft.rfftfreq(fft_length, d=1.0 / sampling_rate_hz)
    return frequencies, power


def refine_peak_frequency(frequencies: np.ndarray, power: np.ndarray, peak_index: int) -> float:
    if peak_index <= 0 or peak_index >= power.size - 1:
        return float(frequencies[peak_index])
    left, center, right = power[peak_index - 1 : peak_index + 2]
    denominator = left - 2.0 * center + right
    if abs(denominator) < EPSILON:
        return float(frequencies[peak_index])
    offset = float(np.clip(0.5 * (left - right) / denominator, -0.5, 0.5))
    return float(frequencies[peak_index] + offset * (frequencies[1] - frequencies[0]))


def compute_snr_db(
    frequencies: np.ndarray, power: np.ndarray, band: FrequencyBand, fundamental_hz: float, tolerance_hz: float
) -> float:
    upper_limit_hz = min(2.0 * band.high_hz, float(frequencies[-1]))
    evaluation = (frequencies >= band.low_hz) & (frequencies <= upper_limit_hz)
    near_fundamental = np.abs(frequencies - fundamental_hz) <= tolerance_hz
    near_harmonic = np.abs(frequencies - 2.0 * fundamental_hz) <= tolerance_hz
    signal_mask = evaluation & (near_fundamental | near_harmonic)
    signal_power = float(np.sum(power[signal_mask]))
    noise_power = float(np.sum(power[evaluation & ~signal_mask]))
    if noise_power <= EPSILON:
        return MAX_SNR_DB
    if signal_power <= EPSILON:
        return MIN_SNR_DB
    return float(np.clip(10.0 * np.log10(signal_power / noise_power), MIN_SNR_DB, MAX_SNR_DB))


def find_subharmonic_index(
    frequencies: np.ndarray,
    power: np.ndarray,
    band: FrequencyBand,
    peak_index: int,
    tolerance_hz: float,
    power_ratio: float,
) -> int | None:
    half_frequency = frequencies[peak_index] / 2.0
    if half_frequency < band.low_hz:
        return None
    candidates = np.flatnonzero(np.abs(frequencies - half_frequency) <= tolerance_hz)
    if candidates.size == 0:
        return None
    best = int(candidates[np.argmax(power[candidates])])
    is_local_peak = 0 < best < power.size - 1 and power[best] >= power[best - 1] and power[best] >= power[best + 1]
    return best if is_local_peak and power[best] >= power_ratio * power[peak_index] else None


def find_spectral_peak(
    samples: np.ndarray,
    sampling_rate_hz: float,
    band: FrequencyBand,
    resolution_hz: float,
    tolerance_hz: float,
    subharmonic_power_ratio: float | None = None,
) -> SpectralPeak | None:
    samples = np.asarray(samples, dtype=float)
    if samples.size < MIN_SAMPLES_FOR_SPECTRUM:
        return None
    frequencies, power = compute_power_spectrum(samples, sampling_rate_hz, resolution_hz)
    band_indices = np.flatnonzero((frequencies >= band.low_hz) & (frequencies <= band.high_hz))
    if band_indices.size == 0 or np.sum(power[band_indices]) <= EPSILON:
        return None
    peak_index = int(band_indices[np.argmax(power[band_indices])])
    effective_tolerance = max(tolerance_hz, MAIN_LOBE_FACTOR * sampling_rate_hz / samples.size)
    if subharmonic_power_ratio is not None:
        subharmonic = find_subharmonic_index(
            frequencies, power, band, peak_index, effective_tolerance / 2.0, subharmonic_power_ratio
        )
        peak_index = peak_index if subharmonic is None else subharmonic
    frequency_hz = refine_peak_frequency(frequencies, power, peak_index)
    snr_db = compute_snr_db(frequencies, power, band, frequency_hz, effective_tolerance)
    return SpectralPeak(frequency_hz=frequency_hz, snr_db=snr_db)
