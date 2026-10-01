import pytest

from aivitals_engine.benchmark.cli import build_method_factories, main
from aivitals_engine.benchmark.dataset import load_dataset, load_npz_recording, save_npz_recording
from aivitals_engine.benchmark.harness import BenchmarkConfig, BenchmarkRunner
from aivitals_engine.benchmark.latency import benchmark_vitals_latency
from aivitals_engine.benchmark.metrics import compute_error_metrics
from aivitals_engine.benchmark.team_methods import TeamRPPGSource


@pytest.fixture(scope="module")
def short_recordings():
    return load_dataset("synthetic", seed=3, duration_seconds=36.0)[:2]


@pytest.fixture(scope="module")
def report(short_recordings):
    factories = {name: (lambda method=name: TeamRPPGSource(method, 30.0)) for name in ("GREEN", "CHROM", "POS")}
    return BenchmarkRunner(factories, BenchmarkConfig(window_seconds=30.0, step_seconds=3.0)).run(short_recordings)


def test_team_source_uses_khang_methods():
    source = TeamRPPGSource("POS")
    assert source.name == "POS"
    assert source.version == "1.0"
    assert source.get_signal() is None
    with pytest.raises(ValueError):
        TeamRPPGSource("PHYSNET")


def test_team_methods_recover_heart_rate(report):
    assert {summary.method for summary in report.summaries} == {"GREEN", "CHROM", "POS"}
    for summary in report.summaries:
        assert summary.window_count > 0
        assert summary.hr_coverage > 0.5
        assert summary.hr_accepted.mae < 5.0


def test_report_is_written(report, tmp_path):
    paths = report.write(tmp_path)
    assert all(path.exists() for path in paths.values())
    assert "Báo cáo benchmark AIVitals" in paths["markdown"].read_text(encoding="utf-8")


def test_npz_roundtrip(short_recordings, tmp_path):
    original = short_recordings[0]
    restored = load_npz_recording(save_npz_recording(original, tmp_path / "recording.npz"))
    assert restored.recording_id == original.recording_id
    assert restored.scenario == original.scenario
    assert restored.reference_heart_rate(0, 30) == pytest.approx(original.reference_heart_rate(0, 30))
    with pytest.raises(FileNotFoundError):
        load_dataset(str(tmp_path / "missing"))


def test_error_metrics():
    metrics = compute_error_metrics([60.0, 70.0, 80.0, None], [62.0, 68.0, 80.0, 75.0], tolerance=2.0)
    assert metrics.count == 3
    assert metrics.mae == pytest.approx(4.0 / 3.0)
    assert metrics.within_tolerance_ratio == 1.0
    assert compute_error_metrics([], [], 1.0).count == 0


def test_runner_requires_methods():
    with pytest.raises(ValueError):
        BenchmarkRunner({})


def test_latency_benchmark():
    latency = benchmark_vitals_latency(iterations=3, window_seconds=20.0)
    assert latency.p95_ms >= latency.p50_ms > 0


def test_cli_run(tmp_path):
    exit_code = main(["run", "--methods", "POS", "--duration", "34", "--step", "4", "--output", str(tmp_path)])
    assert exit_code == 0
    assert (tmp_path / "benchmark_report.json").exists()
    with pytest.raises(ValueError):
        build_method_factories(["PHYSNET"], 30.0)
