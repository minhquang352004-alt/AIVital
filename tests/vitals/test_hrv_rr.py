import numpy as np
import pytest

from aivitals_engine.benchmark.synthetic import synthesize_bvp_window
from aivitals_engine.config.vitals_config import RespiratoryRateConfig
from aivitals_engine.contracts.bvp_window import BVPWindow
from aivitals_engine.vitals.beats import BeatExtractor, BeatSeries, successive_differences
from aivitals_engine.vitals.failures import ComputationFailure
from aivitals_engine.vitals.hrv import HRVEstimator
from aivitals_engine.vitals.rr import RespiratoryRateEstimator


def beat_series_from_intervals(ibi_ms, valid_mask=None) -> BeatSeries:
    ibi_ms = np.asarray(ibi_ms, dtype=float)
    times = np.concatenate([[0.0], np.cumsum(ibi_ms) / 1000.0])
    mask = np.ones(ibi_ms.size, dtype=bool) if valid_mask is None else np.asarray(valid_mask)
    return BeatSeries(times, np.ones(times.size), ibi_ms, times[1:], mask)


def test_hrv_time_domain_values_are_exact():
    intervals = np.array([800, 820, 790, 810, 805] * 8, dtype=float)
    estimate = HRVEstimator().estimate(beat_series_from_intervals(intervals), 40.0, pulse_snr_db=12.0)
    assert estimate.rmssd_ms == pytest.approx(np.sqrt(np.mean(np.diff(intervals) ** 2)))
    assert estimate.sdnn_ms == pytest.approx(np.std(intervals, ddof=1))
    assert estimate.mean_ibi_ms == pytest.approx(intervals.mean())
    assert estimate.artifact_ratio == 0.0


def test_hrv_requires_minimum_snr():
    estimate = HRVEstimator().estimate(beat_series_from_intervals([800] * 40), 40.0, pulse_snr_db=2.0)
    assert estimate.failure_reason is ComputationFailure.LOW_SIGNAL_TO_NOISE
    assert not estimate.is_available


def test_hrv_requires_long_window():
    estimate = HRVEstimator().estimate(beat_series_from_intervals([800] * 40), 20.0, pulse_snr_db=12.0)
    assert estimate.failure_reason is ComputationFailure.WINDOW_TOO_SHORT


def test_hrv_rejects_excessive_artifacts():
    mask = np.array([index % 10 >= 3 for index in range(40)])
    estimate = HRVEstimator().estimate(beat_series_from_intervals([800] * 40, mask), 40.0, pulse_snr_db=12.0)
    assert estimate.failure_reason is ComputationFailure.EXCESSIVE_ARTIFACTS


def test_successive_differences_skip_invalid_neighbours():
    intervals = np.array([800.0, 900.0, 400.0, 820.0])
    mask = np.array([True, True, False, True])
    assert successive_differences(intervals, mask).tolist() == [100.0]


@pytest.mark.parametrize("breaths", [10.0, 15.0, 20.0])
def test_respiratory_rate_accuracy(breaths):
    window, _ = synthesize_bvp_window(respiratory_rate_brpm=breaths, noise_std=0.1, seed=int(breaths))
    beats = BeatExtractor().extract(window.samples, window.sampling_rate_hz)
    estimate = RespiratoryRateEstimator().estimate(window, beats)
    assert estimate.failure_reason is None
    assert estimate.brpm == pytest.approx(breaths, abs=1.5)
    assert len(estimate.component_brpm) >= 2


def test_respiratory_rate_requires_long_window():
    window, _ = synthesize_bvp_window(duration_seconds=20.0)
    estimate = RespiratoryRateEstimator().estimate(window, None)
    assert estimate.failure_reason is ComputationFailure.WINDOW_TOO_SHORT


def test_respiratory_rate_rejects_disagreeing_components(clean_window):
    window, _ = clean_window
    beats = BeatExtractor().extract(window.samples, window.sampling_rate_hz)
    estimator = RespiratoryRateEstimator(RespiratoryRateConfig(max_component_spread_brpm=-1.0))
    estimate = estimator.estimate(window, beats)
    assert estimate.brpm is None
    assert estimate.failure_reason is ComputationFailure.RESPIRATORY_COMPONENTS_DISAGREE


def test_respiratory_rate_without_components():
    window = BVPWindow(samples=np.zeros(1200), sampling_rate_hz=30.0, start_timestamp=0.0, method="POS", method_version="1")
    estimate = RespiratoryRateEstimator().estimate(window, None)
    assert estimate.failure_reason is ComputationFailure.NO_RESPIRATORY_COMPONENT
