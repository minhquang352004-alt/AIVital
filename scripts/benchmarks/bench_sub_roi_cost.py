"""
scripts/benchmarks/bench_sub_roi_cost.py
=========================================
BUOC 2 - Đo chi phí thêm mỗi frame của extract_sub_roi_rgbs() và buffer push
trực tiếp trên khung hình thực tế từ video chuẩn (aivitals_engine/samples/vid.avi).

Chạy từ thư mục gốc AIVital/:
    python scripts/benchmarks/bench_sub_roi_cost.py
"""
import os
import sys
import time
import cv2
import numpy as np

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from aivitals_engine.roi.extractor import ROIExtractor
from aivitals_engine.signal.sliding_buffer import SlidingWindowBuffer
from aivitals_engine.signal_pipeline_realtime import RealtimeSignalPipeline

VIDEO_PATH = os.path.join(PROJECT_ROOT, "aivitals_engine", "samples", "vid.avi")
N = 500

# Đọc khung hình thực tế từ vid.avi và phát hiện khuôn mặt thực tế
cap = cv2.VideoCapture(VIDEO_PATH)
cap.set(cv2.CAP_PROP_POS_FRAMES, 150)
ret, frame = cap.read()
cap.release()
if not ret or frame is None:
    raise RuntimeError(f"Không đọc được khung hình từ {VIDEO_PATH}")

probe_pipe = RealtimeSignalPipeline(method="POS")
bbox = probe_pipe._face_detector.detect(frame) or (180, 100, 260, 280)
landmarks = probe_pipe._face_detector.get_landmarks()

extractor = ROIExtractor()
base_rgb = extractor.extract_mean_rgb(frame, bbox, landmarks=landmarks)


# --- 1. Cost of extract_mean_rgb vs extract_sub_roi_rgbs on vid.avi ---
def fn_mean():
    extractor.extract_mean_rgb(frame, bbox, landmarks=landmarks)


def fn_sub():
    extractor.extract_sub_roi_rgbs(frame, bbox, landmarks=landmarks)


def measure(fn):
    times = []
    for _ in range(N):
        t0 = time.perf_counter()
        fn()
        times.append((time.perf_counter() - t0) * 1e3)
    arr = np.array(times)
    return float(np.median(arr)), float(np.percentile(arr, 95))


med_mean, p95_mean = measure(fn_mean)
med_sub, p95_sub = measure(fn_sub)
extra = med_sub - med_mean

# --- 2. Cost of buffer push with vs without sub_rgbs ---
sub_val = extractor.extract_sub_roi_rgbs(frame, bbox, landmarks=landmarks)
buf = SlidingWindowBuffer(window_sec=8.0, min_sec=1.0, target_fps=30.0, artifact_threshold=None)


def fn_push_no_sub():
    buf._rgb_buffer.append(base_rgb)
    buf._timestamps.append(time.perf_counter())


def fn_push_with_sub():
    buf._rgb_buffer.append(base_rgb)
    buf._timestamps.append(time.perf_counter())
    buf._forehead_buf.append(sub_val.forehead)
    buf._left_cheek_buf.append(sub_val.left_cheek)
    buf._right_cheek_buf.append(sub_val.right_cheek)


med_push_no, p95_push_no = measure(fn_push_no_sub)
med_push_with, p95_push_with = measure(fn_push_with_sub)

h, w = frame.shape[:2]
print("=" * 68)
print("BUOC 2 - CHI PHI THEM CUA EXTRACT_SUB_ROI_RGBS() TREN vid.avi")
print(f"Video: vid.avi | N={N} | Frame={w}x{h} BGR | BBox={bbox}")
print("=" * 68)
print(f"\n{'Phep do':<45} {'Median(ms)':>10} {'p95(ms)':>9}")
print("-" * 68)
print(f"{'extract_mean_rgb() [Single-ROI]':<45} {med_mean:>10.3f} {p95_mean:>9.3f}")
print(f"{'extract_sub_roi_rgbs() [Multi-ROI]':<45} {med_sub:>10.3f} {p95_sub:>9.3f}")
print(f"{'Chi phi them (sub - mean)':<45} {extra:>10.3f} {p95_sub-p95_mean:>9.3f}")
print()
print(f"{'push() khong sub_rgbs':<45} {med_push_no:>10.3f} {p95_push_no:>9.3f}")
print(f"{'push() co sub_rgbs':<45} {med_push_with:>10.3f} {p95_push_with:>9.3f}")
print(f"{'Chi phi them push':<45} {med_push_with-med_push_no:>10.3f} {p95_push_with-p95_push_no:>9.3f}")
print(f"\nTong chi phi them moi frame (extractor + push): ~{extra + (med_push_with-med_push_no):.3f} ms")
print("Ngan sach 30 FPS: 33.33 ms / frame")
