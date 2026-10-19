"""
tests/test_engine_benchmark.py
==============================
Kiểm thử tự động cho Engine Benchmark Harness (scripts/benchmarks/bench_engine_performance.py).
Đảm bảo bộ đo kiểm chạy ổn định, không crash và sinh đúng báo cáo.
"""

import os
import unittest
import numpy as np

from scripts.benchmarks.bench_engine_performance import (
    EngineBenchmarker,
    generate_synthetic_stream,
)


class TestEngineBenchmarkHarness(unittest.TestCase):
    """Kiểm thử tính toàn vẹn và độ tin cậy của Benchmark Harness."""

    def setUp(self):
        self.benchmarker = EngineBenchmarker(video_path=None, max_sec=5.0)

    def test_synthetic_stream_generation(self):
        """Đảm bảo hàm sinh luồng synthetic tạo đúng số frame và kích thước."""
        frames = generate_synthetic_stream(duration_sec=2.0, fps=30.0, width=160, height=120)
        self.assertEqual(len(frames), 60)
        frame_0, ts_0 = frames[0]
        self.assertEqual(frame_0.shape, (120, 160, 3))
        self.assertEqual(ts_0, 0.0)

    def test_benchmark_methods_synthetic(self):
        """Đảm bảo đo kiểm 3 thuật toán rPPG chạy trơn tru trên dữ liệu giả lập."""
        res = self.benchmarker.benchmark_methods(["POS", "GREEN"])
        self.assertIn("POS", res)
        self.assertIn("GREEN", res)
        self.assertGreater(res["POS"]["throughput_fps"], 0.0)
        self.assertGreater(res["POS"]["latency_median_ms"], 0.0)
        self.assertIn("quality_gate", res["POS"])

    def test_benchmark_roi_modes(self):
        """Đảm bảo so sánh Single-ROI vs Multi-ROI tính toán đầy đủ chỉ số."""
        roi_res = self.benchmarker.benchmark_roi_modes()
        self.assertIn("single_roi_extract_ms", roi_res)
        self.assertIn("multi_roi_extract_ms", roi_res)
        self.assertIn("cross_roi_correlation_r", roi_res)
        self.assertGreaterEqual(roi_res["cross_roi_correlation_r"], -1.0)
        self.assertLessEqual(roi_res["cross_roi_correlation_r"], 1.0)

    def test_benchmark_failure_cases(self):
        """Đảm bảo ma trận 5 kịch bản lỗi biên đều được đánh giá an toàn."""
        fail_res = self.benchmarker.benchmark_failure_cases()
        self.assertTrue(fail_res["face_loss_recovered"])
        self.assertTrue(fail_res["low_light_stress_handled"])
        self.assertTrue(fail_res["over_exposure_artifact_detected"])
        self.assertTrue(fail_res["fps_jitter_resampled_ok"])

    def test_markdown_report_formatting(self):
        """Đảm bảo hàm sinh báo cáo Markdown tạo đúng các đề mục chuẩn."""
        mock_results = {
            "methods": {
                "POS": {
                    "throughput_fps": 75.0,
                    "latency_median_ms": 15.0,
                    "latency_p95_ms": 20.0,
                    "cpu_percent_avg": 25.0,
                    "memory_rss_mb": 500.0,
                    "mean_sqi": 0.55,
                    "quality_gate": {"ACCEPTED": 50},
                    "frames_ready": 60,
                }
            },
            "roi_analysis": {
                "single_roi_extract_ms": 0.1,
                "multi_roi_extract_ms": 0.12,
                "extract_overhead_ms": 0.02,
                "extract_overhead_pct": 20.0,
                "pipeline_single_latency_ms": 14.8,
                "pipeline_multi_latency_ms": 15.0,
                "pipeline_overhead_ms": 0.2,
                "single_roi_mean_sqi": 0.52,
                "multi_roi_mean_sqi": 0.55,
                "sqi_delta": 0.03,
                "cross_roi_correlation_r": 0.99,
            },
            "failure_cases": {
                "face_loss_recovered": True,
                "low_light_stress_handled": True,
                "over_exposure_artifact_detected": True,
                "motion_artifact_rejected": True,
                "fps_jitter_resampled_ok": True,
            },
        }
        report = self.benchmarker.generate_markdown_report(mock_results)
        self.assertIn("# Báo Cáo Đo Kiểm Hiệu Năng & Độ Bền rPPG Engine", report)
        self.assertIn("POS", report)
        self.assertIn("Multi-ROI", report)
        self.assertIn("Biên Bản Nghiệm Thu & Bàn Giao Kỹ Thuật", report)


if __name__ == "__main__":
    unittest.main()
