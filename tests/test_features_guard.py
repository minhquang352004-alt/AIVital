"""Test cổng chất lượng trích xuất đặc trưng BVP (Week 7, Khang)."""
import numpy as np
import pytest

from aivitals_engine.features import BVPFeatureExtractor, BVPFeatures, FeatureGuardConfig
from aivitals_engine.features.guard import check_signal
from tests.test_signal_robustness import FPS, make_frame, new_pipeline, run

FS = 30.0


def clean_bvp(seconds=10.0, fs=FS, hr_hz=1.2):
    t = np.arange(int(seconds * fs)) / fs
    # xung có hài bậc 2 để tạo hình thái giống thật
    return np.sin(2 * np.pi * hr_hz * t) + 0.35 * np.sin(2 * np.pi * 2 * hr_hz * t + 0.6)


def test_clean_signal_passes_and_vector_is_complete():
    res = BVPFeatureExtractor().extract_checked(clean_bvp(), FS, sqi=0.8, warnings=[], artifact_ratio=0.0)
    assert res.valid and res.reasons == ()
    assert isinstance(res.features, BVPFeatures)
    vec = res.features.to_numpy()
    assert vec.shape == (len(BVPFeatures.feature_names()),)
    assert res.validity.metadata["sqi"] == 0.8
    assert res.validity.metadata["valid_beat_count"] >= 3


def test_extract_unchanged_still_returns_features_for_bad_signal():
    feats = BVPFeatureExtractor().extract(np.zeros(300), FS)
    assert isinstance(feats, BVPFeatures)    # hành vi cũ giữ nguyên


@pytest.mark.parametrize("bvp,fs,kwargs,reason", [
    (clean_bvp(2.0), FS, {}, "SIGNAL_TOO_SHORT"),
    (np.zeros(300), FS, {}, "SIGNAL_DEGENERATE"),
    (np.full(300, np.nan), FS, {}, "NON_FINITE_SAMPLES"),
    (clean_bvp(), 10.0, {}, "LOW_FS"),
    (clean_bvp(), FS, {"sqi": 0.2}, "LOW_SQI"),
    (clean_bvp(), FS, {"warnings": ["MOTION_HIGH"]}, "BLOCKING_WARNING"),
    (clean_bvp(), FS, {"artifact_ratio": 0.5}, "HIGH_ARTIFACT"),
    (np.array([]), FS, {}, "SIGNAL_DEGENERATE"),
])
def test_bad_signals_are_rejected_with_reason(bvp, fs, kwargs, reason):
    res = BVPFeatureExtractor().extract_checked(bvp, fs, **kwargs)
    assert not res.valid
    assert res.features is None
    assert reason in res.reasons


def test_non_blocking_warning_does_not_reject():
    res = BVPFeatureExtractor().extract_checked(clean_bvp(), FS, sqi=0.8, warnings=["TOO_DARK"])
    assert res.valid


def test_too_few_beats_rejected():
    # tín hiệu chỉ 0.3 Hz (18 BPM) trong 10s → ~3 nhịp nhưng yêu cầu 50 nhịp
    cfg = FeatureGuardConfig(min_valid_beats=50)
    res = BVPFeatureExtractor().extract_checked(clean_bvp(), FS, guard_config=cfg)
    assert not res.valid and res.reasons == ("TOO_FEW_BEATS",)
    assert "valid_beat_count" in res.validity.metadata


def test_metadata_is_copied_not_mutated():
    meta = {"method": "POS", "method_version": "1.0"}
    res = BVPFeatureExtractor().extract_checked(clean_bvp(), FS, metadata=meta)
    assert res.validity.metadata["method"] == "POS"
    assert "fs" not in meta


def test_check_signal_returns_unique_reasons():
    r = check_signal(np.zeros(10), 5.0, sqi=0.0)
    assert len(r) == len(set(r))


# ── Pipeline ────────────────────────────────────────────────────────────────

def test_pipeline_checked_none_before_ready():
    pipe, _ = new_pipeline()
    assert pipe.extract_features_checked() is None


def test_pipeline_checked_has_traceable_metadata_when_ready():
    rng = np.random.default_rng(2)
    pipe, _ = new_pipeline()
    run(pipe, 0.0, 10.0, rng=rng)
    res = pipe.extract_features_checked()
    assert res is not None
    meta = res.validity.metadata
    assert meta["method"] == "POS" and "method_version" in meta
    assert meta["fs"] > 0 and "sqi" in meta and "artifact_ratio" in meta


def test_pipeline_checked_rejects_during_motion():
    pipe, det = new_pipeline()
    _, t = run(pipe, 0.0, 8.0)
    x, y, w, h = det.bbox
    for i in range(60):
        det.bbox = (x + int(0.10 * w * np.sin(2 * np.pi * 1.5 * i / FPS)), y, w, h)
        pipe.process_frame(make_frame(t), timestamp=t)
        t += 1 / FPS
    res = pipe.extract_features_checked()
    if res is not None:      # buffer vẫn ready (không bị jump-reset)
        assert not res.valid and "BLOCKING_WARNING" in res.reasons
