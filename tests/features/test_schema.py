"""
tests/features/test_schema.py
==============================
Unit tests cho BVPFeatures schema — Data contract.

Kiểm tra:
  - to_numpy() kích thước cố định, dtype float64, loại metadata.
  - to_dict() chứa đầy đủ field.
  - to_json() hợp lệ JSON, NaN → null, có _schema_version.
  - frozen dataclass → không thể mutate.
  - feature_names() / feature_dim() nhất quán.
"""
import json

import numpy as np
import pytest

from aivitals_engine.features.schema import BVPFeatures


class TestBVPFeaturesSchemaContract:
    """Contract cơ bản — không được phá vỡ sau khi handoff Khoa."""

    def test_feature_names_non_empty(self):
        assert len(BVPFeatures.feature_names()) > 0

    def test_feature_dim_matches_names_count(self):
        assert BVPFeatures.feature_dim() == len(BVPFeatures.feature_names())

    def test_feature_dim_stable_across_calls(self):
        assert BVPFeatures.feature_dim() == BVPFeatures.feature_dim()

    def test_feature_names_order_deterministic(self):
        names1 = BVPFeatures.feature_names()
        names2 = BVPFeatures.feature_names()
        assert names1 == names2

    def test_metadata_fields_excluded_from_names(self):
        names = BVPFeatures.feature_names()
        assert "valid_beat_count" not in names
        assert "window_duration_s" not in names
        assert "fs" not in names


class TestBVPFeaturesToNumpy:

    def test_shape_matches_feature_dim(self):
        feat = BVPFeatures()
        vec = feat.to_numpy()
        assert vec.shape == (BVPFeatures.feature_dim(),)

    def test_dtype_is_float64(self):
        assert BVPFeatures().to_numpy().dtype == np.float64

    def test_metadata_not_in_vector(self):
        """valid_beat_count=99 không được xuất hiện trong vector."""
        feat = BVPFeatures(valid_beat_count=99, window_duration_s=8.0, fs=30.0)
        vec = feat.to_numpy()
        assert 99.0 not in vec

    def test_known_value_appears_in_vector(self):
        feat = BVPFeatures(mean_rise_time_ms=123.456)
        vec = feat.to_numpy()
        idx = BVPFeatures.feature_names().index("mean_rise_time_ms")
        assert vec[idx] == pytest.approx(123.456)

    def test_default_features_all_nan(self):
        feat = BVPFeatures()
        vec = feat.to_numpy()
        # Tất cả feature mặc định là NaN (trừ metadata đã bị loại)
        assert np.all(np.isnan(vec))

    def test_multiple_calls_consistent(self):
        feat = BVPFeatures(fundamental_freq_hz=1.2)
        vec1 = feat.to_numpy()
        vec2 = feat.to_numpy()
        np.testing.assert_array_equal(vec1, vec2)


class TestBVPFeaturesToDict:

    def test_returns_dict(self):
        assert isinstance(BVPFeatures().to_dict(), dict)

    def test_contains_all_feature_names(self):
        d = BVPFeatures().to_dict()
        for name in BVPFeatures.feature_names():
            assert name in d, f"Missing key: {name}"

    def test_contains_metadata_fields(self):
        d = BVPFeatures().to_dict()
        assert "valid_beat_count" in d
        assert "window_duration_s" in d
        assert "fs" in d

    def test_known_value_preserved(self):
        feat = BVPFeatures(mean_rise_time_ms=150.0, fundamental_freq_hz=1.2)
        d = feat.to_dict()
        assert d["mean_rise_time_ms"] == pytest.approx(150.0)
        assert d["fundamental_freq_hz"] == pytest.approx(1.2)


class TestBVPFeaturesToJson:

    def test_returns_valid_json_string(self):
        json_str = BVPFeatures().to_json()
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)

    def test_nan_becomes_null(self):
        parsed = json.loads(BVPFeatures().to_json())
        for k, v in parsed.items():
            if k.startswith("_"):
                continue
            if isinstance(v, float):
                assert not (v != v), f"Field '{k}' is NaN literal in JSON — phải là null"

    def test_has_schema_version(self):
        parsed = json.loads(BVPFeatures().to_json())
        assert "_schema_version" in parsed
        assert isinstance(parsed["_schema_version"], str)

    def test_known_value_in_json(self):
        feat = BVPFeatures(mean_pulse_amplitude=0.75)
        parsed = json.loads(feat.to_json())
        assert parsed["mean_pulse_amplitude"] == pytest.approx(0.75)

    def test_indent_parameter_respected(self):
        json_compact = BVPFeatures().to_json(indent=None)
        json_indented = BVPFeatures().to_json(indent=4)
        # Indented version phải dài hơn
        assert len(json_indented) > len(json_compact)


class TestBVPFeaturesImmutability:

    def test_frozen_cannot_set_attribute(self):
        feat = BVPFeatures()
        with pytest.raises((TypeError, AttributeError)):
            feat.mean_rise_time_ms = 999.0  # type: ignore[misc]

    def test_frozen_cannot_delete_attribute(self):
        feat = BVPFeatures()
        with pytest.raises((TypeError, AttributeError)):
            del feat.valid_beat_count  # type: ignore[misc]


class TestBVPFeaturesGroupCoverage:
    """Kiểm tra đủ 4 nhóm đặc trưng đã được khai báo trong schema."""

    def test_has_morphology_fields(self):
        names = set(BVPFeatures.feature_names())
        morphology = {
            "mean_rise_time_ms", "mean_decay_time_ms", "std_rise_time_ms",
            "mean_systolic_ratio", "mean_pw25_ms", "mean_pw50_ms", "mean_pw75_ms",
            "mean_area_ratio", "aix_proxy", "apg_aging_index",
        }
        assert morphology.issubset(names), f"Missing: {morphology - names}"

    def test_has_amplitude_fields(self):
        names = set(BVPFeatures.feature_names())
        amplitude = {"mean_pulse_amplitude", "pulse_amp_cv", "notch_relative_amp"}
        assert amplitude.issubset(names)

    def test_has_spectral_fields(self):
        names = set(BVPFeatures.feature_names())
        spectral = {
            "fundamental_freq_hz", "harmonic_ratio_h2", "harmonic_ratio_h3",
            "spectral_entropy", "in_band_power_ratio",
        }
        assert spectral.issubset(names)

    def test_has_trend_fields(self):
        names = set(BVPFeatures.feature_names())
        trend = {
            "baseline_drift_slope", "bvp_skewness", "bvp_kurtosis",
            "ibi_std_ms", "ibi_mean_ms",
        }
        assert trend.issubset(names)
