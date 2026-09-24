"""
test_realtime_three_methods.py
==============================
W3-4 – Test end-to-end 3 methods (GREEN / CHROM / POS) qua RealtimeSignalPipeline.

DoD tuần 3: "BVP real-time + 3 methods"

Kiểm tra:
  1. Cả 3 method đều tạo ra bvp_signal hợp lệ khi buffer đủ dữ liệu.
  2. method_name và method_version phản ánh đúng method đang dùng.
  3. set_method() switch thuật toán và reset buffer đúng cách.
  4. BVPStreamPacket (batch pipeline) cũng mang method metadata.
"""

import unittest
import numpy as np
from scipy import signal as scipy_signal

from aivitals_engine.signal_pipeline_realtime import RealtimeSignalPipeline, FrameResult
from aivitals_engine.pipeline import SignalRPPGPipeline
from aivitals_engine.rppg.green import GREENMethod
from aivitals_engine.rppg.chrom import CHROMMethod
from aivitals_engine.rppg.pos import POSMethod


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

_FS       = 30.0
_WIN_SEC  = 3.0
_MIN_SEC  = 1.5
_N_READY  = 65   # số frame đủ để buffer sẵn sàng (> min_sec @ 30fps)
_N_BUFFER = 30   # số frame còn đang buffering


def _make_pulse_frame(t: float, height: int = 120, width: int = 120) -> np.ndarray:
    """
    Tạo frame BGR giả lập màu da với pulse signal 72 BPM (1.2 Hz).

    Để SimpleFaceDetector fallback hoạt động, frame phải có kích thước > 0.
    Pixel BGR được điều chế nhẹ theo sóng sin để ROIExtractor nhận được
    RGB biến thiên theo thời gian, giúp rPPG method tạo ra BVP có ý nghĩa.
    """
    heart_freq = 1.2          # 72 BPM
    pulse = np.sin(2 * np.pi * heart_freq * t)

    # Skin-tone base (BGR): B≈85, G≈110, R≈160 — điều chế ±2 mức pixel
    b = int(np.clip(85  + 0.3 * pulse * 4, 0, 255))
    g = int(np.clip(110 - 1.8 * pulse * 4, 0, 255))
    r = int(np.clip(160 - 0.6 * pulse * 4, 0, 255))

    frame = np.full((height, width, 3), [b, g, r], dtype=np.uint8)
    return frame


def _run_pipeline_until_ready(
    pipeline: RealtimeSignalPipeline,
    n_frames: int = _N_READY,
    fps: float = _FS,
) -> FrameResult:
    """Feed n_frames vào pipeline và trả về FrameResult cuối cùng."""
    result = None
    for i in range(n_frames):
        ts    = i / fps
        frame = _make_pulse_frame(ts)
        result = pipeline.process_frame(frame, timestamp=ts)
    return result


# ──────────────────────────────────────────────────────────────────────────────
# Test 1 — Cả 3 method tạo được BVP qua realtime pipeline
# ──────────────────────────────────────────────────────────────────────────────

class TestAllThreeMethodsProduceBVP(unittest.TestCase):
    """
    Mỗi method (GREEN / CHROM / POS) phải:
    - Tạo ra FrameResult.is_ready == True sau đủ frame.
    - FrameResult.bvp_signal không None, length > 0.
    - FrameResult.method_name khớp với method đã chọn.
    - FrameResult.method_version == "1.0".
    """

    def _assert_method_produces_bvp(self, method_name: str) -> None:
        pipeline = RealtimeSignalPipeline(
            method     = method_name,
            window_sec = _WIN_SEC,
            min_sec    = _MIN_SEC,
            target_fps = _FS,
        )
        result = _run_pipeline_until_ready(pipeline)

        # Pipeline phải sẵn sàng
        self.assertTrue(
            result.is_ready,
            f"[{method_name}] Pipeline chưa sẵn sàng sau {_N_READY} frames",
        )
        self.assertIn(
            result.status, ["OK", "LOW_QUALITY"],
            f"[{method_name}] status không hợp lệ: {result.status}",
        )

        # BVP signal phải tồn tại
        self.assertIsNotNone(
            result.bvp_signal,
            f"[{method_name}] bvp_signal là None",
        )
        self.assertGreater(
            len(result.bvp_signal), 0,
            f"[{method_name}] bvp_signal rỗng",
        )

        # SQI phải trong khoảng hợp lệ
        self.assertGreaterEqual(result.quality_sqi, 0.0)
        self.assertLessEqual(result.quality_sqi, 1.0)

        # fps phải hợp lý
        self.assertGreater(result.fps, 0.0)

    def test_green_produces_bvp(self):
        self._assert_method_produces_bvp("GREEN")

    def test_chrom_produces_bvp(self):
        self._assert_method_produces_bvp("CHROM")

    def test_pos_produces_bvp(self):
        self._assert_method_produces_bvp("POS")


# ──────────────────────────────────────────────────────────────────────────────
# Test 2 — method_name và method_version đúng trong mọi trạng thái
# ──────────────────────────────────────────────────────────────────────────────

class TestMethodMetadataInFrameResult(unittest.TestCase):
    """
    method_name và method_version phải chính xác ở mọi trạng thái pipeline:
    BUFFERING, FACE_LOST, và OK / LOW_QUALITY.
    """

    def _make_pipeline(self, method_name: str) -> RealtimeSignalPipeline:
        return RealtimeSignalPipeline(
            method     = method_name,
            window_sec = _WIN_SEC,
            min_sec    = _MIN_SEC,
            target_fps = _FS,
        )

    def test_method_name_during_buffering(self):
        """method_name phải đúng ngay cả khi đang BUFFERING."""
        for method_name in ["GREEN", "CHROM", "POS"]:
            pipeline = self._make_pipeline(method_name)
            # Feed ít frame — chưa đủ buffer
            result = _run_pipeline_until_ready(pipeline, n_frames=_N_BUFFER)
            self.assertEqual(
                result.method_name, method_name,
                f"[{method_name}] method_name sai khi BUFFERING: {result.method_name}",
            )

    def test_method_name_when_ready(self):
        """method_name phải đúng khi is_ready == True."""
        for method_name in ["GREEN", "CHROM", "POS"]:
            pipeline = self._make_pipeline(method_name)
            result = _run_pipeline_until_ready(pipeline)
            self.assertEqual(result.method_name, method_name)
            self.assertEqual(result.method_version, "1.0")

    def test_method_name_face_lost(self):
        """method_name phải đúng khi FACE_LOST (frame rỗng)."""
        for method_name in ["GREEN", "CHROM", "POS"]:
            pipeline = self._make_pipeline(method_name)
            result = pipeline.process_frame(np.zeros((0, 0, 3), dtype=np.uint8))
            self.assertEqual(result.status, "FACE_LOST")
            self.assertEqual(result.method_name, method_name)

    def test_current_method_property(self):
        """pipeline.current_method trả về đúng tên method."""
        for method_name in ["GREEN", "CHROM", "POS"]:
            pipeline = self._make_pipeline(method_name)
            self.assertEqual(pipeline.current_method, method_name)


# ──────────────────────────────────────────────────────────────────────────────
# Test 3 — set_method() switch thuật toán và reset buffer
# ──────────────────────────────────────────────────────────────────────────────

class TestSetMethodSwitching(unittest.TestCase):
    """
    set_method() phải:
    - Thay đổi thuật toán đang dùng.
    - Reset buffer (pipeline quay về BUFFERING).
    - method_name trong FrameResult phản ánh method mới.
    """

    def test_switch_pos_to_green(self):
        """Switch từ POS → GREEN: buffer reset, method_name đổi sang GREEN."""
        pipeline = RealtimeSignalPipeline(
            method     = "POS",
            window_sec = _WIN_SEC,
            min_sec    = _MIN_SEC,
            target_fps = _FS,
        )

        # Giai đoạn 1: POS, buffer đủ
        result_pos = _run_pipeline_until_ready(pipeline)
        self.assertTrue(result_pos.is_ready)
        self.assertEqual(result_pos.method_name, "POS")

        # Switch sang GREEN — buffer phải reset
        pipeline.set_method("GREEN")
        self.assertEqual(pipeline.current_method, "GREEN")
        self.assertFalse(pipeline.is_ready, "Buffer phải reset sau set_method()")

        # Giai đoạn 2: feed lại đủ frame, bây giờ phải là GREEN
        result_green = _run_pipeline_until_ready(pipeline)
        self.assertTrue(result_green.is_ready)
        self.assertEqual(result_green.method_name, "GREEN")

    def test_switch_with_instance(self):
        """set_method() nhận RPPGMethod instance trực tiếp."""
        pipeline = RealtimeSignalPipeline(
            method     = "POS",
            window_sec = _WIN_SEC,
            min_sec    = _MIN_SEC,
            target_fps = _FS,
        )

        chrom_instance = CHROMMethod(fps=_FS)
        pipeline.set_method(chrom_instance)
        self.assertEqual(pipeline.current_method, "CHROM")

    def test_invalid_method_raises(self):
        """Tên method không hợp lệ phải raise ValueError."""
        with self.assertRaises(ValueError):
            RealtimeSignalPipeline(method="INVALID_XYZ")

    def test_switch_to_all_methods_sequentially(self):
        """Switch lần lượt qua GREEN → CHROM → POS, mỗi lần phải đúng tên."""
        pipeline = RealtimeSignalPipeline(
            method     = "GREEN",
            window_sec = _WIN_SEC,
            min_sec    = _MIN_SEC,
            target_fps = _FS,
        )
        for expected in ["GREEN", "CHROM", "POS"]:
            pipeline.set_method(expected)
            self.assertEqual(pipeline.current_method, expected)


# ──────────────────────────────────────────────────────────────────────────────
# Test 4 — BVPStreamPacket mang đúng method metadata (batch pipeline)
# ──────────────────────────────────────────────────────────────────────────────

class TestBVPStreamPacketMethodMetadata(unittest.TestCase):
    """
    BVPStreamPacket bàn giao cho Khoa phải có method_name và method_version
    để traceable — dùng qua SignalRPPGPipeline (batch mode).
    """

    def setUp(self):
        """Tạo synthetic RGB data 8 giây @ 30 FPS để test batch pipeline."""
        duration  = 8.0
        N         = int(_FS * duration)
        t         = np.linspace(0, duration, N, endpoint=False)
        heart_freq = 1.2

        pulse = np.sin(2 * np.pi * heart_freq * t)
        r_sig = 160.0 - 0.6 * pulse + np.random.default_rng(42).normal(0, 0.05, N)
        g_sig = 110.0 - 1.8 * pulse + np.random.default_rng(43).normal(0, 0.05, N)
        b_sig = 85.0  - 0.3 * pulse + np.random.default_rng(44).normal(0, 0.05, N)
        self.rgb = np.column_stack([r_sig, g_sig, b_sig])

    def _assert_packet_has_method(self, method_name: str) -> None:
        pipeline   = SignalRPPGPipeline(fps=_FS)
        bvp_result = pipeline.run_on_rgb(self.rgb, fs=_FS, algorithm=method_name)
        packet     = bvp_result.to_stream_packet()

        self.assertEqual(
            packet.method_name, method_name,
            f"[{method_name}] packet.method_name sai: {packet.method_name}",
        )
        self.assertEqual(
            packet.method_version, "1.0",
            f"[{method_name}] packet.method_version sai: {packet.method_version}",
        )
        self.assertIn("method_name", packet.to_dict())
        self.assertIn("method_version", packet.to_dict())

    def test_green_packet_metadata(self):
        self._assert_packet_has_method("GREEN")

    def test_chrom_packet_metadata(self):
        self._assert_packet_has_method("CHROM")

    def test_pos_packet_metadata(self):
        self._assert_packet_has_method("POS")

    def test_packet_bvp_signal_not_empty(self):
        """BVP signal trong packet phải có độ dài > 0 cho cả 3 method."""
        pipeline = SignalRPPGPipeline(fps=_FS)
        for method_name in ["GREEN", "CHROM", "POS"]:
            bvp_result = pipeline.run_on_rgb(self.rgb, fs=_FS, algorithm=method_name)
            packet     = bvp_result.to_stream_packet()
            self.assertGreater(
                len(packet.bvp_signal), 0,
                f"[{method_name}] packet.bvp_signal rỗng",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
