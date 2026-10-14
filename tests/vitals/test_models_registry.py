import hashlib

import numpy as np
import pytest

from aivitals_engine.models.calibration import CalibratorNotFittedError, ConfidenceCalibrator, expected_calibration_error
from aivitals_engine.models.registry import (
    ArtifactOutsideRegistryError,
    ChecksumMismatchError,
    DuplicateModelVersionError,
    ModelKind,
    ModelNotFoundError,
    ModelRegistry,
    ModelStatus,
)


def write_artifact(root, name, content=b"weights"):
    path = root / "artifacts" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def test_register_and_resolve(tmp_path):
    registry = ModelRegistry(tmp_path)
    artifact = write_artifact(tmp_path, "tscan.pt")
    entry = registry.register("tscan", "1.0.0", ModelKind.RPPG_DEEP, artifact, metrics={"hr_mae": 2.1}, dataset_version="ds-v1")
    assert entry.checksum_sha256 == hashlib.sha256(b"weights").hexdigest()
    assert entry.artifact_path == "artifacts/tscan.pt"
    assert registry.resolve_artifact("tscan", "1.0.0") == artifact.resolve()
    assert ModelRegistry(tmp_path).get("tscan", "1.0.0") == entry
    assert entry.to_model_info().checksum_sha256 == entry.checksum_sha256


def test_latest_uses_semantic_version_order(tmp_path):
    registry = ModelRegistry(tmp_path)
    registry.register("bp", "0.9.0", ModelKind.BLOOD_PRESSURE, write_artifact(tmp_path, "a.joblib", b"a"), status=ModelStatus.VALIDATED)
    registry.register("bp", "0.10.0", ModelKind.BLOOD_PRESSURE, write_artifact(tmp_path, "b.joblib", b"b"))
    assert registry.latest("bp").version == "0.10.0"
    assert registry.latest("bp", allowed_statuses=[ModelStatus.VALIDATED]).version == "0.9.0"
    with pytest.raises(ModelNotFoundError):
        registry.latest("bp", allowed_statuses=[ModelStatus.PRODUCTION])


def test_duplicate_version_is_rejected(tmp_path):
    registry = ModelRegistry(tmp_path)
    artifact = write_artifact(tmp_path, "m.bin")
    registry.register("model", "1.0.0", ModelKind.HEALTH_RISK, artifact)
    with pytest.raises(DuplicateModelVersionError):
        registry.register("model", "1.0.0", ModelKind.HEALTH_RISK, artifact)


def test_checksum_mismatch_is_detected(tmp_path):
    registry = ModelRegistry(tmp_path)
    artifact = write_artifact(tmp_path, "m.bin")
    entry = registry.register("model", "1.0.0", ModelKind.RPPG_DEEP, artifact)
    artifact.write_bytes(b"tampered")
    with pytest.raises(ChecksumMismatchError):
        registry.verify(entry)


def test_artifact_outside_registry_is_rejected(tmp_path):
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"x")
    with pytest.raises(ArtifactOutsideRegistryError):
        ModelRegistry(tmp_path / "store").register("model", "1.0.0", ModelKind.RPPG_DEEP, outside)


def test_update_status_persists(tmp_path):
    registry = ModelRegistry(tmp_path)
    registry.register("model", "1.0.0", ModelKind.RPPG_DEEP, write_artifact(tmp_path, "m.bin"))
    registry.update_status("model", "1.0.0", ModelStatus.DEPRECATED)
    assert ModelRegistry(tmp_path).list_entries(status=ModelStatus.DEPRECATED)[0].name == "model"
    assert registry.list_entries(kind=ModelKind.BLOOD_PRESSURE) == []


def test_calibration_reduces_error():
    rng = np.random.default_rng(0)
    raw = rng.uniform(0.0, 1.0, 600)
    errors = np.where(rng.uniform(size=raw.size) < raw**3, 1.0, 20.0)
    calibrator = ConfidenceCalibrator(error_tolerance=5.0).fit(raw, errors)
    metrics = calibrator.evaluate(raw, errors)
    assert metrics["ece_after"] < metrics["ece_before"]


def test_calibrator_save_load_and_guards(tmp_path):
    raw = np.linspace(0, 1, 40)
    errors = np.where(raw > 0.5, 1.0, 10.0)
    calibrator = ConfidenceCalibrator().fit(raw, errors)
    restored = ConfidenceCalibrator.load(calibrator.save(tmp_path / "calibrator.joblib"))
    assert np.allclose(restored.transform(raw), calibrator.transform(raw))
    with pytest.raises(ValueError):
        ConfidenceCalibrator().fit(raw[:5], errors[:5])
    with pytest.raises(CalibratorNotFittedError):
        ConfidenceCalibrator().transform(0.5)


def test_expected_calibration_error_is_zero_when_perfect():
    assert expected_calibration_error(np.array([1.0, 1.0, 0.0, 0.0]), np.array([1, 1, 0, 0])) == 0.0
