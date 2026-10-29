"""
tests/test_week8_device_matrix_qa.py
====================================
Bộ kiểm thử đơn vị và tích hợp cho Tuần 8 (Khang):
1. Kiểm thử Ma trận Thiết bị (Device Matrix: HD, VGA, QVGA, 60FPS, VFR Jitter, Low-FPS).
2. Kiểm chứng sửa lỗi rPPG / ROI / SQI & đồng bộ đồng hồ logic QualityGate.
3. Kiểm chứng chốt phiên bản thuật toán (Frozen Algorithm Version Manifest).
"""
import numpy as np
import pytest

from aivitals_engine.rppg.chrom import CHROMMethod
from aivitals_engine.rppg.green import GREENMethod
from aivitals_engine.rppg.pos import POSMethod
from aivitals_engine.version import (
    FROZEN_ALGORITHM_VERSIONS,
    SIGNAL_PIPELINE_VERSION,
    SIGNAL_QA_STATUS,
    get_signal_version_manifest,
)
from scripts.benchmarks.bench_week8_device_matrix_qa import run_device_profile


@pytest.mark.parametrize(
    "label,width,height,fps,jitter",
    [
        ("HD_720p_30fps", 1280, 720, 30.0, 0.0),
        ("VGA_480p_30fps", 640, 480, 30.0, 0.0),
        ("QVGA_240p_24fps", 320, 240, 24.0, 0.0),
        ("HighFPS_60fps", 640, 480, 60.0, 0.0),
        ("VFR_Jitter_25fps", 640, 480, 25.0, 0.004),
    ],
)
def test_device_matrix_profiles_accuracy_and_latency(label, width, height, fps, jitter):
    """Mọi cấu hình camera đạt chuẩn trong Device Matrix (trên vid.avi) phải cho HR sai số < 3 BPM và SQI >= 0.4."""
    res = run_device_profile(label, width, height, fps, jitter_std_sec=jitter, duration_sec=10.0)
    assert res["status"] == "OK", f"Profile {label} không đạt trạng thái OK: {res}"
    assert res["sqi"] >= 0.40
    assert res["hr_err_bpm"] < 3.0
    assert res["median_ms"] < 33.3


def test_device_matrix_low_fps_triggers_warning():
    """Camera tụt xuống 15 FPS (< 20 FPS) phải phát cảnh báo LOW_FPS."""
    res = run_device_profile("LowFPS_15fps", 640, 480, 15.0, duration_sec=4.0)
    assert "LOW_FPS" in res["warnings"]


def test_frozen_algorithm_versions_and_manifest():
    """Kiểm chứng phiên bản các thuật toán rPPG đã được đóng băng và khớp với manifest."""
    manifest = get_signal_version_manifest()
    assert manifest["signal_pipeline_version"] == SIGNAL_PIPELINE_VERSION == "1.0.0"
    assert manifest["qa_status"] == SIGNAL_QA_STATUS == "SIGNED_OFF"
    assert manifest["default_method"] == "POS"
    assert manifest["algorithms"] == FROZEN_ALGORITHM_VERSIONS

    assert POSMethod().version == FROZEN_ALGORITHM_VERSIONS["POS"] == "1.0"
    assert CHROMMethod().version == FROZEN_ALGORITHM_VERSIONS["CHROM"] == "1.0"
    assert GREENMethod().version == FROZEN_ALGORITHM_VERSIONS["GREEN"] == "1.0"
    assert len(manifest["config_sha256_short"]) == 16
