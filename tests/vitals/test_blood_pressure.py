import numpy as np
import pytest

from aivitals_engine.contracts.result import ResultStatus, VitalCode
from aivitals_engine.integration.vitals_service import VitalsService
from aivitals_engine.models.blood_pressure import (
    BP_FEATURE_NAMES,
    BloodPressureUse,
    ModelNotFittedError,
    RidgeBloodPressureModel,
    evaluate_blood_pressure,
    evaluate_data_sufficiency,
    extract_vital_features,
    file_sha256,
    subject_independent_cross_validation,
)
from aivitals_engine.models.blood_pressure.evaluation import pressure_error_stats
from aivitals_engine.validation.issue_codes import IssueCode


def make_dataset(subject_count: int = 30, samples_per_subject: int = 4, seed: int = 0):
    rng = np.random.default_rng(seed)
    sample_count = subject_count * samples_per_subject
    features = rng.normal(size=(sample_count, len(BP_FEATURE_NAMES)))
    subjects = np.repeat(np.arange(subject_count), samples_per_subject)
    offsets = rng.normal(0, 3, subject_count)[subjects]
    systolic = 120 + 8 * features[:, 0] + 5 * features[:, 10] + offsets + rng.normal(0, 2, sample_count)
    diastolic = 78 + 4 * features[:, 0] + 3 * features[:, 10] + 0.5 * offsets + rng.normal(0, 1.5, sample_count)
    return features, np.column_stack([systolic, diastolic]), subjects


def as_mapping(row: np.ndarray) -> dict[str, float]:
    return {name: float(value) for name, value in zip(BP_FEATURE_NAMES, row)}


@pytest.fixture(scope="module")
def trained():
    features, targets, subjects = make_dataset()
    return RidgeBloodPressureModel().fit(features, targets), features, targets, subjects


def test_baseline_predicts_research_only_estimate(trained):
    model, features, targets, _ = trained
    estimate = model.predict(as_mapping(features[0]))
    assert estimate.status is ResultStatus.OK
    assert estimate.intended_use is BloodPressureUse.RESEARCH_ONLY
    assert abs(estimate.sbp_mmhg - targets[0, 0]) < 10
    assert 0 < estimate.confidence <= 1


def test_missing_features(trained):
    model, features, _, _ = trained
    mapping = as_mapping(features[0])
    too_few = model.predict({name: mapping[name] for name in BP_FEATURE_NAMES[:2]})
    assert too_few.status is ResultStatus.INVALID and too_few.sbp_mmhg is None
    assert too_few.issues[0].code == IssueCode.MISSING_FEATURES
    partial = model.predict({**mapping, "bmi": None})
    assert partial.status is ResultStatus.BAD
    assert partial.missing_features == ["bmi"]


def test_features_outside_training_range_are_clipped(trained):
    model, features, _, _ = trained
    extreme = features[0].copy()
    extreme[0] = 50.0
    estimate = model.predict(as_mapping(extreme))
    assert estimate.status is ResultStatus.BAD
    assert IssueCode.FEATURES_OUT_OF_TRAINING_RANGE in [issue.code for issue in estimate.issues]
    assert 70.0 <= estimate.sbp_mmhg <= 220.0


def test_out_of_range_prediction_is_invalid():
    features, targets, _ = make_dataset()
    model = RidgeBloodPressureModel().fit(features, targets + np.array([150.0, 0.0]))
    estimate = model.predict(as_mapping(features[0]))
    assert estimate.status is ResultStatus.INVALID and estimate.sbp_mmhg is None
    assert IssueCode.OUT_OF_PHYSIOLOGICAL_RANGE in [issue.code for issue in estimate.issues]


def test_model_guards_and_persistence(trained, tmp_path):
    model, features, targets, _ = trained
    with pytest.raises(ModelNotFittedError):
        RidgeBloodPressureModel().predict(as_mapping(features[0]))
    with pytest.raises(ValueError):
        RidgeBloodPressureModel().fit(features[:, :3], targets)
    path = model.save(tmp_path / "bp.joblib")
    checksum = file_sha256(path)
    restored = RidgeBloodPressureModel.load(path, checksum_sha256=checksum)
    assert np.allclose(restored.predict_matrix(features[:5]), model.predict_matrix(features[:5]))
    assert restored.model_info.checksum_sha256 == checksum
    with pytest.raises(ValueError):
        RidgeBloodPressureModel.load(path, checksum_sha256="b" * 64)


def test_error_stats_and_grades():
    reference = np.full(50, 120.0)
    good = pressure_error_stats(reference, reference + 2.0)
    poor = pressure_error_stats(reference, reference + np.linspace(-25, 25, 50))
    assert good.mean_absolute_error == pytest.approx(2.0)
    assert good.bhs_grade == "A" and good.meets_aami
    assert poor.bhs_grade == "D" and not poor.meets_aami
    with pytest.raises(ValueError):
        evaluate_blood_pressure(np.zeros((3, 2)), np.zeros((3, 3)))


def test_subject_independent_cross_validation():
    features, targets, subjects = make_dataset()
    report = subject_independent_cross_validation(RidgeBloodPressureModel, features, targets, subjects, n_splits=5)
    assert len(report.folds) == 5
    assert report.subject_count == 30
    assert report.pooled.systolic.mean_absolute_error < 6
    with pytest.raises(ValueError):
        subject_independent_cross_validation(RidgeBloodPressureModel, features, targets, subjects % 3, n_splits=5)


def test_gate_rejects_small_dataset():
    _, targets, subjects = make_dataset()
    decision = evaluate_data_sufficiency(targets, subjects)
    assert not decision.passed
    assert decision.subject_count == 30
    assert decision.reasons


def test_gate_accepts_representative_dataset():
    systolic = np.array([95.0] * 6 + [165.0] * 6 + [145.0] * 20 + [120.0] * 68)
    diastolic = np.array([55.0] * 6 + [105.0] * 6 + [88.0] * 20 + [75.0] * 68)
    per_subject = np.column_stack([systolic, diastolic])
    targets = np.repeat(per_subject, 3, axis=0)
    subjects = np.repeat(np.arange(100), 3)
    decision = evaluate_data_sufficiency(targets, subjects)
    assert decision.passed, decision.reasons


def test_extract_vital_features(clean_window, fixed_clock):
    window, _ = clean_window
    result = VitalsService(clock=fixed_clock).compute(window, "bp-features")
    features = extract_vital_features(result)
    accepted = {vital.code for vital in result.accepted_vitals()}
    assert (VitalCode.HEART_RATE in accepted) == ("heart_rate_bpm" in features)
    assert set(features) <= set(BP_FEATURE_NAMES)
