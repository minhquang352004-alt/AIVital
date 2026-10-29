"""Exploratory POS HR comparison on a public MPU sample, with explicit alignment assumptions."""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def main():
    import cv2
    import numpy as np
    from aivitals_engine.face.detector import SimpleFaceDetector
    from aivitals_engine.roi.extractor import ROIExtractor
    from aivitals_engine.rppg.pos import POSMethod
    from aivitals_engine.quality.sqi import calculate_bvp_quality
    from aivitals_engine.contracts.bvp_window import BVPWindow
    from aivitals_engine.contracts.result import VitalCode, VitalsResult
    from aivitals_engine.integration.vitals_service import VitalsService
    from aivitals_engine.benchmark.team_methods import green_intensity
    from aivitals_engine.vitals.preprocess import detrend_signal

    cache = ROOT / "docs/ReferenceDataset/external_cache/mpu_public_sample"
    out = ROOT / "docs/ReferenceDataset/mpu_public_benchmark_run01"
    if out.exists():
        raise FileExistsError("Benchmark output exists; do not overwrite")
    with (cache / "55553426_Output.csv").open(encoding="utf-8-sig") as reference_stream:
        reference = list(csv.DictReader(reference_stream))
    counts = np.array([float(row["Count"]) for row in reference])
    ref_hr = np.array([float(row["HR"]) for row in reference])
    ref_ppg = np.array([float(row["PPG"]) for row in reference])
    if not np.all(np.isfinite(ref_hr)) or not np.all(np.diff(counts) == 1) or counts[0] != 0:
        raise ValueError("Invalid reference indexing/data")
    cv2.setNumThreads(1)
    capture = cv2.VideoCapture(str(cache / "55553429_Output.mp4"))
    fps = capture.get(cv2.CAP_PROP_FPS)
    total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    if not capture.isOpened() or fps != 60 or total != len(reference):
        capture.release()
        raise ValueError("Candidate video/reference count or 60 Hz assumption failed")
    detector, extractor = SimpleFaceDetector(), ROIExtractor()
    rgb, index = [], 0
    try:
        while index < 3600:  # Predeclared first 60 s; two 30 s windows, no result-based selection.
            ok, frame = capture.read()
            if not ok:
                raise ValueError("Early video end")
            if index % 2 == 0:  # Explicit 60 -> 30 Hz analysis decimation; original timeline preserved.
                bbox = detector.detect(frame)
                if bbox is None:
                    raise ValueError("No usable ROI")
                rgb.append(extractor.extract_mean_rgb(frame, bbox))
            index += 1
            if index % 600 == 0:
                print(f"Extracted {index / fps:.0f}s", flush=True)
    finally:
        capture.release()
    rgb = np.asarray(rgb)
    out.mkdir(parents=True, exist_ok=False)
    comparisons = []
    for number in range(2):
        start = number * 30
        segment = rgb[number * 900:(number + 1) * 900]
        method = POSMethod(fps=30.0)
        bvp = method.process(segment)
        sqi = calculate_bvp_quality(bvp, fs=30.0)
        window = BVPWindow(samples=bvp, sampling_rate_hz=30.0, start_timestamp=float(start),
                           method="POS", method_version=method.version, signal_quality=sqi,
                           raw_samples=detrend_signal(green_intensity(segment)))
        result = VitalsService().compute(window, f"mpu-public-window-{number + 1}")
        raw = result.model_dump(mode="json")
        VitalsResult.model_validate(raw)
        (out / f"window_{number + 1}_raw_result.json").write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")
        hr = result.find_vital(VitalCode.HEART_RATE)
        # Runtime contract timestamps use synthetic epoch for relative windows, not real capture UTC.
        support_start = hr.window.start.timestamp()
        support_end = hr.window.end.timestamp()
        lo, hi = int(round(support_start * fps)), int(round(support_end * fps))
        values = ref_hr[lo:hi]
        pulse = ref_ppg[lo:hi]
        if not len(values) or not np.all(values > 0) or np.std(pulse) == 0:
            raise ValueError("Reference support empty/invalid")
        reference_mean = float(np.mean(values))
        comparison = {"window": number + 1, "analysis_start_seconds": start,
            "analysis_end_seconds": start + 30, "hr_support_start_seconds": support_start,
            "hr_support_end_seconds": support_end, "reference_hr_bpm": reference_mean,
            "estimated_hr_bpm": hr.value, "hr_status": hr.status.value,
            "sqi": sqi, "confidence": hr.confidence, "issues": ";".join(issue.code for issue in hr.issues),
            "signed_error_bpm": None if hr.value is None else float(hr.value - reference_mean),
            "alignment_assumed": True, "independent_sample_sync_verified": False}
        comparisons.append(comparison)
    evaluated = [row for row in comparisons if row["signed_error_bpm"] is not None]
    errors = np.array([row["signed_error_bpm"] for row in evaluated])
    summary = {"source": "https://doi.org/10.6084/m9.figshare.29377835", "video_file_id": 55553429,
        "reference_file_id": 55553426, "license": "CC BY 4.0", "original_video_fps": fps,
        "video_frames": total, "reference_rows": len(reference), "analysis_fps": 30.0,
        "windows_attempted": 2, "windows_with_estimate": len(evaluated),
        "windows_ok": sum(row["hr_status"] == "OK" for row in comparisons),
        "mae_bpm_exploratory": float(np.mean(np.abs(errors))) if len(errors) else None,
        "rmse_bpm_exploratory": float(np.sqrt(np.mean(errors ** 2))) if len(errors) else None,
        "bias_bpm_exploratory": float(np.mean(errors)) if len(errors) else None,
        "sync_error_ms": None, "strict_reference_acceptance": False,
        "assumptions": ["Adjacent CSV/video IDs with exactly 34496 rows/frames; candidate pairing, no released per-file manifest verified",
            "Paper states reference 60 Hz and alignment; Count index is treated as aligned video-frame index for this exploratory test",
            "CSV has no timestamp column; sample-specific offset/drift/residual not independently verifiable",
            "Synthetic epoch in raw contract encodes relative time only; no capture UTC inferred",
            "Offline ROI/POS comparison, not identical to production realtime quality gate; no thresholds changed"],
        "limitations": "One public candidate, two windows; no subject generalization/clinical accuracy claim. Metrics include non-null BAD estimates and are not a strict PASS."}
    (out / "benchmark_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    with (out / "hr_comparison.csv").open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(comparisons[0]))
        writer.writeheader()
        writer.writerows(comparisons)
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
