"""
tests/features/test_bvp_feature_extractor.py
============================================
Integration tests cho BVPFeatureExtractor Facade.

Kiểm tra:
  - Khởi tạo mặc định và custom extractors (DIP, OCP).
  - Trích xuất thành công trên tín hiệu tổng hợp.
  - Kích thước vector to_numpy() cố định và ổn định.
  - Không crash trên các edge case khắc nghiệt.
  - Latency budget: median < 3.0 ms trên CPU cho cửa sổ 8s @ 30 FPS (240 mẫu).
"""
import time

import numpy as np
import pytest

from aivitals_engine.features import (
    BVPFeatureExtractor,
    BVPFeatures,
    BVPFeaturesConfig,
)
from aivitals_engine.features._base_extractor import PartialFeatureExtractor
from aivitals_engine.features.segmentation import SingleBeat

FS = 30.0


def make_clean_bvp(freq_hz: float = 1.2, duration_s: float = 8.0, fs: float = FS) -> np.ndarray:
    t = np.linspace(0, duration_s, int(duration_s * fs), endpoint=False)
    sig = np.sin(2 * np.pi * freq_hz * t)
    # Thêm chút họa âm và độ lệch để các đặc trưng phong phú
    sig += 0.3 * np.sin(4 * np.pi * freq_hz * t)
    return sig.astype(np.float64)


# ── Integration Tests ─────────────────────────────────────────────────────────

class TestBVPFeatureExtractorIntegration:

    @pytest.fixture
    def extracted(self) -> BVPFeatures:
        bvp = make_clean_bvp()
        return BVPFeatureExtractor().extract(bvp, FS)

    def test_returns_bvp_features_instance(self, extracted):
        assert isinstance(extracted, BVPFeatures)

    def test_valid_beat_count_positive(self, extracted):
        assert extracted.valid_beat_count > 0

    def test_window_duration_correct(self, extracted):
        assert extracted.window_duration_s == pytest.approx(8.0, rel=0.05)

    def test_fs_stored_correctly(self, extracted):
        assert extracted.fs == pytest.approx(FS)

    def test_numpy_vector_shape(self, extracted):
        vec = extracted.to_numpy()
        assert vec.shape == (BVPFeatures.feature_dim(),)
        assert vec.dtype == np.float64

    def test_numpy_vector_dim_stable_across_different_signals(self):
        """Kích thước vector phải đồng nhất 100% dù tín hiệu thế nào."""
        ext = BVPFeatureExtractor()
        signals = [
            make_clean_bvp(freq_hz=1.0),
            make_clean_bvp(freq_hz=1.5),
            np.zeros(240),
            np.ones(100),
            np.array([1.0, 2.0, 3.0]),
        ]
        dims = {ext.extract(s, FS).to_numpy().shape[0] for s in signals}
        assert len(dims) == 1
        assert dims.pop() == BVPFeatures.feature_dim()

    def test_to_dict_has_all_expected_keys(self, extracted):
        d = extracted.to_dict()
        for name in BVPFeatures.feature_names():
            assert name in d, f"Thiếu key '{name}' trong to_dict()"

    def test_to_json_valid_json(self, extracted):
        import json
        parsed = json.loads(extracted.to_json())
        assert "_schema_version" in parsed
        assert parsed["valid_beat_count"] > 0


# ── Safety / Robustness Tests ──────────────────────────────────────────────────

class TestBVPFeatureExtractorSafety:

    def test_all_zeros_signal_no_crash(self):
        res = BVPFeatureExtractor().extract(np.zeros(240), FS)
        assert isinstance(res, BVPFeatures)
        assert res.valid_beat_count == 0

    def test_all_ones_signal_no_crash(self):
        res = BVPFeatureExtractor().extract(np.ones(240), FS)
        assert isinstance(res, BVPFeatures)
        assert res.valid_beat_count == 0

    def test_all_nan_signal_no_crash(self):
        res = BVPFeatureExtractor().extract(np.full(240, float("nan")), FS)
        assert isinstance(res, BVPFeatures)
        assert res.valid_beat_count == 0

    def test_empty_signal_no_crash(self):
        res = BVPFeatureExtractor().extract(np.array([]), FS)
        assert isinstance(res, BVPFeatures)
        assert res.valid_beat_count == 0

    def test_single_sample_no_crash(self):
        res = BVPFeatureExtractor().extract(np.array([1.0]), FS)
        assert isinstance(res, BVPFeatures)

    def test_very_short_signal_no_crash(self):
        res = BVPFeatureExtractor().extract(np.array([0.1, 0.5, 0.2]), FS)
        assert isinstance(res, BVPFeatures)

    def test_high_frequency_noise_no_crash(self):
        noise = np.random.default_rng(42).standard_normal(240)
        res = BVPFeatureExtractor().extract(noise, FS)
        assert isinstance(res, BVPFeatures)


# ── Extensibility / Dependency Injection Tests (SOLID OCP & DIP) ──────────────

class DummyCustomExtractor(PartialFeatureExtractor):
    """Custom extractor thử nghiệm để verify tính mở rộng (OCP)."""

    def extract(self, bvp: np.ndarray, fs: float, beats: list[SingleBeat]) -> dict:
        return {"mean_pulse_amplitude": 999.0}


class TestBVPFeatureExtractorExtensibility:

    def test_custom_extractors_injected_successfully(self):
        custom_ext = DummyCustomExtractor()
        facade = BVPFeatureExtractor(extractors=[custom_ext])
        result = facade.extract(make_clean_bvp(), FS)
        assert result.mean_pulse_amplitude == pytest.approx(999.0)

    def test_custom_config_respected(self):
        cfg = BVPFeaturesConfig(min_valid_beats=100)  # Cực cao → không đủ beat
        facade = BVPFeatureExtractor(config=cfg)
        result = facade.extract(make_clean_bvp(), FS)
        # Vì min_valid_beats=100, morphology không được tính → mean_rise_time_ms = NaN
        assert np.isnan(result.mean_rise_time_ms)


# ── Latency Budget Test ────────────────────────────────────────────────────────

class TestBVPFeatureExtractorLatency:

    def test_median_latency_under_3ms(self):
        """Thời gian trích xuất trung vị cho cửa sổ 8s phải < 3.0 ms trên CPU."""
        bvp = make_clean_bvp()
        ext = BVPFeatureExtractor()

        # Warm-up 5 lần
        for _ in range(5):
            ext.extract(bvp, FS)

        # Đo 50 lần
        times_ms: list[float] = []
        for _ in range(50):
            t0 = time.perf_counter()
            ext.extract(bvp, FS)
            times_ms.append((time.perf_counter() - t0) * 1_000.0)

        median_ms = float(np.median(times_ms))
        assert median_ms < 3.0, (
            f"Median latency {median_ms:.2f} ms vượt ngưỡng budget 3.0 ms"
        )
