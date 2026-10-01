import pytest

from aivitals_engine.config.vitals_config import HRVConfig
from aivitals_engine.vitals.confidence import (
    ConfidenceInputs,
    compute_confidence,
    derive_hrv_confidence,
    derive_respiratory_confidence,
)
from aivitals_engine.vitals.hrv import HRVEstimate
from aivitals_engine.vitals.rr import RespiratoryRateEstimate
from aivitals_engine.vitals.tracker import TemporalTracker


def test_confidence_increases_with_snr():
    assert compute_confidence(ConfidenceInputs(snr_db=10.0)) > compute_confidence(ConfidenceInputs(snr_db=-5.0))


def test_missing_ratio_scales_confidence():
    complete = compute_confidence(ConfidenceInputs(snr_db=10.0, signal_quality=0.9))
    half_missing = compute_confidence(ConfidenceInputs(snr_db=10.0, signal_quality=0.9, missing_ratio=0.5))
    assert half_missing == pytest.approx(complete * 0.5)


def test_confidence_without_inputs_is_zero():
    assert compute_confidence(ConfidenceInputs()) == 0.0


def test_hrv_confidence_depends_on_snr():
    config = HRVConfig()
    unavailable = derive_hrv_confidence(0.9, HRVEstimate(), config)
    strong = HRVEstimate(rmssd_ms=40, sdnn_ms=35, mean_ibi_ms=800, clean_interval_count=40, artifact_ratio=0.0, pulse_snr_db=12.0)
    weak = HRVEstimate(rmssd_ms=40, sdnn_ms=35, mean_ibi_ms=800, clean_interval_count=40, artifact_ratio=0.0, pulse_snr_db=5.0)
    assert unavailable == 0.0
    assert derive_hrv_confidence(0.9, strong, config) > derive_hrv_confidence(0.9, weak, config)


def test_respiratory_confidence_rewards_agreement():
    agreeing = RespiratoryRateEstimate(brpm=15.0, component_brpm={"riav": 15.0, "rifv": 15.2, "riiv": 14.9}, component_spread_brpm=0.3)
    single = RespiratoryRateEstimate(brpm=15.0, component_brpm={"riav": 15.0}, component_spread_brpm=0.0)
    assert derive_respiratory_confidence(0.9, agreeing, 4.0) > derive_respiratory_confidence(0.9, single, 4.0)
    assert derive_respiratory_confidence(0.9, RespiratoryRateEstimate(), 4.0) == 0.0


def test_tracker_smooths_values():
    tracker = TemporalTracker()
    tracker.update(70.0, 1.0)
    tracked = tracker.update(74.0, 2.0)
    assert tracked.smoothed == pytest.approx(72.0)
    assert tracker.last_accepted == (2.0, pytest.approx(72.0))


def test_tracker_rejects_outlier_then_relocks():
    tracker = TemporalTracker()
    for timestamp, value in enumerate([70.0, 71.0, 70.0, 72.0]):
        tracker.update(value, float(timestamp))
    first = tracker.update(120.0, 5.0)
    second = tracker.update(120.0, 6.0)
    third = tracker.update(120.0, 7.0)
    assert first.is_outlier and second.is_outlier
    assert first.smoothed == second.smoothed
    assert not third.is_outlier
    assert third.smoothed == 120.0
    assert tracker.recent_values == (120.0,)
