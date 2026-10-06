import numpy as np
import pytest

from aivitals_engine.benchmark.synthetic import synthesize_bvp_window
from aivitals_engine.config.vitals_config import FrequencyBand
from aivitals_engine.contracts.bvp_window import BVPWindow
from aivitals_engine.vitals.beats import BeatExtractor
from aivitals_engine.vitals.failures import ComputationFailure
from aivitals_engine.vitals.hr import HeartRateEstimator
from aivitals_engine.vitals.spectral import find_spectral_peak

PULSE_BAND = FrequencyBand(0.7, 3.0)


def sine(frequency_hz: float, seconds: float = 20.0, sampling_rate_hz: float = 30.0, noise: float = 0.0) -> np.ndarray:
    times = np.arange(int(seconds * sampling_rate_hz)) / sampling_rate_hz
    rng = np.random.default_rng(0)
    return np.sin(2 * np.pi * frequency_hz * times) + rng.normal(0.0, noise, times.size)


def test_spectral_peak_locates_frequency():
    peak = find_spectral_peak(sine(1.2), 30.0, PULSE_BAND, 0.005, 0.1)
    assert peak.per_minute == pytest.approx(72.0, abs=0.5)


def test_snr_drops_with_noise():
    clean = find_spectral_peak(sine(1.2), 30.0, PULSE_BAND, 0.005, 0.1)
    noisy = find_spectral_peak(sine(1.2, noise=3.0), 30.0, PULSE_BAND, 0.005, 0.1)
    assert clean.snr_db > noisy.snr_db


def test_dominant_harmonic_resolves_to_fundamental():
    times = np.arange(300) / 30.0
    samples = 0.8 * np.sin(2 * np.pi * 0.9 * times) + np.sin(2 * np.pi * 1.8 * times)
    naive = find_spectral_peak(samples, 30.0, PULSE_BAND, 0.005, 0.1)
    resolved = find_spectral_peak(samples, 30.0, PULSE_BAND, 0.005, 0.1, subharmonic_power_ratio=0.5)
    assert naive.per_minute == pytest.approx(108.0, abs=1.0)
    assert resolved.per_minute == pytest.approx(54.0, abs=1.0)


def test_subharmonic_check_keeps_true_high_rate():
    peak = find_spectral_peak(sine(1.8), 30.0, PULSE_BAND, 0.005, 0.1, subharmonic_power_ratio=0.5)
    assert peak.per_minute == pytest.approx(108.0, abs=0.5)


def test_spectral_peak_returns_none_for_flat_signal():
    assert find_spectral_peak(np.zeros(300), 30.0, PULSE_BAND, 0.005, 0.1) is None


@pytest.mark.parametrize("bpm", [50.0, 72.0, 110.0, 150.0])
def test_heart_rate_estimator_accuracy(bpm):
    window, recording = synthesize_bvp_window(heart_rate_bpm=bpm, noise_std=0.2, seed=int(bpm))
    estimate = HeartRateEstimator().estimate(window)
    end = window.duration_seconds
    reference = recording.reference_heart_rate(end - estimate.analysed_seconds, end)
    assert estimate.failure_reason is None
    assert estimate.bpm == pytest.approx(reference, abs=3.0)
    assert estimate.snr_db > 0


def test_heart_rate_rejects_short_window():
    window, _ = synthesize_bvp_window(duration_seconds=4.0)
    estimate = HeartRateEstimator().estimate(window)
    assert estimate.bpm is None
    assert estimate.failure_reason is ComputationFailure.WINDOW_TOO_SHORT


def test_heart_rate_flat_signal_has_no_peak():
    window = BVPWindow(samples=np.zeros(600), sampling_rate_hz=30.0, start_timestamp=0.0, method="POS", method_version="1")
    estimate = HeartRateEstimator().estimate(window)
    assert estimate.failure_reason is ComputationFailure.NO_SPECTRAL_PEAK


def test_beat_extractor_matches_reference_intervals(clean_window):
    window, recording = clean_window
    beats = BeatExtractor().extract(window.samples, window.sampling_rate_hz)
    reference = recording.beat_intervals_between(0.0, window.duration_seconds)
    assert beats.artifact_ratio < 0.1
    assert beats.clean_ibi_ms.mean() == pytest.approx(reference.mean(), rel=0.02)


def test_beat_extractor_flags_missing_beat():
    sampling_rate = 30.0
    positions = [12 + 24 * index for index in range(36) if index != 15]
    samples = np.arange(int(30 * sampling_rate))
    prepared = sum(np.exp(-0.5 * ((samples - position) / 2.0) ** 2) for position in positions)
    beats = BeatExtractor().extract_from_prepared(prepared, sampling_rate)
    assert beats.ibi_ms.size == len(positions) - 1
    assert beats.clean_interval_count == beats.ibi_ms.size - 1
    assert beats.clean_ibi_ms == pytest.approx(np.full(beats.clean_interval_count, 800.0), abs=1.0)
