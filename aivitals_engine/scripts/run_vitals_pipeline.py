import argparse
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import cv2

from aivitals_engine.integration.frontend_mapper import to_measurement_patch, to_measurement_result
from aivitals_engine.integration.realtime_vitals import RealtimeVitalsEngine
from aivitals_engine.signal_pipeline_realtime import RealtimeSignalPipeline

DEFAULT_VIDEO = os.path.join(PROJECT_ROOT, "aivitals_engine", "samples", "sample_video.mp4")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Chạy Camera → BVP (Khang) → HR/HRV/RR + Validation (Khoa) → JSON cho Frontend")
    parser.add_argument("--video", default=DEFAULT_VIDEO)
    parser.add_argument("--method", default="POS", choices=["GREEN", "CHROM", "POS"])
    parser.add_argument("--max-sec", type=float, default=None)
    parser.add_argument("--measurement-id", default="demo-measurement")
    return parser


def format_vital(result, code: str) -> str:
    vital = next(v for v in result.vitals if v.code.value == code)
    value = "-" if vital.value is None else f"{vital.value:g}"
    issues = ",".join(issue.code for issue in vital.issues)
    return f"{code}={value} {vital.status.value}" + (f" [{issues}]" if issues else "")


def run(video_path: str, method: str, max_sec: float | None, measurement_id: str) -> dict:
    capture = cv2.VideoCapture(video_path)
    if not capture.isOpened():
        raise FileNotFoundError(f"Không mở được video: {video_path}")
    fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
    engine = RealtimeVitalsEngine(session_id=measurement_id, pipeline=RealtimeSignalPipeline(method=method))
    index = 0
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        timestamp = index / fps
        if max_sec is not None and timestamp > max_sec:
            break
        update = engine.process_frame(frame, timestamp)
        if update.has_new_vitals:
            summary = " | ".join(
                format_vital(update.vitals, code) for code in ("heart_rate", "hrv_rmssd", "respiratory_rate")
            )
            print(f"t={timestamp:5.1f}s window={update.window_seconds:4.1f}s sqi={update.frame.quality_sqi:.2f} {summary}")
        index += 1
    capture.release()
    result = engine.latest_result
    output = {"result": to_measurement_result(result, measurement_id)}
    if result is not None:
        output["patch"] = to_measurement_patch(result)
    return output


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    arguments = build_parser().parse_args()
    output = run(arguments.video, arguments.method, arguments.max_sec, arguments.measurement_id)
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
