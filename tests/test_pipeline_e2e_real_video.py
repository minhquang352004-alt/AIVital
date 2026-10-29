"""
tests/test_pipeline_e2e_real_video.py
======================================
Kiểm thử tích hợp End-to-End (E2E) trên video người thật (vid.avi)
với Google MediaPipe Face Mesh và toàn bộ RealtimeSignalPipeline (Week 8, Khang).

Chuỗi luồng kiểm tra:
  Video người thật (vid.avi)
    -> MediaPipeFaceDetector (478 landmarks 3D)
    -> Multi-ROI da mặt đa giác (PolygonROI + SkinFilter)
    -> SlidingWindowBuffer (chuẩn hóa FPS & tự thích nghi nhiễu)
    -> Thuật toán rPPG cốt lõi (POS Method)
    -> Đánh giá chất lượng tín hiệu (QualityGate & SQI)
    -> Cổng trích xuất đặc trưng sinh lý có bảo vệ (BVPFeatureGuard -> 23 đặc trưng)
"""

import os
import sys
import unittest
import cv2
import numpy as np

# Đảm bảo import được aivitals_engine dù chạy pytest từ thư mục nào
sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from aivitals_engine.face.detector import MediaPipeFaceDetector
from aivitals_engine.features import BVPFeatures
from aivitals_engine.signal_pipeline_realtime import RealtimeSignalPipeline


def _find_sample_video() -> str | None:
    """Tìm đường dẫn video vid.avi linh hoạt dù chạy pytest từ thư mục nào."""
    candidates = [
        os.path.join("aivitals_engine", "samples", "vid.avi"),
        os.path.join("AIVital", "aivitals_engine", "samples", "vid.avi"),
        os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "aivitals_engine", "samples", "vid.avi")
        ),
        os.path.abspath(
            os.path.join(os.path.dirname(__file__), "aivitals_engine", "samples", "vid.avi")
        ),
    ]
    for path in candidates:
        if os.path.exists(path):
            return os.path.abspath(path)
    return None


class TestPipelineE2ERealVideo(unittest.TestCase):
    """Bộ kiểm thử End-to-End toàn bộ luồng tín hiệu trên video người thật."""

    @classmethod
    def setUpClass(cls):
        cls.video_path = _find_sample_video()
        if cls.video_path is None:
            raise unittest.SkipTest("Tệp video vid.avi không tồn tại, bỏ qua kiểm thử E2E.")

    def test_01_mediapipe_detects_real_face_and_landmarks(self):
        """Kiểm chứng MediaPipe nhận diện chính xác mặt thật và trích xuất 468-478 điểm mốc."""
        cap = cv2.VideoCapture(self.video_path)
        ret, frame = cap.read()
        cap.release()

        self.assertTrue(ret, "Không thể đọc frame đầu tiên từ vid.avi")
        self.assertIsNotNone(frame)
        self.assertEqual(len(frame.shape), 3)

        detector = MediaPipeFaceDetector()
        bbox = detector.detect(frame)

        self.assertIsNotNone(bbox, "MediaPipe phải nhận diện được khuôn mặt trên vid.avi")
        x, y, w, h = bbox
        self.assertGreater(w, 50, "Độ rộng khuôn mặt nhận diện được phải > 50px")
        self.assertGreater(h, 50, "Độ cao khuôn mặt nhận diện được phải > 50px")

        landmarks = detector.get_landmarks()
        self.assertIsNotNone(landmarks, "MediaPipe phải trích xuất được danh sách điểm mốc landmarks")
        self.assertIn(landmarks.shape[0], [468, 478], "Số lượng điểm mốc Face Mesh phải là 468 hoặc 478 điểm")
        self.assertEqual(landmarks.shape[1], 2, "Tọa độ điểm mốc phải là cặp (x, y)")

    def test_02_e2e_realtime_pipeline_on_real_video(self):
        """
        Kiểm chứng toàn bộ pipeline E2E trên video người thật qua 1 chu kỳ hoàn chỉnh:
        Buffering -> Tự thích nghi cử động -> Ready -> Vượt cổng Feature Guard -> Trích xuất 23 đặc trưng.
        """
        cap = cv2.VideoCapture(self.video_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

        pipeline = RealtimeSignalPipeline(method="POS")
        ready_result = None
        valid_guarded = None
        ready_frame_idx = None
        guard_pass_frame_idx = None

        # Nạp tối đa 320 frames (~11s).
        # Thực tế trên vid.avi:
        # - Frames 0-120: Đối tượng cử động nhẹ, cơ chế bảo vệ của Khang kích hoạt (MOTION_HIGH/bbox_jump).
        # - Frame 213: Sau khi ngồi yên đủ 3s, buffer đạt ngưỡng và pipeline chuyển sang is_ready=True.
        # - Frame 274+: Dữ liệu sóng BVP đạt chuẩn y tế (SQI >= 0.40), Feature Guard kích hoạt PASS.
        for i in range(320):
            ret, frame = cap.read()
            if not ret:
                break
            res = pipeline.process_frame(frame, timestamp=i / fps)

            # Kiểm tra trạng thái frame đầu tiên
            if i == 0:
                self.assertFalse(res.is_ready)
                self.assertEqual(res.status, "BUFFERING")
                self.assertIsNone(res.bvp_signal)

            # Ghi nhận mốc ready đầu tiên
            if res.is_ready:
                if ready_result is None:
                    ready_result = res
                    ready_frame_idx = i

                # Kiểm tra cổng trích xuất đặc trưng có bảo vệ
                guarded = pipeline.extract_features_checked()
                if guarded is not None and guarded.valid:
                    valid_guarded = guarded
                    guard_pass_frame_idx = i
                    break  # Đạt kết quả E2E trọn vẹn, dừng sớm để tối ưu tốc độ test

        cap.release()

        # 1. Kiểm tra tính sẵn sàng của Pipeline (Ready)
        self.assertIsNotNone(ready_result, "Pipeline phải chuyển sang is_ready=True khi đối tượng ổn định")
        self.assertLessEqual(ready_frame_idx, 230, "Pipeline phải sẵn sàng trước frame 230")
        self.assertIn(ready_result.status, ["OK", "LOW_QUALITY"])
        self.assertIsNotNone(ready_result.bvp_signal)
        self.assertGreater(len(ready_result.bvp_signal), 0)
        self.assertGreaterEqual(ready_result.quality_sqi, 0.0)
        self.assertEqual(ready_result.method_name, "POS")
        self.assertEqual(ready_result.method_version, "1.0")

        # 2. Kiểm tra Cổng Feature Guard vượt qua kiểm định trên video thật
        self.assertIsNotNone(valid_guarded, "Feature Guard phải chấp nhận (valid=True) khi tín hiệu đạt chuẩn")
        self.assertTrue(valid_guarded.valid)
        self.assertEqual(valid_guarded.reasons, ())
        self.assertLessEqual(guard_pass_frame_idx, 300, "Cổng Feature Guard phải đạt chuẩn trước frame 300")

        # 3. Kiểm tra metadata truy vết
        meta = valid_guarded.validity.metadata
        self.assertEqual(meta["method"], "POS")
        self.assertIn("fs", meta)
        self.assertIn("sqi", meta)
        self.assertGreaterEqual(meta["sqi"], 0.40, "SQI của cửa sổ đạt chuẩn phải >= 0.40")

        # 4. Kiểm tra trích xuất hoàn chỉnh vector 23 đặc trưng sinh lý học
        self.assertIsNotNone(valid_guarded.features, "Bộ trích xuất phải sinh ra đối tượng BVPFeatures")
        vec = valid_guarded.features.to_numpy()
        self.assertEqual(vec.shape, (23,), "Vector đặc trưng sinh lý phải có đúng 23 chiều")
        self.assertEqual(len(BVPFeatures.feature_names()), 23)

        # Đảm bảo phần lớn đặc trưng được tính toán thành công (không bị toàn bộ NaN)
        valid_features_count = np.count_nonzero(~np.isnan(vec))
        self.assertGreaterEqual(
            valid_features_count, 18,
            f"Phải tính toán thành công ít nhất 18/23 đặc trưng sinh lý trên video thật (thực tế: {valid_features_count}/23)"
        )


if __name__ == "__main__":
    unittest.main()
