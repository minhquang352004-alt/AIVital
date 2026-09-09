import os
from typing import Tuple, Optional
import cv2
import numpy as np
import pandas as pd

def _get_frame_roi(frame: np.ndarray) -> np.ndarray:
    """
    Trích xuất vùng ROI tối thiểu từ frame video.
    Ưu tiên tìm khuôn mặt qua CascadeClassifier nếu hỗ trợ; nếu không, lấy 45% trung tâm khuôn hình.
    """
    h, w = frame.shape[:2]
    
    if hasattr(cv2, "CascadeClassifier") and hasattr(cv2, "data") and hasattr(cv2.data, "haarcascades"):
        try:
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            detector = cv2.CascadeClassifier(cascade_path)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(50, 50))
            if len(faces) > 0:
                bx, by, bw, bh = max(faces, key=lambda b: b[2] * b[3])
                rx = max(0, int(bx + 0.25 * bw))
                ry = max(0, int(by + 0.15 * bh))
                rw = min(w - rx, int(0.50 * bw))
                rh = min(h - ry, int(0.50 * bh))
                return frame[ry:ry+rh, rx:rx+rw]
        except Exception:
            pass

    # Fallback trích xuất tối thiểu: 40% trung tâm khung hình
    y1 = int(0.30 * h)
    y2 = int(0.70 * h)
    x1 = int(0.30 * w)
    x2 = int(0.70 * w)
    return frame[y1:y2, x1:x2]

def load_rgb_from_csv(csv_path: str, default_fps: float = 30.0) -> Tuple[np.ndarray, float]:
    """
    Đọc tín hiệu RGB từ file CSV.
    Hỗ trợ header 'R', 'G', 'B' (kèm 'timestamp' nếu có) hoặc 3 cột số bất kỳ.
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Không tìm thấy file: {csv_path}")

    df = pd.read_csv(csv_path)
    cols_lower = [str(c).lower().strip() for c in df.columns]

    fs = default_fps
    ts_col = None
    for c, original in zip(cols_lower, df.columns):
        if c in ["time", "timestamp", "ts"]:
            ts_col = original
            break

    if ts_col is not None:
        ts = df[ts_col].to_numpy(dtype=np.float64)
        if len(ts) > 1:
            diffs = np.diff(ts)
            mean_diff = np.mean(diffs[diffs > 0])
            if mean_diff > 0:
                estimated_fs = 1.0 / mean_diff if mean_diff < 10.0 else 1000.0 / mean_diff
                if 5.0 <= estimated_fs <= 120.0:
                    fs = float(estimated_fs)

    r_col, g_col, b_col = None, None, None
    for c, original in zip(cols_lower, df.columns):
        if c in ["r", "red"]:
            r_col = original
        elif c in ["g", "green"]:
            g_col = original
        elif c in ["b", "blue"]:
            b_col = original

    if r_col and g_col and b_col:
        rgb = df[[r_col, g_col, b_col]].to_numpy(dtype=np.float64)
    else:
        numeric_df = df.select_dtypes(include=[np.number])
        if numeric_df.shape[1] >= 3:
            rgb = numeric_df.iloc[:, :3].to_numpy(dtype=np.float64)
        else:
            raise ValueError(f"File CSV {csv_path} không đủ 3 cột tín hiệu RGB.")

    return rgb, fs

def load_rgb_from_video(video_path: str) -> Tuple[np.ndarray, float]:
    """
    Đọc video và trích xuất vector RGB trung bình từng frame (extraction tối thiểu).
    Tự động chuyển đổi file AVI uncompressed sang MP4 nếu cần để tránh lỗi crash bộ nhớ của OpenCV.
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Không tìm thấy file video: {video_path}")

    actual_path = video_path
    if video_path.lower().endswith(".avi"):
        mp4_path = os.path.splitext(video_path)[0] + ".mp4"
        if os.path.exists(mp4_path):
            actual_path = mp4_path
        else:
            try:
                import subprocess
                print(f"Đang tự động tối ưu định dạng video AVI sang MP4 ({os.path.basename(mp4_path)})...")
                cmd = ["ffmpeg", "-y", "-i", video_path, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", mp4_path]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                if os.path.exists(mp4_path):
                    actual_path = mp4_path
            except Exception:
                actual_path = video_path

    cap = cv2.VideoCapture(actual_path)
    if not cap.isOpened():
        raise RuntimeError(f"Không thể mở video: {actual_path}")

    fs = cap.get(cv2.CAP_PROP_FPS)
    if fs <= 0 or np.isnan(fs):
        fs = 30.0

    rgb_list = []

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        roi = _get_frame_roi(frame)
        if roi.size > 0:
            mean_bgr = np.mean(roi, axis=(0, 1))
            mean_rgb = [mean_bgr[2], mean_bgr[1], mean_bgr[0]]  # BGR sang RGB
            rgb_list.append(mean_rgb)

    cap.release()

    if not rgb_list:
        raise RuntimeError(f"Không trích xuất được frame nào từ video {video_path}")

    return np.asarray(rgb_list, dtype=np.float64), float(fs)

def load_sample(source_path: str, default_fps: float = 30.0) -> Tuple[np.ndarray, float]:
    """
    Tự động nhận diện định dạng input (video hay CSV) và trích xuất mảng RGB + sampling rate (fs).
    """
    ext = os.path.splitext(source_path)[1].lower()
    if ext in [".csv", ".txt"]:
        return load_rgb_from_csv(source_path, default_fps=default_fps)
    elif ext in [".mp4", ".avi", ".mov", ".mkv"]:
        return load_rgb_from_video(source_path)
    else:
        raise ValueError(f"Định dạng file không được hỗ trợ: {ext}. Vui lòng dùng .csv hoặc .mp4/.avi.")
