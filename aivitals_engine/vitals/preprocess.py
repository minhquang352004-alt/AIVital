import numpy as np
from scipy import signal as scipy_signal

from aivitals_engine.config.vitals_config import FrequencyBand

FILTER_ORDER = 3
NYQUIST_SAFETY_FACTOR = 0.99
EPSILON = 1e-12


def detrend_signal(samples: np.ndarray) -> np.ndarray:
    return scipy_signal.detrend(np.asarray(samples, dtype=float), type="linear")


def bandpass_filter(samples: np.ndarray, sampling_rate_hz: float, band: FrequencyBand) -> np.ndarray:
    samples = np.asarray(samples, dtype=float)
    nyquist_hz = sampling_rate_hz / 2.0
    high_hz = min(band.high_hz, nyquist_hz * NYQUIST_SAFETY_FACTOR)
    if band.low_hz >= high_hz:
        raise ValueError("Tần số lấy mẫu quá thấp so với dải tần cần lọc")
    sos = scipy_signal.butter(
        FILTER_ORDER, [band.low_hz / nyquist_hz, high_hz / nyquist_hz], btype="bandpass", output="sos"
    )
    if samples.size < 2:
        return samples.copy()
    padding = min(samples.size - 1, 3 * (2 * len(sos) + 1))
    return scipy_signal.sosfiltfilt(sos, samples, padlen=padding)


def standardize(samples: np.ndarray) -> np.ndarray:
    samples = np.asarray(samples, dtype=float)
    deviation = np.std(samples)
    if deviation < EPSILON:
        return np.zeros_like(samples)
    return (samples - np.mean(samples)) / deviation


def prepare_pulse_signal(samples: np.ndarray, sampling_rate_hz: float, band: FrequencyBand) -> np.ndarray:
    return standardize(bandpass_filter(detrend_signal(samples), sampling_rate_hz, band))
