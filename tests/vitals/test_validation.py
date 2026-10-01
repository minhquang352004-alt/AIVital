from aivitals_engine.contracts.result import ResultStatus, VitalCode
from aivitals_engine.validation import IssueCode, ValidationContext, VitalCandidate, VitalValidator
from aivitals_engine.validation.rules import ComputationRule

validator = VitalValidator()


def candidate(**overrides) -> VitalCandidate:
    values = dict(
        code=VitalCode.HEART_RATE,
        value=72.0,
        timestamp=1000.0,
        confidence=0.9,
        window_duration_seconds=10.0,
        signal_quality=0.9,
        missing_ratio=0.0,
    )
    values.update(overrides)
    return VitalCandidate(**values)


def test_good_result_is_ok():
    outcome = validator.validate(candidate())
    assert outcome.status is ResultStatus.OK
    assert outcome.issues == ()
    assert outcome.is_accepted


def test_low_quality_result_is_bad():
    outcome = validator.validate(candidate(signal_quality=0.5))
    assert outcome.status is ResultStatus.BAD
    assert outcome.issue_codes() == [IssueCode.SIGNAL_QUALITY_LOW]


def test_unusable_quality_is_invalid():
    outcome = validator.validate(candidate(signal_quality=0.2))
    assert outcome.status is ResultStatus.INVALID
    assert not outcome.is_accepted


def test_missing_value_is_invalid():
    outcome = validator.validate(candidate(value=None, confidence=0.0, failure_reason="NO_SPECTRAL_PEAK"))
    assert outcome.status is ResultStatus.INVALID
    assert outcome.issues[0].code == IssueCode.COMPUTATION_FAILED
    assert outcome.issues[0].details["reason"] == "NO_SPECTRAL_PEAK"


def test_out_of_range_heart_rate_is_invalid():
    outcome = validator.validate(candidate(value=220.0))
    assert outcome.status is ResultStatus.INVALID
    assert IssueCode.OUT_OF_PHYSIOLOGICAL_RANGE in outcome.issue_codes()


def test_sudden_jump_is_bad():
    context = ValidationContext(previous_value=70.0, previous_timestamp=999.0)
    outcome = validator.validate(candidate(value=100.0), context)
    assert outcome.status is ResultStatus.BAD
    assert outcome.issue_codes() == [IssueCode.SUDDEN_JUMP]


def test_gradual_change_is_ok():
    context = ValidationContext(previous_value=70.0, previous_timestamp=990.0)
    assert validator.validate(candidate(value=90.0), context).status is ResultStatus.OK


def test_short_window_is_invalid():
    outcome = validator.validate(candidate(code=VitalCode.HRV_RMSSD, value=40.0, window_duration_seconds=20.0))
    assert outcome.status is ResultStatus.INVALID
    assert IssueCode.WINDOW_TOO_SHORT in outcome.issue_codes()


def test_missing_window_data():
    assert validator.validate(candidate(missing_ratio=0.2)).status is ResultStatus.BAD
    assert validator.validate(candidate(missing_ratio=0.4)).status is ResultStatus.INVALID


def test_cross_roi_inconsistency_is_bad():
    outcome = validator.validate(candidate(roi_values=(72.0, 95.0, 60.0)))
    assert outcome.issue_codes() == [IssueCode.CROSS_ROI_INCONSISTENT]


def test_temporal_instability_is_bad():
    outcome = validator.validate(candidate(value=95.0), ValidationContext(recent_values=(60.0, 90.0, 62.0)))
    assert outcome.issue_codes() == [IssueCode.TEMPORAL_UNSTABLE]


def test_confidence_thresholds():
    assert validator.validate(candidate(confidence=0.5)).status is ResultStatus.BAD
    assert validator.validate(candidate(confidence=0.2)).status is ResultStatus.INVALID


def test_custom_rules_are_supported():
    custom = VitalValidator(rules=[ComputationRule()])
    assert custom.validate(candidate(value=500.0)).status is ResultStatus.OK
    assert len(custom.rules) == 1
