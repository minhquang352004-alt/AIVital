"""
run_signal_pipeline.py
======================
Script mô phỏng luồng camera thời gian thực trên video để kiểm thử toàn bộ Signal Pipeline (Khang):

    Video (.avi / .mp4) → Frame-by-frame (stream simulation)
        → SimpleFaceDetector  (Haar cascade + EMA smoother)
        → ROIExtractor        (Trán + Má trái + Má phải)
        → SlidingWindowBuffer (8s, artifact detection, time-gap guard)
        → rPPGMethod          (GREEN / CHROM / POS)
        → BVP signal + SQI
        → FrameResult         (Chỉ số chất lượng SQI + Sóng BVP + Ước lượng HR)

Cách chạy (từ thư mục gốc AIVital/):
    python aivitals_engine/scripts/run_signal_pipeline.py
    python aivitals_engine/scripts/run_signal_pipeline.py --video aivitals_engine/samples/vid.avi
    python aivitals_engine/scripts/run_signal_pipeline.py --method CHROM
    python aivitals_engine/scripts/run_signal_pipeline.py --max-sec 60
    python aivitals_engine/scripts/run_signal_pipeline.py --all-methods
"""

import argparse
import os
import sys
import time

# Script nằm ở aivitals_engine/scripts/ → đi 2 cấp lên để ra AIVital/ (project root)
SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Fix encoding trên Windows terminal
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import cv2
import numpy as np

from aivitals_engine.signal_pipeline_realtime import RealtimeSignalPipeline, FrameResult
from aivitals_engine.vitals.hr import calculate_fft_hr, calculate_peak_hr


# ──────────────────────────────────────────────────────────────────────────────
# Chạy pipeline trên 1 video với 1 method
# ──────────────────────────────────────────────────────────────────────────────

def run_pipeline_on_video(
    video_path: str,
    method: str = "POS",
    max_sec: float = None,
    verbose: bool = True,
) -> dict:
    """
    Đọc video frame-by-frame, chạy qua toàn bộ RealtimeSignalPipeline,
    thu thập thống kê và trả về report dict.

    Args:
        video_path: Đường dẫn video (.avi / .mp4).
        method:     "GREEN", "CHROM", hoặc "POS".
        max_sec:    Giới hạn số giây xử lý (None = xử lý hết video).
        verbose:    In progress mỗi giây.

    Returns:
        dict chứa toàn bộ thống kê.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Không thể mở video: {video_path}")

    video_fps    = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    max_frames   = int(max_sec * video_fps) if max_sec else total_frames

    if verbose:
        print(f"\n{'─'*60}")
        print(f"  Method  : {method}")
        print(f"  Video   : {os.path.basename(video_path)}")
        print(f"  FPS     : {video_fps:.1f}")
        print(f"  Frames  : {total_frames:,} ({total_frames/video_fps:.1f}s)")
        if max_sec:
            print(f"  Giới hạn: {max_sec}s đầu ({max_frames:,} frames)")
        print(f"{'─'*60}")

    pipeline = RealtimeSignalPipeline(method=method)

    # ── Thống kê ──────────────────────────────────────────────────────────────
    stats = {
        "method":          method,
        "video_fps":       video_fps,
        "frames_total":    0,
        "frames_face_ok":  0,
        "frames_artifact": 0,
        "frames_face_lost":0,
        "frames_ready":    0,
        "frames_ok":       0,
        "frames_low_q":    0,
        "sqi_list":        [],
        "bvp_last":        None,
        "fps_effective":   0.0,
        "hr_fft":          0.0,
        "hr_peak":         0.0,
        "elapsed_sec":     0.0,
    }

    last_print_time = time.perf_counter()
    t_start         = time.perf_counter()
    frame_idx       = 0

    while frame_idx < max_frames:
        ret, frame = cap.read()
        if not ret:
            break

        timestamp = frame_idx / video_fps
        result: FrameResult = pipeline.process_frame(frame, timestamp=timestamp)

        # ── Tích lũy thống kê ─────────────────────────────────────────────────
        stats["frames_total"] += 1

        if result.status == "FACE_LOST":
            stats["frames_face_lost"] += 1
        elif result.status == "ARTIFACT":
            stats["frames_artifact"] += 1
        else:
            stats["frames_face_ok"] += 1

        if result.is_ready:
            stats["frames_ready"] += 1
            stats["sqi_list"].append(result.quality_sqi)
            stats["bvp_last"]      = result.bvp_signal
            stats["fps_effective"] = result.fps

            if result.status == "OK":
                stats["frames_ok"] += 1
            elif result.status == "LOW_QUALITY":
                stats["frames_low_q"] += 1

        # ── In progress mỗi giây ──────────────────────────────────────────────
        if verbose:
            now = time.perf_counter()
            if now - last_print_time >= 1.0:
                pct      = frame_idx / max_frames * 100
                elapsed  = now - t_start
                eta      = (elapsed / (frame_idx + 1)) * (max_frames - frame_idx)
                sqi_disp = f"{result.quality_sqi:.2f}" if result.is_ready else "  — "
                print(
                    f"  [{pct:5.1f}%] frame={frame_idx:5d} | "
                    f"status={result.status:<12} | "
                    f"progress={result.progress:.0%} | "
                    f"SQI={sqi_disp} | "
                    f"ETA={eta:.0f}s"
                )
                last_print_time = now

        frame_idx += 1

    cap.release()
    stats["elapsed_sec"] = time.perf_counter() - t_start

    # ── Tính HR từ BVP cuối ───────────────────────────────────────────────────
    if stats["bvp_last"] is not None and len(stats["bvp_last"]) > 0:
        stats["hr_fft"]  = calculate_fft_hr(stats["bvp_last"],  fs=stats["fps_effective"])
        stats["hr_peak"] = calculate_peak_hr(stats["bvp_last"], fs=stats["fps_effective"])

    return stats


# ──────────────────────────────────────────────────────────────────────────────
# In report
# ──────────────────────────────────────────────────────────────────────────────

def print_report(stats: dict) -> None:
    method       = stats["method"]
    n            = stats["frames_total"]
    sqi_list     = stats["sqi_list"]
    sqi_arr      = np.array(sqi_list) if sqi_list else np.array([0.0])
    face_rate    = stats["frames_face_ok"] / n * 100 if n > 0 else 0
    ready_rate   = stats["frames_ready"]   / n * 100 if n > 0 else 0
    ok_rate      = stats["frames_ok"]      / stats["frames_ready"] * 100 if stats["frames_ready"] > 0 else 0

    print(f"\n{'═'*60}")
    print(f"  KẾT QUẢ VALIDATE — Method: {method}")
    print(f"{'═'*60}")
    print(f"  Tổng frames xử lý   : {n:,}")
    print(f"  Thời gian chạy      : {stats['elapsed_sec']:.1f}s")
    print(f"  FPS pipeline        : {n / stats['elapsed_sec']:.1f} frames/s")
    print()
    print(f"  ── Face Detection ──────────────────────────────")
    print(f"  Face OK             : {stats['frames_face_ok']:,}  ({face_rate:.1f}%)")
    print(f"  Face Lost           : {stats['frames_face_lost']:,}")
    print(f"  Artifact rejected   : {stats['frames_artifact']:,}")
    print()
    print(f"  ── BVP Signal ──────────────────────────────────")
    print(f"  Buffer ready        : {stats['frames_ready']:,}  ({ready_rate:.1f}%)")
    print(f"  Status OK           : {stats['frames_ok']:,}  ({ok_rate:.1f}% of ready)")
    print(f"  Status LOW_QUALITY  : {stats['frames_low_q']:,}")
    print()
    print(f"  ── Signal Quality (SQI) ────────────────────────")
    if len(sqi_list) > 0:
        print(f"  SQI mean            : {sqi_arr.mean():.3f}")
        print(f"  SQI median          : {np.median(sqi_arr):.3f}")
        print(f"  SQI min             : {sqi_arr.min():.3f}")
        print(f"  SQI max             : {sqi_arr.max():.3f}")
        print(f"  Frames SQI >= 0.7   : {(sqi_arr >= 0.7).sum():,}  (tốt)")
        print(f"  Frames SQI 0.4-0.7  : {((sqi_arr >= 0.4) & (sqi_arr < 0.7)).sum():,}  (trung bình)")
        print(f"  Frames SQI < 0.4    : {(sqi_arr < 0.4).sum():,}  (kém)")
    else:
        print(f"  Không có frame nào đủ buffer để tính SQI")
    print()
    print(f"  ── Ước lượng HR (từ BVP cuối) ──────────────────")
    if stats["hr_fft"] > 0:
        print(f"  HR (FFT)            : {stats['hr_fft']:.1f} BPM")
        print(f"  HR (Peak detection) : {stats['hr_peak']:.1f} BPM")
    else:
        print(f"  Không đủ BVP để ước lượng HR")
    print(f"{'═'*60}")


# ──────────────────────────────────────────────────────────────────────────────
# Save BVP to CSV
# ──────────────────────────────────────────────────────────────────────────────

def save_bvp(stats: dict, output_dir: str) -> None:
    import pandas as pd
    if stats["bvp_last"] is None:
        return
    method = stats["method"].lower()
    path   = os.path.join(output_dir, f"validate_{method}_bvp.csv")
    os.makedirs(output_dir, exist_ok=True)
    df = pd.DataFrame({
        "sample_index": np.arange(len(stats["bvp_last"])),
        "bvp":          stats["bvp_last"],
    })
    df.to_csv(path, index=False)
    print(f"  BVP saved → {path}")


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Kiểm thử và đánh giá Signal Pipeline (Face/ROI -> Buffer -> rPPG -> BVP + SQI) trên video thực tế"
    )
    default_video = os.path.join(PROJECT_ROOT, "aivitals_engine", "samples", "vid.avi")
    default_out   = os.path.join(PROJECT_ROOT, "aivitals_engine", "outputs")

    parser.add_argument(
        "--video", "-v",
        default=default_video,
        help=f"Đường dẫn video (mặc định: {os.path.basename(default_video)})"
    )
    parser.add_argument(
        "--method", "-m",
        default="POS",
        choices=["GREEN", "CHROM", "POS"],
        help="Thuật toán rPPG (mặc định: POS)"
    )
    parser.add_argument(
        "--all-methods",
        action="store_true",
        help="Chạy cả 3 method GREEN / CHROM / POS và so sánh"
    )
    parser.add_argument(
        "--max-sec", "-s",
        type=float,
        default=None,
        help="Giới hạn số giây xử lý (mặc định: xử lý hết video)"
    )
    parser.add_argument(
        "--output-dir", "-o",
        default=default_out,
        help="Thư mục lưu BVP output"
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Tắt progress output"
    )
    args = parser.parse_args()

    if not os.path.exists(args.video):
        print(f"[ERROR] Không tìm thấy video: {args.video}")
        sys.exit(1)

    methods = ["GREEN", "CHROM", "POS"] if args.all_methods else [args.method]

    all_stats = []
    for method in methods:
        stats = run_pipeline_on_video(
            video_path = args.video,
            method     = method,
            max_sec    = args.max_sec,
            verbose    = not args.quiet,
        )
        print_report(stats)
        save_bvp(stats, args.output_dir)
        all_stats.append(stats)

    # ── So sánh nhanh nếu chạy all-methods ────────────────────────────────────
    if args.all_methods and len(all_stats) == 3:
        print(f"\n{'─'*60}")
        print(f"  SO SÁNH 3 METHODS")
        print(f"{'─'*60}")
        print(f"  {'Method':<8} | {'HR FFT':>8} | {'HR Peak':>8} | {'SQI mean':>9} | {'Ready%':>7}")
        print(f"  {'─'*8}-+-{'─'*8}-+-{'─'*8}-+-{'─'*9}-+-{'─'*7}")
        for s in all_stats:
            sqi_arr   = np.array(s["sqi_list"]) if s["sqi_list"] else np.array([0.0])
            ready_pct = s["frames_ready"] / s["frames_total"] * 100 if s["frames_total"] > 0 else 0
            print(
                f"  {s['method']:<8} | {s['hr_fft']:>7.1f}  | {s['hr_peak']:>7.1f}  "
                f"| {sqi_arr.mean():>9.3f} | {ready_pct:>6.1f}%"
            )
        print(f"{'─'*60}")


if __name__ == "__main__":
    main()
