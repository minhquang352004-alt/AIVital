"""
tests/features/test_extractors.py
==================================
Unit tests cho 4 Partial Feature Extractor:
  - MorphologyExtractor (Group A)
  - AmplitudeExtractor  (Group B)
  - SpectralExtractor   (Group C)
  - TrendExtractor      (Group D)

Kiểm tra:
  - Schema Contract: Mọi key trả về phải là field hợp lệ trong BVPFeatures.
  - Correctness: Giá trị trên tín hiệu tổng hợp chuẩn.
  - Numerical Bounds: Tỷ lệ và entropy nằm trong khoảng sinh lý [0, 1].
  - Safety: Không crash trên tín hiệu ngắn, rỗng, phẳng, toàn NaN.
"""
from dataclasses import fields

import numpy as np
import pytest

from aivitals_engine.features.amplitude import AmplitudeExtractor
from aivitals_engine.features.config import BVPFeaturesConfig
from aivitals_engine.features.morphology import MorphologyExtractor
from aivitals_engine.features.schema import BVPFeatures
from aivitals_engine.features.segmentation import BeatSegmenter, SingleBeat
from aivitals_engine.features.spectral import SpectralExtractor
from aivitals_engine.features.trend import TrendExtractor

FS = 30.0
_VALID_FEATURE_KEYS = frozenset({f.name for f in fields(BVPFeatures)})


# ── Fixtures & Test Helpers ───────────────────────────────────────────────────

def make_synth_bvp(
    freq_hz: float = 1.2,
    duration_s: float = 8.0,
    fs: float = FS,
    snr_db: float = 25.0,
    seed: int = 42,
) -> np.ndarray:
    """Tạo tín hiệu BVP mô phỏng có nhịp và nhiễu Gaussian nhẹ."""
    t = np.linspace(0, duration_s, int(duration_s * fs), endpoint=False)
    sig = np.sin(2 * np.pi * freq_hz * t)
    noise_std = 10.0 ** (-snr_db / 20.0)
    sig += np.random.default_rng(seed).normal(0, noise_std, sig.size)
    return sig.astype(np.float64)


def extract_beats(bvp: np.ndarray, fs: float = FS) -> list[SingleBeat]:
    return BeatSegmenter().segment(bvp, fs)


# ── Schema Contract Tests ──────────────────────────────────────────────────────

class TestExtractorsSchemaContract:
    """Mọi key do bất kỳ extractor nào trả về phải khớp chính xác với field BVPFeatures."""

    @pytest.fixture
    def synth_data(self):
        bvp = make_synth_bvp()
        beats = extract_beats(bvp)
        return bvp, beats

    def test_morphology_keys_in_schema(self, synth_data):
        bvp, beats = synth_data
        result = MorphologyExtractor().extract(bvp, FS, beats)
        assert len(result) > 0
        for key in result:
            assert key in _VALID_FEATURE_KEYS, f"Unknown key in Morphology: '{key}'"

    def test_amplitude_keys_in_schema(self, synth_data):
        bvp, beats = synth_data
        result = AmplitudeExtractor().extract(bvp, FS, beats)
        assert len(result) > 0
        for key in result:
            assert key in _VALID_FEATURE_KEYS, f"Unknown key in Amplitude: '{key}'"

    def test_spectral_keys_in_schema(self, synth_data):
        bvp, beats = synth_data
        result = SpectralExtractor().extract(bvp, FS, beats)
        assert len(result) > 0
        for key in result:
            assert key in _VALID_FEATURE_KEYS, f"Unknown key in Spectral: '{key}'"

    def test_trend_keys_in_schema(self, synth_data):
        bvp, beats = synth_data
        result = TrendExtractor().extract(bvp, FS, beats)
        assert len(result) > 0
        for key in result:
            assert key in _VALID_FEATURE_KEYS, f"Unknown key in Trend: '{key}'"


# ── Group A: MorphologyExtractor Tests ────────────────────────────────────────

class TestMorphologyExtractor:

    @pytest.fixture
    def morph_result(self):
        bvp = make_synth_bvp(freq_hz=1.2)
        beats = extract_beats(bvp)
        return MorphologyExtractor().extract(bvp, FS, beats)

    def test_rise_time_positive(self, morph_result):
        val = morph_result["mean_rise_time_ms"]
        assert not np.isnan(val)
        assert val > 0

    def test_decay_time_positive(self, morph_result):
        val = morph_result["mean_decay_time_ms"]
        assert not np.isnan(val)
        assert val > 0

    def test_systolic_ratio_in_unit_range(self, morph_result):
        val = morph_result["mean_systolic_ratio"]
        assert not np.isnan(val)
        assert 0.0 < val < 1.0

    def test_pw25_greater_than_pw50(self, morph_result):
        """Độ rộng xung ở đáy (25% chiều cao) phải lớn hơn ở lưng chừng (50% chiều cao)."""
        pw25 = morph_result["mean_pw25_ms"]
        pw50 = morph_result["mean_pw50_ms"]
        if not (np.isnan(pw25) or np.isnan(pw50)):
            assert pw25 >= pw50, f"pw25={pw25} should >= pw50={pw50}"

    def test_empty_beats_returns_empty_dict(self):
        result = MorphologyExtractor().extract(np.ones(240), FS, [])
        assert result == {}

    def test_single_beat_insufficient_returns_empty(self):
        """min_valid_beats=2 → 1 beat duy nhất thì không tính."""
        bvp = make_synth_bvp()
        beats = extract_beats(bvp)[:1]
        result = MorphologyExtractor().extract(bvp, FS, beats)
        assert result == {}

    def test_flat_signal_no_crash(self):
        result = MorphologyExtractor().extract(np.zeros(240), FS, [])
        assert isinstance(result, dict)


# ── Group B: AmplitudeExtractor Tests ─────────────────────────────────────────

class TestAmplitudeExtractor:

    @pytest.fixture
    def amp_result(self):
        bvp = make_synth_bvp(freq_hz=1.2)
        beats = extract_beats(bvp)
        return AmplitudeExtractor().extract(bvp, FS, beats)

    def test_mean_pulse_amplitude_positive(self, amp_result):
        val = amp_result["mean_pulse_amplitude"]
        assert not np.isnan(val)
        assert val > 0

    def test_pulse_amp_cv_non_negative(self, amp_result):
        val = amp_result["pulse_amp_cv"]
        if not np.isnan(val):
            assert val >= 0.0

    def test_empty_beats_returns_empty_dict(self):
        result = AmplitudeExtractor().extract(np.ones(240), FS, [])
        assert result == {}

    def test_flat_signal_no_crash(self):
        result = AmplitudeExtractor().extract(np.zeros(240), FS, [])
        assert isinstance(result, dict)


# ── Group C: SpectralExtractor Tests ──────────────────────────────────────────

class TestSpectralExtractor:

    @pytest.fixture
    def spec_result(self):
        bvp = make_synth_bvp(freq_hz=1.2, snr_db=30.0)
        beats = extract_beats(bvp)
        return SpectralExtractor().extract(bvp, FS, beats)

    def test_fundamental_freq_recovers_ground_truth(self, spec_result):
        """f0 phải gần 1.2 Hz (sai số < 0.15 Hz)."""
        f0 = spec_result["fundamental_freq_hz"]
        assert not np.isnan(f0)
        assert abs(f0 - 1.2) < 0.15, f"f0={f0} lệch quá nhiều so với 1.2 Hz"

    def test_fundamental_freq_within_cardiac_band(self, spec_result):
        f0 = spec_result["fundamental_freq_hz"]
        assert 0.75 <= f0 <= 2.50

    def test_spectral_entropy_in_unit_range(self, spec_result):
        ent = spec_result["spectral_entropy"]
        if not np.isnan(ent):
            assert 0.0 <= ent <= 1.0

    def test_in_band_power_ratio_in_unit_range(self, spec_result):
        ibp = spec_result["in_band_power_ratio"]
        if not np.isnan(ibp):
            assert 0.0 <= ibp <= 1.0

    def test_clean_signal_in_band_power_high(self, spec_result):
        """Sóng sạch trong dải tim mạch → tỷ lệ năng lượng trong dải phải cao."""
        ibp = spec_result["in_band_power_ratio"]
        if not np.isnan(ibp):
            assert ibp > 0.5, f"in_band_power_ratio={ibp} quá thấp cho sóng sạch"

    def test_too_short_signal_returns_empty_dict(self):
        result = SpectralExtractor().extract(np.array([1.0, 2.0]), FS, [])
        assert result == {}

    def test_flat_signal_safe(self):
        result = SpectralExtractor().extract(np.ones(240), FS, [])
        assert isinstance(result, dict)


# ── Group D: TrendExtractor Tests ─────────────────────────────────────────────

class TestTrendExtractor:

    def test_slope_of_flat_signal_near_zero(self):
        bvp = np.zeros(240)
        result = TrendExtractor().extract(bvp, FS, [])
        slope = result["baseline_drift_slope"]
        assert not np.isnan(slope)
        assert abs(slope) < 1e-6

    def test_slope_of_linear_ramp_is_positive(self):
        t = np.arange(240, dtype=np.float64) / FS
        ramp = 2.0 * t  # Slope lý thuyết = 2.0
        result = TrendExtractor().extract(ramp, FS, [])
        slope = result["baseline_drift_slope"]
        assert not np.isnan(slope)
        assert slope == pytest.approx(2.0, rel=1e-3)

    def test_skewness_and_kurtosis_calculated(self):
        bvp = make_synth_bvp()
        result = TrendExtractor().extract(bvp, FS, [])
        assert not np.isnan(result["bvp_skewness"])
        assert not np.isnan(result["bvp_kurtosis"])

    def test_ibi_mean_and_std_from_beats(self):
        bvp = make_synth_bvp(freq_hz=1.2)  # 72 BPM → IBI ~ 833 ms
        beats = extract_beats(bvp)
        result = TrendExtractor().extract(bvp, FS, beats)
        ibi_mean = result["ibi_mean_ms"]
        assert not np.isnan(ibi_mean)
        assert abs(ibi_mean - 833.0) < 100.0  # Sai số < 100ms

    def test_empty_beats_gives_nan_for_ibi(self):
        bvp = np.sin(np.linspace(0, 1, 30))
        result = TrendExtractor().extract(bvp, FS, [])
        assert np.isnan(result["ibi_std_ms"])
        assert np.isnan(result["ibi_mean_ms"])

    def test_very_short_signal_returns_empty_dict(self):
        result = TrendExtractor().extract(np.array([1.0]), FS, [])
        assert result == {}
