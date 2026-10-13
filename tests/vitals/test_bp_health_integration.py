import ast
from pathlib import Path

import numpy as np
import pytest

from aivitals_engine.benchmark.bp_dataset import (
    generate_synthetic_bp_dataset,
    load_bp_dataset_csv,
    write_bp_dataset_csv,
)
from aivitals_engine.benchmark.synthetic import SyntheticScenario, generate_recording
from aivitals_engine.contracts.result import ResultStatus
from aivitals_engine.features import BVPFeatureExtractor, BVPFeatures
from aivitals_engine.health import BloodPressureRiskModel, EvidenceLevel, RiskCategory, classify_blood_pressure
from aivitals_engine.health.bp_risk import blood_pressure_score
from aivitals_engine.integration.bp_service import BloodPressureService
from aivitals_engine.integration.realtime_vitals import RealtimeVitalsConfig, RealtimeVitalsEngine
from aivitals_engine.integration.vitals_service import VitalsService
from aivitals_engine.models.blood_pressure import (
    BP_FEATURE_NAMES,
    Demographics,
    RidgeBloodPressureModel,
    build_bp_features,
    build_feature_vector,
    extract_bvp_features,
)
from tests.vitals.test_team_integration import ReplayPipeline, replay

ENGINE_ROOT = Path(__file__).resolve().parents[2] / "aivitals_engine"
FORBIDDEN_IMPORTS = {"openai", "httpx", "requests"}


@pytest.fixture(scope="module")
def synthetic_dataset():
    return generate_synthetic_bp_dataset(subject_count=60, seed=3)


@pytest.fixture(scope="module")
def trained_model(synthetic_dataset):
    return RidgeBloodPressureModel().fit(synthetic_dataset.features, synthetic_dataset.targets)


@pytest.fixture(scope="module")
def pipeline_inputs(clean_window):
    window, _ = clean_window
    result = VitalsService().compute(window, "bp-pipeline")
    features = BVPFeatureExtractor().extract(window.samples, window.sampling_rate_hz)
    return result, features


def test_feature_set_combines_vitals_khang_features_and_demographics():
    assert len(BP_FEATURE_NAMES) == 5 + BVPFeatures.feature_dim() + 3
    assert BP_FEATURE_NAMES[5 : 5 + BVPFeatures.feature_dim()] == tuple(BVPFeatures.feature_names())
    assert len(set(BP_FEATURE_NAMES)) == len(BP_FEATURE_NAMES)


def test_demographics_bmi():
    assert Demographics(height_cm=170, weight_kg=72.25).bmi == pytest.approx(25.0)
    assert Demographics(age_years=40).to_features() == {"age_years": 40, "sex_male": None, "bmi": None}


def test_build_features_from_real_pipeline(pipeline_inputs):
    result, bvp_features = pipeline_inputs
    features = build_bp_features(result, bvp_features, Demographics(age_years=45, sex_male=True, height_cm=172, weight_kg=70))
    assert set(features) == set(BP_FEATURE_NAMES)
    assert features["sex_male"] == 1.0
    assert features["mean_rise_time_ms"] == extract_bvp_features(bvp_features)["mean_rise_time_ms"]
    vector = build_feature_vector(features)
    assert vector.missing_ratio < 0.3


def test_nan_bvp_features_become_missing():
    features = extract_bvp_features(BVPFeatures())
    assert all(value is None for value in features.values())


def test_service_without_model_returns_none(pipeline_inputs):
    result, bvp_features = pipeline_inputs
    service = BloodPressureService()
    assert not service.is_available
    assert service.assess(result, bvp_features) is None


def test_service_returns_research_only_estimate_and_risk(trained_model, pipeline_inputs):
    result, bvp_features = pipeline_inputs
    assessment = BloodPressureService(trained_model).assess(result, bvp_features, Demographics(age_years=50, sex_male=False))
    assert assessment.estimate.intended_use.value == "research_only"
    assert assessment.risk.is_diagnosis is False
    assert assessment.risk.evidence_level is EvidenceLevel.INSUFFICIENT
    assert assessment.risk.source_result_id == result.result_id
    if assessment.estimate.status is ResultStatus.INVALID:
        assert assessment.risk.category is None
    else:
        expected = classify_blood_pressure(assessment.estimate.sbp_mmhg, assessment.estimate.dbp_mmhg)
        assert assessment.risk.category is expected


def test_risk_from_invalid_estimate(trained_model, pipeline_inputs):
    result, _ = pipeline_inputs
    estimate = trained_model.predict({})
    risk = BloodPressureRiskModel(trained_model).from_estimate(estimate, result.result_id)
    assert estimate.status is ResultStatus.INVALID
    assert risk.status is ResultStatus.INVALID and risk.score is None and risk.category is None


@pytest.mark.parametrize(
    ("sbp", "dbp", "category"),
    [(112, 72, RiskCategory.LOW), (125, 78, RiskCategory.MODERATE), (132, 84, RiskCategory.MODERATE), (145, 85, RiskCategory.ELEVATED), (128, 92, RiskCategory.ELEVATED)],
)
def test_blood_pressure_categories(sbp, dbp, category):
    assert classify_blood_pressure(sbp, dbp) is category
    assert 0.0 <= blood_pressure_score(sbp, dbp) <= 1.0


def test_bp_csv_roundtrip(synthetic_dataset, tmp_path):
    path = write_bp_dataset_csv(synthetic_dataset, tmp_path / "bp.csv")
    restored = load_bp_dataset_csv(path)
    assert restored.sample_count == synthetic_dataset.sample_count
    assert restored.subject_count == synthetic_dataset.subject_count
    assert np.allclose(restored.targets, synthetic_dataset.targets, atol=0.06)
    assert np.isnan(restored.features).sum() == np.isnan(synthetic_dataset.features).sum()
    with pytest.raises(FileNotFoundError):
        load_bp_dataset_csv(tmp_path / "missing.csv")
    broken = tmp_path / "broken.csv"
    broken.write_text("subject_id,heart_rate_bpm\n1,70\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_bp_dataset_csv(broken)


def test_run_bp_baseline_script(tmp_path):
    from aivitals_engine.scripts.run_bp_baseline import build_parser, run

    summary = run(build_parser().parse_args(["--subjects", "30", "--folds", "3", "--output", str(tmp_path), "--save-model"]))
    assert summary["subjects"] == 30 and summary["intended_use"] == "research_only"
    assert summary["gate"]["passed"] is False
    assert Path(summary["report_path"]).exists()
    restored = RidgeBloodPressureModel.load(summary["model"]["path"], checksum_sha256=summary["model"]["sha256"])
    assert restored.is_fitted


def test_realtime_engine_exposes_khang_features():
    recording = generate_recording(SyntheticScenario(heart_rate_bpm=70.0, duration_seconds=20.0, seed=9))
    engine = RealtimeVitalsEngine("bp-rt", pipeline=ReplayPipeline(recording), config=RealtimeVitalsConfig(update_interval_sec=4.0))
    updates = replay(engine, recording)
    assert updates and all(isinstance(update.bvp_features, BVPFeatures) for update in updates)
    assert engine.latest_features.valid_beat_count > 0
    engine.reset()
    assert engine.latest_features is None


def test_bp_and_health_modules_do_not_call_external_llm():
    for folder in ("models/blood_pressure", "health"):
        for path in (ENGINE_ROOT / folder).glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            imported = {
                (node.module or "").split(".")[0] if isinstance(node, ast.ImportFrom) else alias.name.split(".")[0]
                for node in ast.walk(tree)
                if isinstance(node, (ast.Import, ast.ImportFrom))
                for alias in node.names
            }
            assert not imported & FORBIDDEN_IMPORTS, path.name
