from dataclasses import replace

import numpy as np
import pytest

from aivitals_engine.contracts.bvp_window import BVPWindow
from aivitals_engine.contracts.result import ResultStatus, VitalCode
from aivitals_engine.integration.vitals_service import VitalsService
from aivitals_engine.validation import VitalCandidate, VitalValidator
from aivitals_engine.validation.issue_codes import IssueCode
from aivitals_engine.vitals.failures import ComputationFailure

FS = 30.0


def window_of(samples, sampling_rate_hz=FS, **overrides) -> BVPWindow:
    return BVPWindow(
        samples=samples,
        sampling_rate_hz=sampling_rate_hz,
        start_timestamp=0.0,
        method="POS",
        method_version="1.0",
        **overrides,
    )


def failure_reason(vital) -> str | None:
    for issue in vital.issues:
        if issue.code == IssueCode.COMPUTATION_FAILED:
            return issue.details.get("reason")
    return None


DEGENERATE_SIGNALS = {
    "zeros": np.zeros(900),
    "constant": np.full(900, 5.0),
    "single_sample": np.array([1.0]),
    "five_samples": np.arange(5, dtype=float),
    "step": np.r_[np.zeros(450), np.ones(450)],
    "empty": np.array([], dtype=float),
}


@pytest.mark.parametrize("name", sorted(DEGENERATE_SIGNALS))
def test_degenerate_signal_is_invalid_without_crash(name):
    result = VitalsService().compute(window_of(DEGENERATE_SIGNALS[name]), f"degenerate-{name}")
    assert result.status is ResultStatus.INVALID
    assert all(vital.value is None for vital in result.vitals)
    assert {vital.code for vital in result.vitals} == set(VitalCode)


@pytest.mark.parametrize("sampling_rate_hz", [1.0, 2.0, 5.0, 10.0, 14.9])
def test_low_sampling_rate_is_rejected(sampling_rate_hz):
    samples = np.random.default_rng(3).normal(size=int(sampling_rate_hz * 40))
    result = VitalsService().compute(window_of(samples, sampling_rate_hz), "low-fs")
    heart_rate = result.find_vital(VitalCode.HEART_RATE)
    respiratory = result.find_vital(VitalCode.RESPIRATORY_RATE)
    assert result.status is ResultStatus.INVALID
    assert failure_reason(heart_rate) == ComputationFailure.SAMPLING_RATE_TOO_LOW
    assert failure_reason(respiratory) == ComputationFailure.SAMPLING_RATE_TOO_LOW


def test_sampling_rate_at_minimum_still_computes(clean_window):
    window, _ = clean_window
    resampled = np.interp(np.arange(0, window.duration_seconds, 1 / 15.0), np.arange(window.samples.size) / FS, window.samples)
    result = VitalsService().compute(window_of(resampled, 15.0, signal_quality=0.85), "fs-15")
    assert result.find_vital(VitalCode.HEART_RATE).value is not None


def test_amplitude_scale_does_not_change_heart_rate(clean_window):
    window, _ = clean_window
    service = VitalsService()
    reference = service.compute(window, "scale-1").find_vital(VitalCode.HEART_RATE)
    for scale in (1e-6, 1e6):
        scaled = service.compute(replace(window, samples=window.samples * scale, raw_samples=None), f"scale-{scale}")
        assert scaled.find_vital(VitalCode.HEART_RATE).value == pytest.approx(reference.value, abs=0.5)


def test_non_finite_samples_are_rejected_by_contract():
    with pytest.raises(ValueError):
        window_of(np.array([1.0, np.nan, 2.0]))
    with pytest.raises(ValueError):
        window_of(np.zeros((10, 3)))
    with pytest.raises(ValueError):
        window_of(np.zeros(300), sampling_rate_hz=0.0)


def test_blocking_signal_warning_marks_vitals_bad(clean_window):
    window, _ = clean_window
    result = VitalsService().compute(replace(window, signal_warnings=("MOTION_HIGH", "LOW_SNR")), "motion")
    heart_rate = result.find_vital(VitalCode.HEART_RATE)
    assert heart_rate.status is ResultStatus.BAD
    assert [issue.code for issue in heart_rate.issues] == [IssueCode.SIGNAL_CONDITION_BLOCKING]
    assert heart_rate.issues[0].details == {"signal_warnings": "MOTION_HIGH"}


def test_non_blocking_warnings_do_not_change_status(clean_window):
    window, _ = clean_window
    result = VitalsService().compute(replace(window, signal_warnings=("TOO_DARK", "LOW_FPS", "UNKNOWN_CODE")), "dark")
    assert result.find_vital(VitalCode.HEART_RATE).status is ResultStatus.OK


def test_signal_warnings_are_normalized_to_strings():
    window = window_of(np.zeros(300), signal_warnings=["MOTION_HIGH"])
    assert window.signal_warnings == ("MOTION_HIGH",)
    assert window.tail(5.0).signal_warnings == ("MOTION_HIGH",)


def test_signal_condition_rule_ignores_missing_value():
    candidate = VitalCandidate(
        code=VitalCode.HEART_RATE,
        value=None,
        timestamp=1.0,
        confidence=0.0,
        window_duration_seconds=10.0,
        signal_warnings=("FACE_NOT_FOUND",),
    )
    issues = VitalValidator().validate(candidate).issue_codes()
    assert IssueCode.SIGNAL_CONDITION_BLOCKING not in issues


def test_session_state_is_isolated_between_sessions(clean_window):
    window, _ = clean_window
    service = VitalsService()
    service.compute(window, "first")
    service.compute(window, "second")
    assert service.active_sessions() == ["first", "second"]
    assert service.reset_session("first")
    assert not service.reset_session("first")
    assert service.active_sessions() == ["second"]
