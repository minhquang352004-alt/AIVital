"""Read a recording and export real engine evidence without fabricating reference data."""
import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--sample-id", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--rotate", type=int, choices=[0, 90, 180, 270], default=0)
    parser.add_argument("--method", choices=["POS", "CHROM", "GREEN"], default="POS")
    args = parser.parse_args()
    if not all(re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value) for value in (args.sample_id, args.session_id)):
        parser.error("Sample/session IDs must contain 1–64 letters, digits, underscores or hyphens")
    out = args.output_dir.resolve()
    allowed = [(ROOT / "docs" / "ReferenceDataset").resolve(), (ROOT / "docs" / "CollectionPackage_V1").resolve()]
    if not any(out.is_relative_to(base) and out != base for base in allowed):
        parser.error("Use a new subdirectory inside ReferenceDataset or CollectionPackage_V1")
    if out.exists():
        parser.error("Output directory already exists; choose a new run ID")
    if not args.video.is_file():
        parser.error("Video file not found")

    import cv2
    import numpy as np
    from aivitals_engine.contracts.result import VitalsResult
    from aivitals_engine.integration.frontend_mapper import to_measurement_result, to_measurement_patch
    from aivitals_engine.integration.realtime_vitals import RealtimeVitalsEngine
    from aivitals_engine.scripts.run_vitals_pipeline import rotate_frame
    from aivitals_engine.signal_pipeline_realtime import RealtimeSignalPipeline

    cv2.setNumThreads(1)  # Process-local scheduling only; no threshold/config changes.
    cap = cv2.VideoCapture(str(args.video))
    if not cap.isOpened():
        cap.release()
        parser.error("Video cannot be opened")
    fps = cap.get(cv2.CAP_PROP_FPS)
    if not np.isfinite(fps) or fps <= 0:
        cap.release()
        parser.error("Invalid reported FPS; do not invent capture timestamps")
    width, height = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    reported_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    out.mkdir(parents=True, exist_ok=False)
    engine = RealtimeVitalsEngine(args.session_id, pipeline=RealtimeSignalPipeline(method=args.method))
    started = datetime.now(timezone.utc).isoformat()
    statuses = Counter()
    frame_count, updates, max_window = 0, 0, 0.0
    last_pts, last_progress = None, -10.0
    with (out / "updates.jsonl").open("x", encoding="utf-8") as evidence:
        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                ts = frame_count / fps
                last_pts = cap.get(cv2.CAP_PROP_POS_MSEC)
                update = engine.process_frame(rotate_frame(frame, args.rotate), ts)
                statuses[update.frame.status] += 1
                if update.has_new_vitals:
                    updates += 1
                    max_window = max(max_window, update.window_seconds)
                    evidence.write(json.dumps({"video_time_seconds": ts, "window_seconds": update.window_seconds,
                        "sqi": update.frame.quality_sqi, "engine_result": update.vitals.model_dump(mode="json")}, ensure_ascii=False) + "\n")
                    evidence.flush()
                if ts - last_progress >= 10:
                    print(f"Processed {ts:.1f}s; updates={updates}", flush=True)
                    last_progress = ts
                frame_count += 1
        finally:
            cap.release()

    latest = engine.latest_result
    raw = None if latest is None else latest.model_dump(mode="json")
    if raw is not None:
        VitalsResult.model_validate(raw)  # Runtime contract, no rewriting invalid values.
    frontend = {"result": to_measurement_result(latest, args.session_id)}
    if latest is not None:
        frontend["patch"] = to_measurement_patch(latest)
    with args.video.open("rb") as video_stream:
        digest = hashlib.file_digest(video_stream, "sha256").hexdigest()
    summary = {"sample_id": args.sample_id, "session_id": args.session_id, "run_started_at": started,
        "run_finished_at": datetime.now(timezone.utc).isoformat(), "video_filename": args.video.name,
        "video_sha256": digest, "width_px": width, "height_px": height, "fps_actual": fps,
        "reported_frames": reported_frames, "decoded_frames": frame_count,
        "video_duration_sec": frame_count / fps, "last_decoded_pts_ms": last_pts,
        "rotation_clockwise_degrees": args.rotate, "method": args.method,
        "frame_status_counts": dict(statuses), "updates": updates, "max_computed_window_seconds": max_window,
        "engine_status": None if latest is None else latest.status.value,
        "frontend_status": frontend["result"]["status"], "quality_score": frontend["result"].get("quality_score"),
        "reference_available": False, "reference_hr_bpm": None, "reference_sbp_mmhg": None,
        "reference_dbp_mmhg": None, "sync_error_ms": None, "consent_verified": False,
        "collection_timestamp": None, "video_timing_verified_cfr": False,
        "dataset_quality_label": "REJECT", "dataset_exclusion_reason": "MISSING_REFERENCE",
        "notes": "Video-only. Decode timing is not capture UTC or proof of CFR/sync. Reference/consent not supplied."}
    for name, content in [("raw_vitals_result.json", raw), ("frontend_result.json", frontend), ("qc_summary.json", summary)]:
        (out / name).write_text(json.dumps(content, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    metadata = json.loads((ROOT / "docs/CollectionPackage_V1/SESSION_METADATA_TEMPLATE.json").read_text(encoding="utf-8"))
    for field in ("sample_id", "session_id", "video_filename", "width_px", "height_px", "fps_actual", "video_duration_sec", "engine_status"):
        metadata[field] = summary[field]
    metadata.update(session_mode="video_only", video_timebase="decoder index / reported FPS; capture UTC unknown",
                    quality_label="REJECT", exclusion_reason="MISSING_REFERENCE", video_quality="WARNING" if summary["frontend_status"] == "READY" else "REJECT",
                    engine_result_filename="raw_vitals_result.json" if raw else None, notes=summary["notes"])
    if latest:
        metadata["engine_issue_codes"] = ";".join(sorted({issue.code for vital in latest.vitals for issue in vital.issues} | {issue.code for issue in latest.issues}))
    (out / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (out / "metadata.csv").open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(metadata))
        writer.writeheader()
        writer.writerow({key: "" if value is None else value for key, value in metadata.items()})
    print(json.dumps(summary, ensure_ascii=True), flush=True)


if __name__ == "__main__":
    main()
