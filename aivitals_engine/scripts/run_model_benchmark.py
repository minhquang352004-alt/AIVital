import argparse
import json
import os
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import numpy as np

from aivitals_engine.benchmark.bp_dataset import generate_synthetic_bp_dataset, load_bp_dataset_csv
from aivitals_engine.benchmark.dataset import load_dataset
from aivitals_engine.benchmark.error_analysis import MethodErrorAnalysis, analyse_heart_rate_errors, calibration_arrays
from aivitals_engine.benchmark.harness import BenchmarkConfig, BenchmarkRunner
from aivitals_engine.benchmark.team_methods import TEAM_METHODS, TeamRPPGSource
from aivitals_engine.models.blood_pressure import (
    RidgeBloodPressureModel,
    evaluate_data_sufficiency,
    subject_independent_cross_validation,
)
from aivitals_engine.models.calibration import MIN_CALIBRATION_SAMPLES, ConfidenceCalibrator
from aivitals_engine.models.deep.preprocessing import build_representation, to_model_layout
from aivitals_engine.models.deep.specs import DEEP_MODEL_SPECS
from aivitals_engine.models.registry import ModelKind, ModelNotFoundError, ModelRegistry, ModelStatus
from aivitals_engine.version import ENGINE_VERSION

DEFAULT_OUTPUT = os.path.join(PROJECT_ROOT, "aivitals_engine", "outputs", "model_benchmark")
CALIBRATOR_NAME = "hr_confidence_calibrator"
BP_MODEL_NAME = "bp_ridge_baseline"
PREPROCESS_REPEATS = 3


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Model benchmark report Tuần 6: HR error, calibration, BP baseline, deep model")
    parser.add_argument("--duration", type=float, default=60.0, help="Độ dài mỗi recording mô phỏng (giây)")
    parser.add_argument("--step", type=float, default=2.0)
    parser.add_argument("--train-seed", type=int, default=7)
    parser.add_argument("--test-seed", type=int, default=8)
    parser.add_argument("--bp-csv", default=None)
    parser.add_argument("--bp-subjects", type=int, default=100)
    parser.add_argument("--version", default="0.1.0", help="Phiên bản đăng ký cho model sinh ra lần này")
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--registry", default=None, help="Thư mục model registry (mặc định <output>/model_store)")
    return parser


def run_heart_rate_benchmark(seed: float, arguments: argparse.Namespace):
    factories = {name: (lambda method=name: TeamRPPGSource(method, 30.0)) for name in TEAM_METHODS}
    recordings = load_dataset("synthetic", seed=seed, duration_seconds=arguments.duration)
    return BenchmarkRunner(factories, BenchmarkConfig(step_seconds=arguments.step)).run(recordings)


def register_artifact(registry: ModelRegistry, name: str, version: str, kind: ModelKind, path: Path, status: ModelStatus, metrics: dict, notes: str):
    try:
        registry.get(name, version)
        return {"name": name, "version": version, "registered": False, "reason": "Phiên bản đã tồn tại trong registry"}
    except ModelNotFoundError:
        entry = registry.register(name, version, kind, path, status=status, metrics=metrics, notes=notes)
        return {"name": name, "version": version, "registered": True, "status": entry.status.value, "checksum_sha256": entry.checksum_sha256}


def calibrate_confidence(train_records, test_records, registry: ModelRegistry, version: str) -> dict:
    train_confidence, train_errors, _ = calibration_arrays(train_records)
    test_confidence, test_errors, _ = calibration_arrays(test_records)
    if train_confidence.size < MIN_CALIBRATION_SAMPLES or test_confidence.size == 0:
        return {
            "skipped": True,
            "reason": f"Cần tối thiểu {MIN_CALIBRATION_SAMPLES} cửa sổ huấn luyện, hiện có {train_confidence.size}",
            "train_windows": int(train_confidence.size),
            "test_windows": int(test_confidence.size),
        }
    calibrator = ConfidenceCalibrator().fit(train_confidence, train_errors)
    evaluation = calibrator.evaluate(test_confidence, test_errors)
    path = calibrator.save(registry.root / CALIBRATOR_NAME / f"{version}.joblib")
    registration = register_artifact(
        registry, CALIBRATOR_NAME, version, ModelKind.CONFIDENCE_CALIBRATOR, path, ModelStatus.EXPERIMENTAL,
        {key: round(value, 4) for key, value in evaluation.items()},
        "Isotonic trên dữ liệu mô phỏng, cần hiệu chỉnh lại trên dữ liệu thật",
    )
    return {
        "train_windows": int(train_confidence.size),
        "test_windows": int(test_confidence.size),
        "error_tolerance_bpm": calibrator.error_tolerance,
        "ece_before": round(evaluation["ece_before"], 4),
        "ece_after": round(evaluation["ece_after"], 4),
        "correct_ratio": round(float(np.mean(test_errors <= calibrator.error_tolerance)), 4),
        "registry": registration,
    }


def blood_pressure_baseline(arguments: argparse.Namespace, registry: ModelRegistry) -> dict:
    dataset = load_bp_dataset_csv(arguments.bp_csv) if arguments.bp_csv else generate_synthetic_bp_dataset(arguments.bp_subjects)
    gate = evaluate_data_sufficiency(dataset.targets, dataset.subject_ids)
    report = subject_independent_cross_validation(RidgeBloodPressureModel, dataset.features, dataset.targets, dataset.subject_ids)
    summary = {
        "source": dataset.source,
        "samples": dataset.sample_count,
        "subjects": dataset.subject_count,
        "gate_passed": gate.passed,
        "gate_reasons": list(gate.reasons),
        "systolic": {**asdict(report.pooled.systolic), "meets_aami": report.pooled.systolic.meets_aami, "bhs_grade": report.pooled.systolic.bhs_grade},
        "diastolic": {**asdict(report.pooled.diastolic), "meets_aami": report.pooled.diastolic.meets_aami, "bhs_grade": report.pooled.diastolic.bhs_grade},
    }
    if not gate.passed:
        summary["registry"] = {"registered": False, "reason": "Chưa đủ dữ liệu theo gate, không huấn luyện bản đăng ký"}
        return summary
    model = RidgeBloodPressureModel(version=arguments.version).fit(dataset.features, dataset.targets)
    path = model.save(registry.root / BP_MODEL_NAME / f"{arguments.version}.joblib")
    metrics = {"sbp_mae": report.pooled.systolic.mean_absolute_error, "dbp_mae": report.pooled.diastolic.mean_absolute_error}
    summary["registry"] = register_artifact(
        registry, BP_MODEL_NAME, arguments.version, ModelKind.BLOOD_PRESSURE, path, ModelStatus.RESEARCH_ONLY, metrics, dataset.source
    )
    return summary


def deep_model_status(registry: ModelRegistry) -> list[dict]:
    rows = []
    rng = np.random.default_rng(0)
    for name, spec in DEEP_MODEL_SPECS.items():
        frames = rng.uniform(40, 220, size=(spec.chunk_frames, spec.frame_size, spec.frame_size, 3)).astype(np.float32)
        timings = []
        for _ in range(PREPROCESS_REPEATS):
            started = perf_counter()
            to_model_layout(build_representation(frames, spec.representations), spec.layout, spec.frame_depth)
            timings.append((perf_counter() - started) * 1000.0)
        try:
            entry = registry.latest(name)
            weights = {"available": True, "version": entry.version, "checksum_sha256": entry.checksum_sha256}
        except ModelNotFoundError:
            weights = {"available": False}
        rows.append({
            "model": name,
            "priority": spec.integration_priority,
            "tier": spec.integration_tier.value,
            "chunk_frames": spec.chunk_frames,
            "window_seconds": spec.window_seconds,
            "preprocess_ms": round(float(np.median(timings)), 2),
            "weights": weights,
            "accuracy": "Chưa đo – chưa có trọng số pretrained" if not weights["available"] else "Chạy benchmark với DeepRPPGAdapter",
        })
    return sorted(rows, key=lambda row: row["priority"])


def format_number(value, digits: int = 2) -> str:
    return "–" if value is None else f"{value:.{digits}f}"


def markdown_report(summary: dict) -> str:
    lines = [
        "# Model Benchmark Report – Tuần 6 (Khoa)",
        "",
        f"- Thời điểm: {summary['generated_at']}",
        f"- Engine version: {summary['engine_version']}",
        "- **Toàn bộ số liệu dưới đây chạy trên dữ liệu mô phỏng**, chỉ để kiểm tra pipeline và so sánh tương đối giữa các thuật toán; chưa phản ánh độ chính xác trên người thật.",
        "",
        "## 1. Sai số nhịp tim (GREEN / CHROM / POS của Khang)",
        "",
        "| Method | Cửa sổ | Bị từ chối | MAE (bpm) | RMSE | Bias | LoA Bland-Altman | Pearson r | ±5 bpm |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for item in summary["heart_rate"]:
        m = item["overall"]
        loa = f"{format_number(m['loa_lower'])} → {format_number(m['loa_upper'])}"
        lines.append(
            f"| {item['method']} | {item['windows']} | {item['rejected_windows']} | {format_number(m['mae'])} | {format_number(m['rmse'])} "
            f"| {format_number(m['bias'])} | {loa} | {format_number(m['pearson_r'], 3)} | {format_number(m['within_tolerance_ratio'])} |"
        )
    for item in summary["heart_rate"]:
        lines += ["", f"### {item['method']} theo kịch bản / trạng thái / mức confidence", "", "| Nhóm | Cửa sổ | MAE (bpm) | ±5 bpm |", "|---|---|---|---|"]
        for group in [*item["by_scenario"], *item["by_status"], *item["by_confidence"]]:
            lines.append(f"| {group['label']} | {group['windows']} | {format_number(group['metrics']['mae'])} | {format_number(group['metrics']['within_tolerance_ratio'])} |")
        lines += ["", "Cửa sổ sai nhiều nhất:", "", "| Kịch bản | t (s) | Tham chiếu | Ước lượng | Sai số | Trạng thái | Confidence | Issue |", "|---|---|---|---|---|---|---|---|"]
        for worst in item["worst_windows"]:
            lines.append(
                f"| {worst['scenario']} | {worst['window_end_s']} | {worst['reference_bpm']} | {worst['estimated_bpm']} | {worst['error_bpm']} "
                f"| {worst['status']} | {worst['confidence']} | {', '.join(worst['issue_codes']) or '–'} |"
            )
    calibration = summary["calibration"]
    lines += ["", "## 2. Hiệu chỉnh confidence (isotonic)", ""]
    if calibration.get("skipped"):
        lines.append(f"- Bỏ qua: {calibration['reason']}.")
    else:
        lines += calibration_lines(summary, calibration)
    lines += [
        "",
        "## 3. Baseline huyết áp",
        "",
    ]
    return blood_pressure_and_deep_lines(summary, lines)


def calibration_lines(summary: dict, calibration: dict) -> list[str]:
    return [
        f"- Huấn luyện trên {calibration['train_windows']} cửa sổ (seed {summary['train_seed']}), kiểm tra trên {calibration['test_windows']} cửa sổ (seed {summary['test_seed']}).",
        f"- Đúng = sai số ≤ {calibration['error_tolerance_bpm']} bpm. ECE trước: {calibration['ece_before']}, sau: {calibration['ece_after']}.",
        f"- Tỷ lệ cửa sổ đúng trên tập kiểm tra: {calibration['correct_ratio']}.",
        *(
            ["- Tất cả cửa sổ đều đúng nên isotonic chỉ học được hằng số 1; ECE sau hiệu chỉnh không có ý nghĩa, cần dữ liệu thật có cửa sổ sai."]
            if calibration["correct_ratio"] >= 1.0
            else []
        ),
        f"- Registry: {json.dumps(calibration['registry'], ensure_ascii=False)}",
    ]


def blood_pressure_and_deep_lines(summary: dict, lines: list[str]) -> str:
    bp = summary["blood_pressure"]
    lines += [
        f"- Dữ liệu: {bp['source']} – {bp['samples']} mẫu, {bp['subjects']} người.",
        f"- SBP: MAE {format_number(bp['systolic']['mean_absolute_error'])} mmHg, ME {format_number(bp['systolic']['mean_error'])} ± {format_number(bp['systolic']['error_sd'])}, AAMI {'đạt' if bp['systolic']['meets_aami'] else 'chưa đạt'}, BHS {bp['systolic']['bhs_grade']}.",
        f"- DBP: MAE {format_number(bp['diastolic']['mean_absolute_error'])} mmHg, ME {format_number(bp['diastolic']['mean_error'])} ± {format_number(bp['diastolic']['error_sd'])}, AAMI {'đạt' if bp['diastolic']['meets_aami'] else 'chưa đạt'}, BHS {bp['diastolic']['bhs_grade']}.",
        f"- Gate dữ liệu: {'đạt' if bp['gate_passed'] else 'chưa đạt'}. Registry: {json.dumps(bp['registry'], ensure_ascii=False)}",
    ]
    lines += [f"  - {reason}" for reason in bp["gate_reasons"]]
    lines += [
        "",
        "## 4. Deep model",
        "",
        "| Ưu tiên | Model | Phân loại | Chunk | Cửa sổ (s) | Tiền xử lý (ms) | Trọng số | Độ chính xác |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in summary["deep_models"]:
        weights = f"có ({row['weights']['version']})" if row["weights"]["available"] else "chưa có"
        lines.append(
            f"| {row['priority']} | {row['model']} | {row['tier']} | {row['chunk_frames']} | {row['window_seconds']:.1f} "
            f"| {row['preprocess_ms']} | {weights} | {row['accuracy']} |"
        )
    return "\n".join(lines) + "\n"


def run(arguments: argparse.Namespace) -> dict:
    output = Path(arguments.output)
    output.mkdir(parents=True, exist_ok=True)
    registry = ModelRegistry(arguments.registry or output / "model_store")
    train_report = run_heart_rate_benchmark(arguments.train_seed, arguments)
    test_report = run_heart_rate_benchmark(arguments.test_seed, arguments)
    analyses: list[MethodErrorAnalysis] = analyse_heart_rate_errors(test_report.records)
    summary = {
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "engine_version": ENGINE_VERSION,
        "train_seed": arguments.train_seed,
        "test_seed": arguments.test_seed,
        "heart_rate": [asdict(analysis) for analysis in analyses],
        "calibration": calibrate_confidence(train_report.records, test_report.records, registry, arguments.version),
        "blood_pressure": blood_pressure_baseline(arguments, registry),
        "deep_models": deep_model_status(registry),
        "registry_root": str(registry.root),
    }
    (output / "model_benchmark_report.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (output / "model_benchmark_report.md").write_text(markdown_report(summary), encoding="utf-8")
    summary["report_dir"] = str(output)
    return summary


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    summary = run(build_parser().parse_args())
    print(markdown_report(summary))
    print(f"Đã ghi báo cáo vào {summary['report_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
