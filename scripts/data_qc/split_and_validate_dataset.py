"""HAO local inventory lock, grouped allocation and paired-metric audit; never fits models."""
import argparse
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
import csv
import hashlib
import json
import math
from pathlib import Path
import random
import statistics
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "docs/DatasetValidation_V1"
sys.path.insert(0, str(ROOT))
from aivitals_engine.benchmark.metrics import compute_error_metrics
from aivitals_engine.config.vitals_config import ValidationConfig
from aivitals_engine.contracts.result import VitalCode
from aivitals_engine.models.blood_pressure.evaluation import evaluate_blood_pressure
from aivitals_engine.models.blood_pressure.gate import evaluate_data_sufficiency
import numpy as np

CONFIG = ValidationConfig()
ALIASES = {"reference_hr_bpm": "hr_reference_bpm", "reference_sbp_mmhg": "sbp_reference_mmhg",
           "reference_dbp_mmhg": "dbp_reference_mmhg", "subject_age_years": "age_years",
           "subject_sex": "sex", "fitzpatrick_type": "fitzpatrick", "engine_status": "signal_status"}
NUMERIC = ("age_years", "hr_reference_bpm", "hr_estimated_bpm", "sbp_reference_mmhg",
           "dbp_reference_mmhg", "sbp_estimated_mmhg", "dbp_estimated_mmhg", "sqi")
FLAGS = ("usage_authorized", "strict_protocol_accepted", "hr_reference_qc_pass", "bp_reference_qc_pass",
         "hr_pairing_verified", "bp_pairing_verified", "prediction_subject_independent")
ENGINE_PATHS = ("quality/sqi.py", "config/vitals_config.py", "validation/rules.py",
                "benchmark/metrics.py", "models/blood_pressure/evaluation.py", "models/blood_pressure/gate.py")


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def boolean(value):
    text = str(value if value is not None else "").strip().lower()
    if text not in ("", "true", "false", "1", "0"):
        raise ValueError("Boolean must be blank/true/false/1/0")
    return text in ("true", "1")


def normalize(raw):
    row = {str(k): (v.strip() if isinstance(v, str) else v) for k, v in raw.items()}
    for old, new in ALIASES.items():
        if old in row:
            if new in row and row[new] != row[old]:
                raise ValueError(f"Conflicting columns: {old}, {new}")
            row[new] = row[old]
    for name in NUMERIC:
        value = row.get(name)
        row[name] = None if value in (None, "") else float(value)
        if row[name] is not None and not math.isfinite(row[name]):
            raise ValueError(f"Non-finite number: {name}")
    for name in FLAGS:
        row[name] = boolean(row.get(name))
    for name in ("signal_status", "hr_status", "bp_status"):
        row[name] = str(row.get(name) or "").upper()
        if row[name] not in ("", "OK", "BAD", "INVALID"):
            raise ValueError(f"Invalid {name}")
    if row["sqi"] is not None and not 0 <= row["sqi"] <= 1:
        raise ValueError("SQI outside [0,1]")
    if row["age_years"] is not None and row["age_years"] < 0:
        raise ValueError("Negative age")
    return row


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames or []
        if len(fields) != len(set(fields)) or not {"sample_id", "subject_id"} <= set(fields):
            raise ValueError("CSV requires unique headers, sample_id and subject_id")
        rows = []
        for number, raw in enumerate(reader, 2):
            if None in raw or any(v is None for v in raw.values()):
                raise ValueError(f"Malformed CSV row {number}")
            rows.append(normalize(raw))
    return rows, [path]


def read_clbp(folder):
    """Adapt only existing JSON evidence; never read videos or infer missing approvals."""
    path = folder / "DATASET_V1_BP_PILOT_MANIFEST.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    rows, sources = [], [path]
    for label in manifest["samples"]:
        sid = label["sample_id"]
        if Path(sid).name != sid or "/" in sid or "\\" in sid:
            raise ValueError("Unsafe cached sample ID")
        evidence_path = folder / f"{sid}_qc_features.json"
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        if evidence["sample_id"] != sid:
            raise ValueError("Cached evidence/sample mismatch")
        sources.append(evidence_path)
        rows.append(normalize({
            "sample_id": sid, "subject_id": label["subject_id"], "source_dataset": "CLBP_pilot",
            "video_sha256": label["video_sha256"], "age_years": label["age_years"], "sex": label["sex"],
            "hr_reference_bpm": label["hr_bpm"], "sbp_reference_mmhg": label["sbp_mmhg"],
            "dbp_reference_mmhg": label["dbp_mmhg"], "hr_estimated_bpm": evidence["estimated_hr_bpm"],
            "sqi": evidence["sqi"], "signal_status": evidence["raw_engine_status"],
            "hr_status": evidence["hr_status"], "strict_protocol_accepted": label["strict_protocol_accepted"],
            "label_provenance": "publisher workbook verified in Week5; cuff timing/repeats unavailable",
            "source_evidence": str(evidence_path.relative_to(ROOT)),
        }))
    return rows, sources


def validate_identity(rows):
    if not rows:
        raise ValueError("Empty dataset")
    samples, spellings, identities = set(), {}, {}
    for row in rows:
        for key in ("sample_id", "subject_id"):
            value = row.get(key)
            if not isinstance(value, str) or not value or value != value.strip():
                raise ValueError(f"Missing/noncanonical {key}")
        sample, subject = row["sample_id"], row["subject_id"]
        if sample.casefold() in samples:
            raise ValueError("Duplicate sample_id")
        samples.add(sample.casefold())
        folded = subject.casefold()
        if folded in spellings and spellings[folded] != subject:
            raise ValueError("Subject ID case variants require canonical mapping")
        spellings[folded] = subject
        for key in ("video_sha256", "parent_sample_id"):
            value = row.get(key)
            if value:
                if key == "video_sha256" and (len(value) != 64 or any(c not in "0123456789abcdefABCDEF" for c in value)):
                    raise ValueError("Invalid video_sha256")
                identity = (key, value.lower() if key == "video_sha256" else value)
                if identity in identities and identities[identity] != subject:
                    raise ValueError("Same source/parent assigned to different subjects")
                identities[identity] = subject
    # Validate supplied splits before creating any new plan; never silently repair leakage.
    for key, allowed in (("split", {"train", "val", "test"}), ("fold", None)):
        present = [bool(row.get(key)) for row in rows]
        if any(present):
            if not all(present):
                raise ValueError(f"Partial input {key} assignment")
            by_subject = defaultdict(set)
            for row in rows:
                value = str(row[key])
                if allowed is not None and value not in allowed:
                    raise ValueError("split must be train/val/test")
                if key == "fold" and (not value.isdigit() or int(value) < 0):
                    raise ValueError("fold must be a nonnegative integer")
                by_subject[row["subject_id"]].add(value)
            if any(len(values) != 1 for values in by_subject.values()):
                raise ValueError(f"Subject leakage in input {key}")
    # A child must belong to the subject of its parent if the parent is also present.
    sample_subjects = {r["sample_id"]: r["subject_id"] for r in rows}
    for row in rows:
        parent = row.get("parent_sample_id")
        if parent in sample_subjects and sample_subjects[parent] != row["subject_id"]:
            raise ValueError("Child/parent subject mismatch")


def assign(rows, mode, seed, folds):
    subjects = sorted({r["subject_id"] for r in rows})
    shuffled = subjects.copy()
    random.Random(seed).shuffle(shuffled)
    if mode == "existing":
        supplied = [key for key in ("split", "fold") if all(r.get(key) not in (None, "") for r in rows)]
        if len(supplied) != 1:
            raise ValueError("existing mode requires exactly one complete split or fold column")
        key = supplied[0]
        if key == "split" and {r[key] for r in rows} != {"train", "val", "test"}:
            raise ValueError("existing mode needs nonempty train/val/test")
        if key == "fold" and len({r[key] for r in rows}) < 2:
            raise ValueError("existing mode needs >=2 test folds")
        allocation = {r["subject_id"]: str(r[key]) for r in rows}
    else:
        if any(r.get("split") or r.get("fold") for r in rows):
            raise ValueError("Input already assigned; use existing mode or a reviewed new input version")
        if mode == "audit":
            allocation = {s: "unassigned" for s in subjects}
        elif mode == "kfold":
            if not 2 <= folds <= len(subjects):
                raise ValueError("Need 2 <= folds <= subject count")
            allocation = {s: str(i % folds) for i, s in enumerate(shuffled)}
        else:
            if len(subjects) < 7:
                raise ValueError("70/15/15 needs >=7 subjects by local planning policy; use kfold for pilot")
            quotas = [len(subjects) * f for f in (.70, .15, .15)]
            counts = [math.floor(x) for x in quotas]
            for i in sorted(range(3), key=lambda i: (-(quotas[i] - counts[i]), i))[:len(subjects) - sum(counts)]:
                counts[i] += 1
            if min(counts) < 1:
                raise ValueError("Empty split")
            allocation = {}
            start = 0
            for name, count in zip(("train", "val", "test"), counts):
                allocation.update({s: name for s in shuffled[start:start + count]})
                start += count
    key = "candidate_fold" if mode == "kfold" or (mode == "existing" and supplied[0] == "fold") else "candidate_split"
    for row in rows:
        row[key] = allocation[row["subject_id"]]
    for value in set(allocation.values()):
        heldout = {s for s in subjects if allocation[s] == value}
        other = set(subjects) - heldout
        if heldout & other:
            raise ValueError("Generated subject leakage")
    return key


def label_reasons(row, target):
    if target == "hr":
        value = row["hr_reference_bpm"]
        reasons = ["MISSING_OR_NONPOSITIVE_HR_REFERENCE"] if value is None or value <= 0 else []
        if value is not None and value > 0 and not CONFIG.ranges[VitalCode.HEART_RATE].contains(value):
            reasons.append("HR_REFERENCE_OUTSIDE_ENGINE_RANGE_REVIEW")
    else:
        sbp, dbp = row["sbp_reference_mmhg"], row["dbp_reference_mmhg"]
        reasons = ["MISSING_OR_UNORDERED_BP_REFERENCE"] if sbp is None or dbp is None or not sbp > dbp > 0 else []
    return reasons


def qc_reasons(row, target):
    reasons = label_reasons(row, target)
    for field in ("usage_authorized", "strict_protocol_accepted", f"{target}_reference_qc_pass", f"{target}_pairing_verified"):
        if not row[field]:
            reasons.append(field.upper() + "_NOT_CONFIRMED")
    if row["sqi"] is None:
        reasons.append("SQI_MISSING")
    elif row["sqi"] < CONFIG.signal_quality_ok:
        reasons.append("SQI_UNUSABLE" if row["sqi"] < CONFIG.signal_quality_invalid else "SQI_LOW")
    if row["signal_status"] != "OK":
        reasons.append("SIGNAL_STATUS_NOT_OK")
    return reasons


def describe(values):
    values = [v for v in values if v is not None]
    if not values:
        return {"n": 0, "min": None, "max": None, "mean": None, "sd_sample": None}
    return {"n": len(values), "min": min(values), "max": max(values), "mean": statistics.mean(values),
            "sd_sample": statistics.stdev(values) if len(values) > 1 else None}


def distributions(rows):
    by_subject = defaultdict(list)
    for row in rows:
        by_subject[row["subject_id"]].append(row)
    subject_stats = {}
    for field in ("age_years", "sex", "fitzpatrick"):
        values = []
        for records in by_subject.values():
            present = {r.get(field) for r in records if r.get(field) not in (None, "")}
            if len(present) > 1:
                raise ValueError(f"Conflicting within-subject demographic: {field}")
            values.append(next(iter(present), None))
        subject_stats[field] = {"missing_subjects": sum(v is None for v in values),
                                "values": describe(values) if field == "age_years" else dict(Counter(v for v in values if v is not None))}
    vitals = {}
    for field in ("hr_reference_bpm", "sbp_reference_mmhg", "dbp_reference_mmhg"):
        means = [statistics.mean(vals) for records in by_subject.values()
                 if (vals := [r[field] for r in records if r[field] is not None])]
        vitals[field] = {"row_values": describe([r[field] for r in rows]), "subject_means": describe(means),
                         "missing_rows": sum(r[field] is None for r in rows)}
    return {"rows": len(rows), "subjects": len(by_subject), "demographics_subject_level": subject_stats,
            "reference_vitals_descriptive_not_accuracy": vitals}


def paired_report(rows, target, mode, assignment_sha256):
    selected, excluded = [], Counter()
    for row in rows:
        reasons = qc_reasons(row, target)
        if row[f"{target}_status"] != "OK":
            reasons.append("PREDICTION_STATUS_NOT_OK")
        if not row["prediction_subject_independent"] or not row.get("prediction_provenance"):
            reasons.append("INDEPENDENT_PREDICTION_PROVENANCE_MISSING")
        expected_holdout = row.get("candidate_fold") if mode == "kfold" else "test"
        if (str(row.get("prediction_holdout", "")) != expected_holdout
                or row.get("prediction_assignment_sha256") != assignment_sha256):
            reasons.append("PREDICTION_ALLOCATION_NOT_VERIFIED")
        if mode != "kfold" and row.get("candidate_split") != "test":
            reasons.append("NOT_HELDOUT_TEST")
        fields = ("hr_estimated_bpm",) if target == "hr" else ("sbp_estimated_mmhg", "dbp_estimated_mmhg")
        if any(row[f] is None for f in fields):
            reasons.append("PREDICTION_MISSING")
        if reasons:
            excluded.update(set(reasons))
        else:
            selected.append(row)
    endpoints = (("hr", "hr_reference_bpm", "hr_estimated_bpm", 5.0),) if target == "hr" else (
        ("sbp", "sbp_reference_mmhg", "sbp_estimated_mmhg", 5.0),
        ("dbp", "dbp_reference_mmhg", "dbp_estimated_mmhg", 5.0))
    output = {}
    for name, ref, est, tolerance in endpoints:
        output[name] = asdict(compute_error_metrics([r[ref] for r in selected], [r[est] for r in selected], tolerance))
    bp_stats = None
    if target == "bp" and selected:
        truth = np.array([[r["sbp_reference_mmhg"], r["dbp_reference_mmhg"]] for r in selected])
        pred = np.array([[r["sbp_estimated_mmhg"], r["dbp_estimated_mmhg"]] for r in selected])
        # Serialize dataclass fields only; numerical AAMI/BHS properties are not standards certification.
        bp_stats = asdict(evaluate_blood_pressure(truth, pred))
    return {"paired_rows": len(selected), "paired_subjects": len({r["subject_id"] for r in selected}),
            "metrics": output, "bp_engine_stats": bp_stats, "exclusion_reason_counts_nonexclusive": dict(excluded),
            "prediction_provenance_is_user_attested_not_model_training_audited": True,
            "loa_interpretation": "n<2 unusable; repeated rows/subject require repeated-measures analysis; no CI computed"}


def bp_gate(rows):
    valid = [r for r in rows if not label_reasons(r, "bp")]
    targets = np.asarray([[r["sbp_reference_mmhg"], r["dbp_reference_mmhg"]] for r in valid], dtype=float).reshape(-1, 2)
    return asdict(evaluate_data_sufficiency(targets, np.array([r["subject_id"] for r in valid])))


def build_report(rows, mode, seed, folds, target):
    validate_identity(rows)
    assignment_key = assign(rows, mode, seed, folds)
    assignments = sorted({(r["subject_id"], r[assignment_key]) for r in rows})
    assignment_sha256 = hashlib.sha256(json.dumps(assignments, ensure_ascii=True, separators=(",", ":")).encode()).hexdigest()
    for row in rows:
        reasons = qc_reasons(row, target)
        row["supervised_eligible"] = not reasons
        row["exclusion_reasons"] = ";".join(reasons)
    groups = {value: [r for r in rows if r[assignment_key] == value] for value in sorted({r[assignment_key] for r in rows})}
    eligible = [r for r in rows if r["supervised_eligible"]]
    report = {"scope": "local inventory snapshot and allocation; no model fit or clinical validation",
              "mode": mode, "seed": seed, "target": target,
              "folds": len(groups) if assignment_key == "candidate_fold" else None,
              "allocation_scope": "all inventoried subjects; eligible subsets reported separately",
              "assignment_sha256": assignment_sha256,
              "subject_leakage_detected": False, "input": distributions(rows), "eligible": distributions(eligible),
              "exclusion_reason_counts_nonexclusive": dict(Counter(x for r in rows for x in r["exclusion_reasons"].split(";") if x)),
              "partitions": {k: {"inventory": distributions(v), "eligible": distributions([r for r in v if r["supervised_eligible"]])} for k, v in groups.items()},
              "bp_gate_descriptive_label_cohort": bp_gate(rows), "bp_gate_eligible_cohort": bp_gate(eligible),
              "evaluation": paired_report(rows, target, "kfold" if assignment_key == "candidate_fold" else mode, assignment_sha256),
              "clinical_readiness": False}
    if assignment_key == "candidate_fold":
        report["fold_roles"] = {k: {"test_subjects": sorted({r["subject_id"] for r in v}),
                                    "train_subjects": sorted({r["subject_id"] for r in rows if r[assignment_key] != k}),
                                    "validation": "not assigned; use inner subject-grouped folds for tuning"} for k, v in groups.items()}
    report["usable_supervised_partitions"] = mode != "audit" and all(any(r["supervised_eligible"] for r in v) for v in groups.values())
    return report


def validate_output(path):
    out = path.resolve()
    if not out.is_relative_to(BASE.resolve()) or out == BASE.resolve() or "_run" not in out.name:
        raise ValueError("Output must be a new *_run* subdirectory inside docs/DatasetValidation_V1")
    if out.exists():
        raise FileExistsError("Output exists; choose a new run ID")
    return out


def write_json(path, data):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def write_csv(path, rows, fields=None):
    fields = fields or sorted({k for row in rows for k in row})
    with path.open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input-csv", type=Path, nargs="+")
    source.add_argument("--clbp-run", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--mode", choices=("holdout", "kfold", "existing", "audit"), default="holdout")
    parser.add_argument("--target", choices=("hr", "bp"), default="bp")
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        out = validate_output(args.output_dir)
        rows, sources = [], []
        if args.clbp_run:
            rows, sources = read_clbp(args.clbp_run.resolve())
        else:
            for path in args.input_csv:
                part, files = read_csv(path.resolve())
                rows.extend(part)
                sources.extend(files)
        # Hash inputs before processing, then verify unchanged before publishing a snapshot.
        source_hashes = {str(p): sha256(p) for p in sources}
        report = build_report(rows, args.mode, args.seed, args.folds, args.target)
        compact = {"rows": len(rows), "subjects": report["input"]["subjects"],
                   "eligible_rows": report["eligible"]["rows"], "paired_rows": report["evaluation"]["paired_rows"],
                   "subject_leakage_detected": False, "dry_run": args.dry_run}
        if args.dry_run:
            print(json.dumps(compact))
            return 0
        if source_hashes != {str(p): sha256(p) for p in sources}:
            raise ValueError("Source changed during audit")
        out.mkdir(parents=True, exist_ok=False)
        write_csv(out / "DATASET_SNAPSHOT.csv", rows)
        write_csv(out / "ELIGIBLE_ROWS.csv", [r for r in rows if r["supervised_eligible"]], sorted({k for r in rows for k in r}))
        write_json(out / "VALIDATION_REPORT.json", report)
        source_files = [ROOT / "aivitals_engine" / p for p in ENGINE_PATHS]
        source_files += [Path(__file__), *sorted(BASE.glob("*.md"))]
        lock = {"version": "1.0", "created_at_utc": datetime.now(timezone.utc).isoformat(),
                "status": "INVENTORY_SNAPSHOT_LOCKED", "training_dataset_ready": False,
                "inputs_sha256": source_hashes,
                "rules_and_code_sha256": {str(p.relative_to(ROOT)): sha256(p) for p in source_files},
                "artifacts_sha256": {p.name: sha256(p) for p in sorted(out.iterdir()) if p.is_file()},
                "runtime": {"python": sys.version, "numpy": np.__version__},
                "thresholds": {"sqi_ok": CONFIG.signal_quality_ok, "sqi_invalid": CONFIG.signal_quality_invalid},
                "arguments": {k: str(v) if isinstance(v, Path) else [str(p) for p in v] if isinstance(v, list) else v for k, v in vars(args).items()},
                "limitations": "Integrity snapshot only; input metadata assertions not independently certified; rights and reference QC still apply"}
        write_json(out / "DATASET_LOCK.json", lock)
        print(json.dumps(compact))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
