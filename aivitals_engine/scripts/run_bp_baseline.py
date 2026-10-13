import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from aivitals_engine.benchmark.bp_dataset import (
    BloodPressureDataset,
    generate_synthetic_bp_dataset,
    load_bp_dataset_csv,
)
from aivitals_engine.models.blood_pressure import (
    RidgeBloodPressureModel,
    evaluate_data_sufficiency,
    file_sha256,
    subject_independent_cross_validation,
)

DEFAULT_OUTPUT = os.path.join(PROJECT_ROOT, "aivitals_engine", "outputs", "bp")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Huấn luyện và đánh giá baseline huyết áp (chỉ phục vụ nghiên cứu)")
    parser.add_argument("--csv", default=None, help="File CSV: subject_id, sbp_mmhg, dbp_mmhg + các cột đặc trưng")
    parser.add_argument("--subjects", type=int, default=100, help="Số subject khi dùng dữ liệu mô phỏng")
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--alpha", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--save-model", action="store_true", help="Lưu model huấn luyện trên toàn bộ dữ liệu kèm checksum")
    return parser


def load_dataset(arguments: argparse.Namespace) -> BloodPressureDataset:
    if arguments.csv:
        return load_bp_dataset_csv(arguments.csv)
    return generate_synthetic_bp_dataset(subject_count=arguments.subjects, seed=arguments.seed)


def run(arguments: argparse.Namespace) -> dict:
    dataset = load_dataset(arguments)
    gate = evaluate_data_sufficiency(dataset.targets, dataset.subject_ids)
    report = subject_independent_cross_validation(
        lambda: RidgeBloodPressureModel(alpha=arguments.alpha),
        dataset.features,
        dataset.targets,
        dataset.subject_ids,
        n_splits=arguments.folds,
    )
    pooled = report.pooled
    summary = {
        "source": dataset.source,
        "samples": dataset.sample_count,
        "subjects": dataset.subject_count,
        "feature_count": len(dataset.feature_names),
        "gate": asdict(gate),
        "pooled": {
            "systolic": {**asdict(pooled.systolic), "meets_aami": pooled.systolic.meets_aami, "bhs_grade": pooled.systolic.bhs_grade},
            "diastolic": {**asdict(pooled.diastolic), "meets_aami": pooled.diastolic.meets_aami, "bhs_grade": pooled.diastolic.bhs_grade},
        },
        "intended_use": "research_only",
    }
    output = Path(arguments.output)
    output.mkdir(parents=True, exist_ok=True)
    if arguments.save_model:
        model = RidgeBloodPressureModel(alpha=arguments.alpha).fit(dataset.features, dataset.targets)
        model_path = model.save(output / "bp_ridge_baseline.joblib")
        summary["model"] = {"path": str(model_path), "sha256": file_sha256(model_path)}
    report_path = output / "bp_baseline_report.json"
    report_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    summary["report_path"] = str(report_path)
    return summary


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    summary = run(build_parser().parse_args())
    pooled = summary["pooled"]
    print(f"Nguồn dữ liệu: {summary['source']} | {summary['samples']} mẫu, {summary['subjects']} subject")
    for name in ("systolic", "diastolic"):
        stats = pooled[name]
        print(
            f"{name}: MAE {stats['mean_absolute_error']:.2f} mmHg, ME {stats['mean_error']:.2f} ± {stats['error_sd']:.2f}, "
            f"AAMI {'đạt' if stats['meets_aami'] else 'chưa đạt'}, BHS {stats['bhs_grade']}"
        )
    print(f"Gate dữ liệu: {'đạt' if summary['gate']['passed'] else 'chưa đạt'}")
    for reason in summary["gate"]["reasons"]:
        print(f"  - {reason}")
    print(f"Báo cáo: {summary['report_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
