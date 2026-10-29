import hashlib
import json
from typing import Any, Dict

from aivitals_engine.config.settings import SignalConfig

ENGINE_NAME = "aivitals_engine"
ENGINE_VERSION = "0.1.0"

# Week 8 — Frozen Signal Pipeline & rPPG Algorithm Release Manifest
SIGNAL_PIPELINE_VERSION = "1.0.0"
SIGNAL_QA_STATUS = "SIGNED_OFF"

FROZEN_ALGORITHM_VERSIONS: Dict[str, str] = {
    "POS": "1.0",
    "CHROM": "1.0",
    "GREEN": "1.0",
}


def get_signal_version_manifest() -> Dict[str, Any]:
    """
    Trả về manifest đóng băng phiên bản thuật toán và cấu hình chuẩn của Signal Engine (Tuần 8).
    Bao gồm mã băm SHA-256 của tham số chuẩn để truy vết (traceability).
    """
    cfg = SignalConfig()
    frozen_params = {
        "fps": cfg.fps,
        "window_sec": cfg.window_sec,
        "sub_window_sec": cfg.sub_window_sec,
        "min_window_sec": cfg.min_window_sec,
        "detrend_lambda": cfg.detrend_lambda,
        "low_cutoff_hz": cfg.low_cutoff_hz,
        "high_cutoff_hz": cfg.high_cutoff_hz,
        "filter_order": cfg.filter_order,
        "artifact_threshold": cfg.artifact_threshold,
        "time_gap_threshold_sec": cfg.time_gap_threshold_sec,
        "max_face_lost_sec": cfg.max_face_lost_sec,
    }
    payload = json.dumps(
        {"algorithms": FROZEN_ALGORITHM_VERSIONS, "config": frozen_params},
        sort_keys=True,
    ).encode("utf-8")
    checksum = hashlib.sha256(payload).hexdigest()[:16]

    return {
        "engine_name": ENGINE_NAME,
        "engine_version": ENGINE_VERSION,
        "signal_pipeline_version": SIGNAL_PIPELINE_VERSION,
        "qa_status": SIGNAL_QA_STATUS,
        "default_method": "POS",
        "algorithms": dict(FROZEN_ALGORITHM_VERSIONS),
        "frozen_config": frozen_params,
        "config_sha256_short": checksum,
    }
