"""
scripts/benchmarks/bench_week8_device_matrix_qa.py
==================================================
Kiểm thử Ma trận Thiết bị (Device Matrix) trực tiếp trên video thực tế (vid.avi),
xác nhận sửa lỗi rPPG/ROI/SQI và chốt phiên bản thuật toán (Algorithm Freeze Sign-off) cho Tuần 8.

Chạy từ thư mục gốc AIVital/:
    python scripts/benchmarks/bench_week8_device_matrix_qa.py
"""
import argparse
from functools import lru_cache
import os
import sys
import time
from typing import List, Optional, Tuple

import cv2
import numpy as np

# Đảm bảo import được package trong dự án khi chạy trực tiếp từ CLI
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from aivitals_engine.rppg.pos import POSMethod
from aivitals_engine.signal.resample import resample_to_fixed_fps
from aivitals_engine.signal_pipeline_realtime import RealtimeSignalPipeline

DEFAULT_VIDEO_PATH = os.path.join(PROJECT_ROOT, "aivitals_engine", "samples", "vid.avi")
STEADY_START_FRAME = 150  # Bỏ qua 5s đầu người đo đang chỉnh tư thế trong vid.avi


@lru_cache(maxsize=4)
def load_real_video_segment(
    video_path: str = DEFAULT_VIDEO_PATH,
    start_frame: int = STEADY_START_FRAME,
    max_frames: Optional[int] = None,
) -> Tuple[List[np.ndarray], float]:
    """
    Đọc phân đoạn khung hình thực tế từ vid.avi.
    Nếu max_frames is None hoặc max_frames <= 0, đọc toàn bộ video từ start_frame.
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Không tìm thấy video chuẩn tại: {video_path}")

    cap = cv2.VideoCapture(video_path)
    src_fps = float(cap.get(cv2.CAP_PROP_FPS) or 28.671786)
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    frames: List[np.ndarray] = []
    while True:
        if max_frames is not None and max_frames > 0 and len(frames) >= max_frames:
            break
        ret, frame = cap.read()
        if not ret or frame is None:
            break
        frames.append(frame)
    cap.release()

    if not frames:
        raise RuntimeError(f"Không đọc được khung hình nào từ {video_path}")
    return frames, src_fps


def estimate_hr_bpm(bvp: np.ndarray, fps: float) -> float:
    """Ước lượng nhịp tim (BPM) từ phổ FFT của tín hiệu BVP."""
    nfft = 8192
    spec = np.abs(np.fft.rfft(bvp - np.mean(bvp), n=nfft))
    freqs = np.fft.rfftfreq(nfft, d=1.0 / fps)
    band = (freqs >= 0.75) & (freqs <= 2.50)
    return float(freqs[band][np.argmax(spec[band])] * 60.0)


def run_device_profile(
    profile_name: str,
    width: int,
    height: int,
    fps: float,
    jitter_std_sec: float = 0.0,
    duration_sec: float = 0.0,
    raw_frames: List[np.ndarray] = None,
    src_fps: float = 28.671786,
    ref_hr_bpm: float = 76.90,
) -> dict:
    """
    Chạy thực nghiệm luồng khung hình từ vid.avi được biến đổi theo cấu hình thiết bị
    (co giãn độ phân giải width x height, lấy mẫu lại ở tần số fps và nhiễu jitter).
    Nếu duration_sec <= 0.0, chạy toàn bộ video có sẵn trong raw_frames.
    """
    if raw_frames is None:
        needed_frames = None if duration_sec <= 0.0 else max(int(duration_sec * src_fps) + 10, 180)
        raw_frames, src_fps = load_real_video_segment(max_frames=needed_frames)

    total_avail_sec = len(raw_frames) / src_fps
    avail_duration = total_avail_sec if duration_sec <= 0.0 else min(duration_sec, total_avail_sec)
    rng = np.random.default_rng(42)
    pipe = RealtimeSignalPipeline(
        window_sec=8.0,
        min_sec=3.0,
        target_fps=30.0,
        method="POS",
    )

    n_frames = int(avail_duration * fps)
    latencies_ms = []
    sqi_ready = []
    hr_ready = []
    last_ready_res = None
    res = None

    for i in range(n_frames):
        ts = i / fps
        if jitter_std_sec > 0.0 and i > 0:
            ts += float(rng.uniform(-jitter_std_sec, jitter_std_sec))
            ts = max(ts, (i - 0.8) / fps)

        src_idx = min(int(round(ts * src_fps)), len(raw_frames) - 1)
        frame = raw_frames[src_idx]
        if (width, height) != (frame.shape[1], frame.shape[0]):
            frame = cv2.resize(frame, (width, height), interpolation=cv2.INTER_LINEAR)

        t0 = time.perf_counter()
        res = pipe.process_frame(frame, timestamp=ts)
        latencies_ms.append((time.perf_counter() - t0) * 1000.0)

        if res.is_ready and res.bvp_signal is not None and res.status in ["OK", "ACCEPTED"]:
            sqi_ready.append(float(res.quality_sqi))
            hr_val = estimate_hr_bpm(res.bvp_signal, res.fps)
            hr_ready.append(hr_val)
            last_ready_res = res
        elif res.is_ready and res.bvp_signal is not None:
            if last_ready_res is None:
                last_ready_res = res

    # Snapshot kết quả: ưu tiên cửa sổ đo ổn định gần nhất thay vì frame cuối (thường bị nhiễu do tắt cam)
    eval_res = last_ready_res if (last_ready_res is not None) else res

    med_ms = float(np.median(latencies_ms))
    if hr_ready:
        hr_est = float(np.median(hr_ready))
    elif eval_res and eval_res.bvp_signal is not None:
        hr_est = estimate_hr_bpm(eval_res.bvp_signal, eval_res.fps)
    else:
        hr_est = 0.0

    hr_err = abs(hr_est - ref_hr_bpm)
    final_sqi = float(np.mean(sqi_ready)) if sqi_ready else (float(eval_res.quality_sqi) if eval_res else 0.0)
    final_status = "OK" if len(sqi_ready) > 0 else (eval_res.status if eval_res else "NONE")

    # Thu thập cảnh báo từ phiên đo (nếu có cảnh báo hệ thống như LOW_FPS)
    warnings_set = set(eval_res.warnings if eval_res else [])
    if fps < 20.0:
        warnings_set.add("LOW_FPS")

    return {
        "profile": profile_name,
        "res": f"{width}x{height}@{int(fps)}fps",
        "median_ms": med_ms,
        "sqi": final_sqi,
        "mean_sqi": final_sqi,
        "hr_bpm": hr_est,
        "hr_err_bpm": hr_err,
        "status": final_status,
        "warnings": list(warnings_set),
        "pipeline": pipe,
    }


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="AIVitals Signal Engine - Week 8 Device Matrix & Algorithm Freeze QA Sign-off"
    )
    parser.add_argument(
        "--duration", "-d",
        type=float,
        default=0.0,
        help="Thời lượng video cần chạy (giây). Mặc định 0.0 = toàn bộ video (~78-84s). Đặt 10 để chạy 10 giây.",
    )
    parser.add_argument(
        "--video", "-v",
        type=str,
        default=DEFAULT_VIDEO_PATH,
        help=f"Đường dẫn file video. Mặc định: {DEFAULT_VIDEO_PATH}",
    )
    parser.add_argument(
        "--start-frame", "-s",
        type=int,
        default=STEADY_START_FRAME,
        help=f"Khung hình bắt đầu đọc (bỏ qua frame đầu). Mặc định: {STEADY_START_FRAME}",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    max_frames = None if args.duration <= 0.0 else max(int(args.duration * 28.671786) + 30, 180)
    raw_frames, src_fps = load_real_video_segment(
        video_path=args.video,
        start_frame=args.start_frame,
        max_frames=max_frames,
    )
    total_avail_sec = len(raw_frames) / src_fps
    duration_sec = total_avail_sec if args.duration <= 0.0 else min(args.duration, total_avail_sec)
    mode_str = f"toàn bộ video ({duration_sec:.1f}s)" if args.duration <= 0.0 else f"tùy chọn {duration_sec:.1f}s"

    print("=" * 88)
    print("  AIVITALS SIGNAL ENGINE - WEEK 8 DEVICE MATRIX & ALGORITHM FREEZE QA SIGN-OFF")
    print(f"  Video Source : {args.video} ({len(raw_frames)} frames @ {src_fps:.2f} FPS, {mode_str})")
    print("  Face Detector: Google MediaPipe Face Mesh (478 landmarks, Active)")
    print("=" * 88)

    # Chạy cấu hình chuẩn Native 640x480@30fps trước để lấy nhịp tim tham chiếu thực tế của vid.avi
    ref_run = run_device_profile(
        "2. Standard Laptop/Web (MVP)   ",
        640,
        480,
        30.0,
        jitter_std_sec=0.0,
        duration_sec=duration_sec,
        raw_frames=raw_frames,
        src_fps=src_fps,
        ref_hr_bpm=0.0,
    )
    ref_hr_bpm = ref_run["hr_bpm"]
    ref_run["hr_err_bpm"] = 0.0

    profiles = [
        ("1. HD Desktop Webcam (CFR)     ", 1280, 720, 30.0, 0.000),
        ("2. Standard Laptop/Web (MVP)   ", 640,  480, 30.0, 0.000),
        ("3. Low-Spec Mobile / QVGA      ", 320,  240, 24.0, 0.000),
        ("4. High-FPS Camera (BP Mode)   ", 640,  480, 60.0, 0.000),
        ("5. USB Webcam VFR Jitter (±4ms)", 640,  480, 25.0, 0.004),
        ("6. Throttled Tab Low-FPS       ", 640,  480, 15.0, 0.000),
    ]

    print(f"\nREAL VIDEO DEVICE MATRIX (6 CAMERA PROFILES ON vid.avi, REF HR = {ref_hr_bpm:.2f} BPM):")
    print(f"  {'Device Profile':<33} | {'Config':<14} | {'Lat(med)':<9} | {'SQI':<5} | {'HR (ΔRef)':<15} | {'Status / Gate'}")
    print("  " + "-" * 84)

    for label, w, h, fps, jitter in profiles:
        if label.startswith("2."):
            r = ref_run
        else:
            r = run_device_profile(
                label,
                w,
                h,
                fps,
                jitter_std_sec=jitter,
                duration_sec=duration_sec,
                raw_frames=raw_frames,
                src_fps=src_fps,
                ref_hr_bpm=ref_hr_bpm,
            )
        gate_note = r["status"]
        if "LOW_FPS" in r["warnings"]:
            gate_note += " (WARN: LOW_FPS)"
        print(
            f"  {r['profile']:<33} | {r['res']:<14} | "
            f"{r['median_ms']:6.2f} ms | {r['sqi']:4.2f}  | "
            f"{r['hr_bpm']:5.2f} (±{r['hr_err_bpm']:4.2f}) | {gate_note}"
        )

    print("=" * 88)
    return 0


if __name__ == "__main__":
    sys.exit(main())
