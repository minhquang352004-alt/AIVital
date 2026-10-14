import json
from pathlib import Path

import numpy as np
import pytest

from aivitals_engine.benchmark.error_analysis import analyse_heart_rate_errors, calibration_arrays
from aivitals_engine.benchmark.report import WindowRecord
from aivitals_engine.contracts.frame import FramePacket
from aivitals_engine.integration.vitals_service import VitalsService
from aivitals_engine.models.calibration import ConfidenceCalibrator
from aivitals_engine.models.deep.adapter import DeepRPPGAdapter, resample_frames
from aivitals_engine.models.deep.specs import TSCAN_SPEC
from aivitals_engine.models.registry import ModelRegistry
from aivitals_engine.scripts.run_model_benchmark import build_parser, markdown_report, run
from tests.vitals.test_deep_models import SineDerivativeRunner


def make_record(method: str, scenario: str, reference: float, estimated: float | None, confidence: float, status: str = "OK") -> WindowRecord:
    return WindowRecord(
        method=method,
        method_version="1.0",
        recording_id=f"{scenario}-rec",
        subject_id="s",
        scenario=scenario,
        window_end_s=30.0,
        reference_hr_bpm=reference,
        estimated_hr_bpm=estimated,
        hr_status=status,
        hr_confidence=confidence,
        hr_issue_codes=() if status == "OK" else ("LOW_CONFIDENCE",),
        reference_rmssd_ms=None,
        estimated_rmssd_ms=None,
        hrv_status="INVALID",
        reference_rr_brpm=None,
        estimated_rr_brpm=None,
        rr_status="INVALID",
        signal_latency_ms=1.0,
        vitals_latency_ms=1.0,
    )


def test_error_analysis_groups_and_worst_windows():
    records = [
        make_record("POS", "rest", 70.0, 71.0, 0.9),
        make_record("POS", "rest", 70.0, 69.0, 0.85),
        make_record("POS", "motion", 80.0, 92.0, 0.5, "BAD"),
        make_record("POS", "motion", 80.0, None, 0.0, "INVALID"),
        make_record("GREEN", "rest", 70.0, 70.5, 0.95),
    ]
    analyses = {analysis.method: analysis for analysis in analyse_heart_rate_errors(records)}
    pos = analyses["POS"]
    assert pos.windows == 4 and pos.rejected_windows == 1
    assert pos.overall.count == 3
    assert pos.overall.mae == pytest.approx((1 + 1 + 12) / 3)
    scenarios = {group.label: group for group in pos.by_scenario}
    assert scenarios["motion"].metrics.mae == pytest.approx(12.0)
    assert pos.worst_windows[0].error_bpm == pytest.approx(12.0)
    assert sum(group.windows for group in pos.by_confidence) == pos.windows
    confidence, errors, groups = calibration_arrays(records)
    assert confidence.size == errors.size == groups.size == 4


def test_resample_frames_aligns_to_target_fps():
    timestamps = np.arange(0, 3.0, 1 / 15.0)
    frames = timestamps.reshape(-1, 1, 1, 1) * np.ones((1, 2, 2, 3))
    resampled = resample_frames(frames, timestamps, 30.0)
    assert resampled.shape == frames.shape
    assert np.allclose(resampled[:, 0, 0, 0], np.arange(frames.shape[0]) / 30.0)


def feed(adapter: DeepRPPGAdapter, count: int, fps: float, start: int = 0) -> None:
    rng = np.random.default_rng(start)
    for index in range(start, start + count):
        crop = rng.integers(0, 255, size=(80, 80, 3), dtype=np.uint8)
        adapter.update(FramePacket(timestamp=index / fps, face_detected=True, face_crop=crop))


def test_adapter_reuses_inference_until_stride():
    runner = SineDerivativeRunner(1.2, 30.0)
    adapter = DeepRPPGAdapter(TSCAN_SPEC, runner, stride_frames=15)
    feed(adapter, 180, 30.0)
    first = adapter.get_signal()
    feed(adapter, 5, 30.0, start=180)
    assert adapter.get_signal() is first
    assert len(runner.input_shapes) == 1
    feed(adapter, 10, 30.0, start=185)
    assert adapter.get_signal() is not first
    assert len(runner.input_shapes) == 2
    assert adapter.get_metadata()["stride_frames"] == 15


def test_adapter_resamples_low_fps_camera():
    adapter = DeepRPPGAdapter(TSCAN_SPEC, SineDerivativeRunner(1.2, 30.0))
    feed(adapter, 180, 20.0)
    window = adapter.get_signal()
    assert window.sampling_rate_hz == pytest.approx(TSCAN_SPEC.target_fps)


def test_calibrator_checksum_and_service_integration(tmp_path, clean_window):
    raw = np.linspace(0.05, 0.95, 60)
    errors = np.where(raw > 0.5, 1.0, 12.0)
    calibrator = ConfidenceCalibrator().fit(raw, errors)
    path = calibrator.save(tmp_path / "calibrator.joblib")
    registry = ModelRegistry(tmp_path)
    from aivitals_engine.models.registry import ModelKind

    entry = registry.register("hr_confidence_calibrator", "0.1.0", ModelKind.CONFIDENCE_CALIBRATOR, path)
    restored = ConfidenceCalibrator.load(registry.verify(entry), checksum_sha256=entry.checksum_sha256)
    with pytest.raises(ValueError):
        ConfidenceCalibrator.load(path, checksum_sha256="0" * 64)
    window, _ = clean_window
    raw_result = VitalsService().compute(window, "raw")
    calibrated_result = VitalsService(confidence_calibrator=restored).compute(window, "calibrated")
    raw_confidence = raw_result.vitals[0].confidence
    expected = float(restored.transform(raw_confidence)[0])
    assert calibrated_result.vitals[0].confidence == pytest.approx(expected, abs=0.01)


def test_model_benchmark_script(tmp_path):
    arguments = build_parser().parse_args(
        ["--duration", "36", "--step", "3", "--bp-subjects", "30", "--output", str(tmp_path)]
    )
    summary = run(arguments)
    assert {item["method"] for item in summary["heart_rate"]} == {"GREEN", "CHROM", "POS"}
    assert summary["calibration"]["registry"]["registered"] is True
    assert summary["blood_pressure"]["gate_passed"] is False
    assert summary["blood_pressure"]["registry"]["registered"] is False
    assert [row["model"] for row in summary["deep_models"]] == ["tscan", "efficientphys", "deepphys", "physnet"]
    assert all(row["weights"]["available"] is False for row in summary["deep_models"])
    report = json.loads((tmp_path / "model_benchmark_report.json").read_text(encoding="utf-8"))
    assert report["calibration"]["test_windows"] > 0
    markdown = markdown_report(summary)
    assert "Model Benchmark Report" in markdown and "dữ liệu mô phỏng" in markdown
    registry = ModelRegistry(Path(summary["registry_root"]))
    assert registry.verify(registry.latest("hr_confidence_calibrator")).exists()
    again = run(arguments)
    assert again["calibration"]["registry"]["registered"] is False
