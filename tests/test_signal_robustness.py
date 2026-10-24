"""
Bộ test robustness tín hiệu (Week 7, Khang).

Dùng detector giả lập (bbox điều khiển được) và video tổng hợp có xung mạch 1.2 Hz (72 BPM)
để kiểm tra: ánh sáng, chuyển động, FPS/timestamp, mất mặt và frame đầu vào bất thường.
"""
import numpy as np
import pytest

from aivitals_engine.face.detector import BaseFaceDetector
from aivitals_engine.quality.signal_warnings import (
    MESSAGE_VI,
    SEVERITY,
    SignalWarning,
    WarningSeverity,
    has_blocking,
    severity_of,
)
from aivitals_engine.signal_pipeline_realtime import RealtimeSignalPipeline

H, W = 480, 640
FPS = 30.0
HR_HZ = 1.2          # 72 BPM
FACE_BOX = (220, 140, 200, 200)
BASE_RGB = np.array([190.0, 140.0, 120.0])


class ScriptedDetector(BaseFaceDetector):
    """Detector giả lập: trả bbox do test đặt (None = mất mặt)."""

    def __init__(self, bbox=FACE_BOX):
        self.bbox = bbox

    def detect(self, frame):
        return self.bbox

    def reset(self):
        pass

    def get_landmarks(self):
        return None


def make_frame(t, gain=1.0, base=BASE_RGB, amp=0.012, rng=None):
    """Frame BGR với màu da dao động theo mạch (kênh G mạnh nhất)."""
    pulse = np.sin(2 * np.pi * HR_HZ * t)
    rgb = base * gain * (1.0 + amp * pulse * np.array([0.3, 1.0, 0.5]))
    if rng is not None:
        rgb = rgb + rng.normal(0, 0.15, 3)
    frame = np.empty((H, W, 3), dtype=np.uint8)
    frame[:] = np.clip(rgb[::-1], 0, 255).astype(np.uint8)  # RGB → BGR
    return frame


def estimate_hr_bpm(bvp, fps):
    n = 8192
    spec = np.abs(np.fft.rfft(bvp - np.mean(bvp), n=n))
    freqs = np.fft.rfftfreq(n, d=1.0 / fps)
    band = (freqs >= 0.7) & (freqs <= 3.0)
    return float(freqs[band][np.argmax(spec[band])] * 60.0)


def new_pipeline(bbox=FACE_BOX, **kw):
    kw.setdefault("window_sec", 6.0)
    kw.setdefault("min_sec", 4.0)
    kw.setdefault("target_fps", FPS)
    det = ScriptedDetector(bbox)
    return RealtimeSignalPipeline(face_detector=det, **kw), det


def run(pipe, t0, seconds, fps=FPS, gain=1.0, rng=None):
    res = None
    n = int(seconds * fps)
    for i in range(n):
        t = t0 + i / fps
        res = pipe.process_frame(make_frame(t, gain=gain, rng=rng), timestamp=t)
    return res, t0 + n / fps


# ── Enum / danh mục cảnh báo ────────────────────────────────────────────────

def test_enum_is_string_comparable():
    assert SignalWarning.TOO_DARK == "TOO_DARK"
    assert "MOTION_HIGH" in [SignalWarning.MOTION_HIGH]


def test_every_code_has_severity_and_message():
    for code in SignalWarning:
        assert code in SEVERITY
        assert MESSAGE_VI[code]


def test_severity_of_unknown_is_info():
    assert severity_of("HIGH_MOTION") is WarningSeverity.INFO
    assert severity_of(SignalWarning.MOTION_HIGH) is WarningSeverity.BLOCK


def test_has_blocking():
    assert has_blocking(["TOO_DARK", "MOTION_HIGH"])
    assert not has_blocking(["TOO_DARK"])
    assert not has_blocking(None)


# ── Frame đầu vào bất thường ────────────────────────────────────────────────

@pytest.mark.parametrize("bad", [None, [1, 2, 3], np.zeros((0, 0, 3), np.uint8),
                                 np.zeros((10, 10, 2), np.uint8), np.zeros((10,), np.uint8)])
def test_unusable_frames_become_face_lost(bad):
    pipe, _ = new_pipeline()
    res = pipe.process_frame(bad, timestamp=0.0)
    assert res.status == "FACE_LOST"
    assert SignalWarning.FACE_NOT_FOUND.value in res.warnings


def test_grayscale_bgra_and_float_frames_are_accepted():
    pipe, _ = new_pipeline()
    base = make_frame(0.0)
    gray = base[:, :, 0]
    bgra = np.dstack([base, np.full((H, W), 255, np.uint8)])
    flt = base.astype(np.float64) * 1.0
    for i, f in enumerate([gray, bgra, flt]):
        res = pipe.process_frame(f, timestamp=i / FPS)
        assert res.status != "FACE_LOST"


def test_nan_float_frame_does_not_crash():
    pipe, _ = new_pipeline()
    f = make_frame(0.0).astype(np.float64)
    f[0, 0, 0] = np.nan
    res = pipe.process_frame(f, timestamp=0.0)
    assert res.status != "FACE_LOST"


# ── Ánh sáng ────────────────────────────────────────────────────────────────

def test_steady_light_has_no_light_warning():
    pipe, _ = new_pipeline()
    res, _t = run(pipe, 0.0, 5.0)
    assert SignalWarning.LIGHT_UNSTABLE.value not in res.warnings
    assert SignalWarning.TOO_DARK.value not in res.warnings
    assert SignalWarning.TOO_BRIGHT.value not in res.warnings


def test_single_bright_outlier_does_not_flip_too_bright():
    pipe, _ = new_pipeline()
    _, t = run(pipe, 0.0, 2.0)
    res = pipe.process_frame(make_frame(t, gain=1.7), timestamp=t)   # 1 frame chói
    assert SignalWarning.TOO_BRIGHT.value not in res.warnings


def test_sustained_dark_and_bright_warnings():
    pipe, _ = new_pipeline()
    res, _ = run(pipe, 0.0, 1.0, gain=0.15)
    assert SignalWarning.TOO_DARK.value in res.warnings
    pipe2, _ = new_pipeline()
    res2, _ = run(pipe2, 0.0, 1.0, gain=1.6)
    assert SignalWarning.TOO_BRIGHT.value in res2.warnings


def test_flicker_triggers_light_unstable():
    pipe, _ = new_pipeline()
    res = None
    for i in range(90):
        t = i / FPS
        res = pipe.process_frame(make_frame(t, gain=0.6 if i % 2 else 1.0), timestamp=t)
    assert SignalWarning.LIGHT_UNSTABLE.value in res.warnings


def test_light_step_recovers_and_hr_stays_accurate():
    rng = np.random.default_rng(7)
    pipe, _ = new_pipeline()
    _, t = run(pipe, 0.0, 8.0, rng=rng)
    adapt0 = pipe._buffer.adapt_count
    res, t = run(pipe, t, 18.0, gain=1.25, rng=rng)       # bật đèn: sáng hơn 25%
    assert pipe._buffer.adapt_count > adapt0, "buffer phải tự thích nghi bước nhảy ánh sáng"
    assert res.is_ready
    assert abs(estimate_hr_bpm(res.bvp_signal, res.fps) - 72.0) < 3.0


def test_quality_cache_cleared_when_buffer_adapts():
    rng = np.random.default_rng(3)
    pipe, _ = new_pipeline()
    _, t = run(pipe, 0.0, 8.0, rng=rng)
    assert pipe._cached_metrics, "cần có cache SQI trước khi đổi sáng"
    adapt0 = pipe._buffer.adapt_count
    for _ in range(200):
        pipe.process_frame(make_frame(t, gain=1.3), timestamp=t)
        t += 1 / FPS
        if pipe._buffer.adapt_count > adapt0:
            break
    assert pipe._buffer.adapt_count > adapt0
    assert pipe._cached_metrics == {}


# ── Chuyển động ─────────────────────────────────────────────────────────────

def test_static_face_has_no_motion_warning():
    pipe, _ = new_pipeline()
    res, _ = run(pipe, 0.0, 6.0)
    assert SignalWarning.MOTION_HIGH.value not in res.warnings


def test_head_shaking_triggers_motion_high_and_low_quality():
    pipe, det = new_pipeline()
    res, t = run(pipe, 0.0, 8.0)
    assert res.is_ready
    x, y, w, h = FACE_BOX
    flagged = False
    for i in range(60):
        det.bbox = (x + int(0.10 * w * np.sin(2 * np.pi * 1.5 * i / FPS)), y, w, h)
        res = pipe.process_frame(make_frame(t), timestamp=t)
        t += 1 / FPS
        if SignalWarning.MOTION_HIGH.value in res.warnings:
            flagged = True
    assert flagged
    if res.is_ready:
        assert res.status == "LOW_QUALITY"


def test_small_jitter_is_not_motion():
    pipe, det = new_pipeline()
    _, t = run(pipe, 0.0, 6.0)
    x, y, w, h = FACE_BOX
    rng = np.random.default_rng(1)
    res = None
    for _ in range(60):
        det.bbox = (x + int(rng.integers(-2, 3)), y + int(rng.integers(-2, 3)), w, h)
        res = pipe.process_frame(make_frame(t), timestamp=t)
        t += 1 / FPS
    assert SignalWarning.MOTION_HIGH.value not in res.warnings


def test_bbox_jump_resets_window():
    pipe, det = new_pipeline()
    res, t = run(pipe, 0.0, 8.0)
    assert res.is_ready
    det.bbox = (FACE_BOX[0] + 250, FACE_BOX[1], FACE_BOX[2], FACE_BOX[3])
    res = pipe.process_frame(make_frame(t), timestamp=t)
    assert SignalWarning.MOTION_HIGH.value in res.warnings
    assert not res.is_ready
    assert pipe.buffer_size <= 1


# ── FPS / timestamp ─────────────────────────────────────────────────────────

def test_low_fps_warning():
    pipe, _ = new_pipeline()
    res, _ = run(pipe, 0.0, 3.0, fps=10.0)
    assert SignalWarning.LOW_FPS.value in res.warnings


def test_normal_fps_no_low_fps_warning():
    pipe, _ = new_pipeline()
    res, _ = run(pipe, 0.0, 3.0, fps=30.0)
    assert SignalWarning.LOW_FPS.value not in res.warnings


def test_timestamp_jitter_is_tolerated():
    rng = np.random.default_rng(5)
    pipe, _ = new_pipeline()
    res = None
    saw_gap = False
    for i in range(30 * 8):
        t = i / FPS + rng.uniform(-0.005, 0.005)
        res = pipe.process_frame(make_frame(t), timestamp=t)
        saw_gap |= SignalWarning.TIME_GAP.value in res.warnings
    assert not saw_gap
    assert res.is_ready


def test_long_timestamp_gap_resets_with_warning():
    pipe, _ = new_pipeline()
    res, t = run(pipe, 0.0, 6.0)
    assert res.is_ready
    t += 2.0                      # đứt luồng 2s (> ngưỡng)
    res = pipe.process_frame(make_frame(t), timestamp=t)
    assert SignalWarning.TIME_GAP.value in res.warnings
    assert not res.is_ready
    assert pipe._cached_metrics == {}


def test_duplicate_and_backward_timestamps_do_not_crash():
    pipe, _ = new_pipeline()
    _, t = run(pipe, 0.0, 2.0)
    for ts in (t, t, t - 0.5, t + 0.01):
        pipe.process_frame(make_frame(max(ts, 0.0)), timestamp=ts)


# ── Mất mặt ────────────────────────────────────────────────────────────────

def test_short_face_loss_keeps_buffer_and_hr_accurate():
    rng = np.random.default_rng(11)
    pipe, det = new_pipeline()
    _, t = run(pipe, 0.0, 8.0, rng=rng)
    det.bbox = None
    for _ in range(int(0.4 * FPS)):
        res = pipe.process_frame(make_frame(t), timestamp=t)
        assert res.status == "FACE_LOST"
        t += 1 / FPS
    det.bbox = FACE_BOX
    res, t = run(pipe, t, 8.0, rng=rng)
    assert res.is_ready
    assert abs(estimate_hr_bpm(res.bvp_signal, res.fps) - 72.0) < 3.0


def test_long_face_loss_resets_everything():
    pipe, det = new_pipeline()
    res, t = run(pipe, 0.0, 8.0)
    assert res.is_ready and pipe._cached_metrics
    det.bbox = None
    pipe.process_frame(make_frame(t), timestamp=t)
    res = pipe.process_frame(make_frame(t + 1.5), timestamp=t + 1.5)
    assert res.status == "FACE_LOST"
    assert pipe.buffer_size == 0
    assert pipe._cached_metrics == {}
    assert len(pipe._motion_history) == 0


def test_reset_clears_environment_state():
    pipe, _ = new_pipeline()
    run(pipe, 0.0, 3.0)
    pipe.reset()
    assert len(pipe._luma_history) == 0
    assert len(pipe._luma_recent) == 0
    assert len(pipe._motion_history) == 0
