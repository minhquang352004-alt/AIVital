"""Restricted local CLBP pilot QC; no model fitting, facial exports or gate overrides."""
import argparse
import hashlib
import json
import math
import re
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def validate_rows(rows):
    if not rows:
        raise ValueError("No publisher reference rows")
    ids, names = set(), set()
    for row in rows:
        name = row["filename"]
        match = re.fullmatch(r"(Subject\d{3})_([MF])(\d+)_(\d+)_(\d+)_(\d+)_(\d+)\.mov", name)
        if not match or Path(name).name != name:
            raise ValueError("Unsafe/unrecognized filename")
        sid, sex, age, sbp, dbp, hr, lux = match.groups()
        expected = (row["subject_id"], "M" if row["sex"] == "Male" else "F",
                    *(str(row[k]) for k in ("age_years", "sbp_mmhg", "dbp_mmhg", "hr_bpm", "lux")))
        if (sid, sex, age, sbp, dbp, hr, lux) != expected:
            raise ValueError("Filename differs from verified publisher row")
        if sid in ids or name in names:
            raise ValueError("Duplicate subject/sample")
        if not all(math.isfinite(float(row[k])) for k in ("sbp_mmhg", "dbp_mmhg", "hr_bpm")):
            raise ValueError("Non-finite reference")
        if not row["sbp_mmhg"] > row["dbp_mmhg"] > 0 or row["hr_bpm"] <= 0:
            raise ValueError("Invalid reference ordering")
        ids.add(sid)
        names.add(name)


def validate_output(path):
    out = path.resolve()
    base = (ROOT / "docs/EvidenceMatrix_BP").resolve()
    if not out.is_relative_to(base) or out == base:
        raise ValueError("Output must be a new subdirectory of EvidenceMatrix_BP")
    if out.exists():
        raise FileExistsError("Output exists; use a new run ID")
    return out


def write_json(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")


def process(row, folder, out):
    import cv2
    import numpy as np
    from aivitals_engine.face.detector import SimpleFaceDetector
    from aivitals_engine.roi.extractor import ROIExtractor
    from aivitals_engine.rppg.pos import POSMethod
    from aivitals_engine.quality.sqi import calculate_bvp_quality
    from aivitals_engine.features.extractor import BVPFeatureExtractor
    from aivitals_engine.models.blood_pressure.features import Demographics, build_bp_features, build_feature_vector
    from aivitals_engine.contracts.bvp_window import BVPWindow
    from aivitals_engine.contracts.result import VitalCode, VitalsResult
    from aivitals_engine.integration.vitals_service import VitalsService
    from aivitals_engine.vitals.preprocess import detrend_signal
    from aivitals_engine.benchmark.team_methods import green_intensity

    class AuditDetector(SimpleFaceDetector):
        def __init__(self):
            super().__init__()
            self.fallbacks = 0

        def _fallback_bbox(self, frame):
            self.fallbacks += 1
            return super()._fallback_bbox(frame)

    video = folder / row["filename"]
    with video.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    cap = cv2.VideoCapture(str(video))
    try:
        if not cap.isOpened():
            raise ValueError("Video not readable")
        fps = cap.get(cv2.CAP_PROP_FPS)
        if not np.isfinite(fps) or fps <= 0:
            raise ValueError("Invalid FPS")
        rotation = cap.get(cv2.CAP_PROP_ORIENTATION_META)
        if not cap.set(cv2.CAP_PROP_ORIENTATION_AUTO, 1):
            raise ValueError("Container orientation handling unavailable")
        reported = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        detector, extractor = AuditDetector(), ROIExtractor()
        rgb, pts, selected_pts = [], [], []
        count, analyzed_size = 0, None
        next_progress = 0
        # Fixed first 30 s and every second frame, before looking at any result.
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            pts.append(float(cap.get(cv2.CAP_PROP_POS_MSEC)))
            if count % 2 == 0 and count / fps < 30:
                h, w = frame.shape[:2]
                scale = min(1.0, 640.0 / max(w, h))
                frame = cv2.resize(frame, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_AREA)
                analyzed_size = [frame.shape[1], frame.shape[0]]
                rgb.append(extractor.extract_mean_rgb(frame, detector.detect(frame)))
                selected_pts.append(pts[-1])
            if count / fps >= next_progress:
                print(f"{row['subject_id']}: decoded {count / fps:.0f}s", flush=True)
                next_progress += 10
            count += 1
    finally:
        cap.release()
    fs = fps / 2.0
    rgb = np.asarray(rgb)
    if len(rgb) < 16 or not np.all(np.isfinite(rgb)):
        raise ValueError("Insufficient finite RGB")
    method = POSMethod(fps=fs)
    bvp = method.process(rgb)
    sqi = calculate_bvp_quality(bvp, fs=fs)
    window = BVPWindow(samples=bvp, sampling_rate_hz=fs, start_timestamp=0.0,
                       method="POS", method_version=method.version, signal_quality=sqi,
                       raw_samples=detrend_signal(green_intensity(rgb)))
    sample_id = "CLBP_SAMPLE_" + row["subject_id"]
    result = VitalsService().compute(window, sample_id)
    raw = result.model_dump(mode="json")
    VitalsResult.model_validate(raw)
    features = BVPFeatureExtractor().extract(bvp, fs=fs)
    bp_fields = build_bp_features(result, features, Demographics(age_years=row["age_years"], sex_male=row["sex"] == "Male"))
    vector = build_feature_vector(bp_fields)
    hr = result.find_vital(VitalCode.HEART_RATE)
    deltas = np.diff(pts)
    selected_deltas = np.diff(selected_pts)
    label = {**row, "sample_id": sample_id, "subject_id": "CLBP_" + row["subject_id"],
             "video_sha256": digest, "video_size_bytes": video.stat().st_size,
             "label_scope": "publisher_session_spot_BP_not_per_frame", "label_verified_against_publisher_sheet": True,
             "reference_device_family": "Omron/Rossmax (dataset-level, per-subject model unknown)",
             "reference_device_model": None, "reference_measurement_intervals": None,
             "reference_repeat_readings": None, "capture_utc": None, "sync_error_ms": None,
             "strict_protocol_accepted": False, "license_review_required_before_training_or_sharing": True,
             "height_cm": None, "weight_kg": None, "fitzpatrick": None}
    evidence = {"sample_id": sample_id, "reported_frames": reported, "decoded_frames": count,
                "complete_decode_count_matches_header": reported == count,
                "reported_fps": fps, "decoded_duration_index_seconds": count / fps,
                "container_orientation_degrees": rotation, "opencv_orientation_auto_enabled": True,
                "analysis_frame_size_px": analyzed_size, "analysis_start_seconds": 0,
                "analysis_duration_seconds": len(rgb) / fs, "analysis_samples": len(rgb), "analysis_fps": fs,
                "pts_strictly_increasing": bool(np.all(deltas > 0)),
                "pts_delta_min_ms": float(deltas.min()), "pts_delta_max_ms": float(deltas.max()),
                "selected_pts_delta_min_ms": float(selected_deltas.min()),
                "selected_pts_delta_max_ms": float(selected_deltas.max()),
                "uniform_index_time_assumed": True, "independent_sensor_sync_verified": False,
                "detector_fallback_count": detector.fallbacks, "detector_fallback_ratio": detector.fallbacks / len(rgb),
                "sqi": sqi, "raw_engine_status": result.status.value,
                "hr_status": hr.status.value, "estimated_hr_bpm": hr.value,
                "hr_reference_session_summary_bpm": row["hr_bpm"], "hr_accuracy_error_bpm": None,
                "hr_error_not_computed_reason": "Reference averaging/support time unknown; HR output window differs from whole session",
                "valid_beat_count": features.valid_beat_count, "bp_feature_set_version": vector.feature_set_version,
                "missing_bp_features": vector.missing_names, "missing_bp_feature_ratio": vector.missing_ratio,
                "features": bp_fields,
                "training_eligible": False,
                "dataset_exclusions": ["REFERENCE_TIMING_UNVERIFIED", "CUFF_REPEATS_UNAVAILABLE", "LICENSE_REVIEW_REQUIRED"]}
    write_json(out / f"{sample_id}_raw_vitals.json", raw)
    write_json(out / f"{sample_id}_qc_features.json", evidence)
    print(f"{sample_id}: SQI={sqi}; HR={hr.status.value}; missing={vector.missing_ratio:.3f}", flush=True)
    return label, evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    source = json.loads((ROOT / "docs/EvidenceMatrix_BP/CLBP_SAMPLE_SOURCE_ROWS_V1.json").read_text(encoding="utf-8"))
    validate_rows(source["rows"])
    out = validate_output(args.output_dir)
    for row in source["rows"]:
        if not (args.input_dir / row["filename"]).is_file():
            parser.error("Missing source video: " + row["filename"])
    if args.dry_run:
        print("5 verified source rows; inputs exist; output safe/new; no files written")
        return
    import cv2
    import numpy as np
    from aivitals_engine.models.blood_pressure.gate import evaluate_data_sufficiency
    cv2.setNumThreads(1)
    out.mkdir(parents=True, exist_ok=False)
    labels, evidence = [], []
    for row in source["rows"]:
        label, qc = process(row, args.input_dir, out)
        labels.append(label)
        evidence.append(qc)
    gate = asdict(evaluate_data_sufficiency(np.array([[r["sbp_mmhg"], r["dbp_mmhg"]] for r in labels]),
                                           np.array([r["subject_id"] for r in labels])))
    write_json(out / "DATASET_V1_BP_PILOT_MANIFEST.json", {
        "version": "1.0-pilot", "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": {k: v for k, v in source.items() if k != "rows"},
        "samples": labels, "reported_bp_label_count": len(labels), "strict_protocol_accepted_count": 0,
        "intended_use": "restricted_local_research_QC_only_no_clinical_use",
        "subject_split": "Not fitted/split: 5 subjects, insufficient for meaningful held-out BP validation",
        "sampling_unit": "One publisher BP pair per subject/video; no clip inflation"})
    write_json(out / "BP_GATE_REPORT.json", {"publisher_label_cohort_gate": gate,
        "strict_training_eligible_count": 0, "strict_gate_passed": False,
        "bp_predictions_generated": 0, "bp_mae_mmhg": None, "bp_rmse_mmhg": None,
        "reason": "Five source-reported labels; no trained model or independently audited cuff timing/repeats"})
    write_json(out / "RUN_SUMMARY.json", {"completed": True, "samples": 5, "method": "offline POS first 30 seconds; max side 640; stride 2",
        "production_realtime_pipeline_tested": False, "source_videos_modified": False,
        "facial_frames_exported": False, "models_trained": 0,
        "hr_status_counts": {status: sum(q["hr_status"] == status for q in evidence) for status in ("OK", "BAD", "INVALID")},
        "raw_result_contract_checks": len(evidence), "gate_passed": gate["passed"]})
    print(json.dumps({"completed": True, "samples": 5, "publisher_label_gate": gate}, ensure_ascii=True), flush=True)


if __name__ == "__main__":
    main()
