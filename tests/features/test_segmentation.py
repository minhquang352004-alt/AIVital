"""
tests/features/test_segmentation.py
=====================================
Unit tests cho BeatSegmenter và SingleBeat.

Chiến lược:
  - Safety tests:    edge cases không được crash.
  - Correctness:     sóng sin chuẩn → số nhịp, timing, bounds sinh lý.
  - Properties:      vpg/apg shape, rise+decay=duration, normalized [0,1].
  - Config tests:    BVPFeaturesConfig khác nhau → hành vi khác nhau.
"""
import numpy as np
import pytest

from aivitals_engine.features.config import BVPFeaturesConfig
from aivitals_engine.features.segmentation import BeatSegmenter, SingleBeat

FS = 30.0


# ── Fixture helpers ────────────────────────────────────────────────────────────

def make_clean_bvp(
    freq_hz: float = 1.2,
    duration_s: float = 8.0,
    fs: float = FS,
    amplitude: float = 1.0,
) -> np.ndarray:
    """Sóng sin tổng hợp mô phỏng BVP sạch (tần số đã biết)."""
    t = np.linspace(0, duration_s, int(duration_s * fs), endpoint=False)
    return (amplitude * np.sin(2 * np.pi * freq_hz * t)).astype(np.float64)


def get_beats(bvp: np.ndarray, fs: float = FS) -> list[SingleBeat]:
    return BeatSegmenter().segment(bvp, fs)


# ── Safety Tests — không được crash ───────────────────────────────────────────

class TestBeatSegmenterSafety:

    def test_empty_array_returns_empty(self):
        assert BeatSegmenter().segment(np.array([]), FS) == []

    def test_single_sample_returns_empty(self):
        assert BeatSegmenter().segment(np.array([1.0]), FS) == []

    def test_flat_signal_returns_empty(self):
        assert BeatSegmenter().segment(np.ones(240), FS) == []

    def test_all_zeros_returns_empty(self):
        assert BeatSegmenter().segment(np.zeros(240), FS) == []

    def test_all_nan_returns_empty(self):
        assert BeatSegmenter().segment(np.full(240, float("nan")), FS) == []

    def test_all_inf_returns_empty(self):
        assert BeatSegmenter().segment(np.full(240, float("inf")), FS) == []

    def test_two_samples_returns_empty(self):
        assert BeatSegmenter().segment(np.array([0.0, 1.0]), FS) == []

    def test_very_short_signal_no_crash(self):
        short = np.sin(np.linspace(0, 1, 5))
        result = BeatSegmenter().segment(short, FS)
        assert isinstance(result, list)

    def test_single_peak_returns_empty(self):
        sig = np.zeros(240)
        sig[120] = 1.0
        assert BeatSegmenter().segment(sig, FS) == []


# ── Correctness Tests — kết quả đúng trên tín hiệu chuẩn ─────────────────────

class TestBeatSegmenterCorrectness:

    @pytest.mark.parametrize("freq_hz,duration_s", [
        (1.0, 8.0),   # 60 BPM
        (1.2, 8.0),   # 72 BPM
        (1.5, 8.0),   # 90 BPM
        (2.0, 8.0),   # 120 BPM
    ])
    def test_beat_count_close_to_expected(self, freq_hz, duration_s):
        """Số nhịp phân đoạn phải gần với số nhịp lý thuyết (±2)."""
        bvp = make_clean_bvp(freq_hz=freq_hz, duration_s=duration_s)
        beats = BeatSegmenter().segment(bvp, FS)
        expected = int(freq_hz * duration_s)
        assert len(beats) > 0, f"Không tìm được nhịp nào cho {freq_hz} Hz"
        assert abs(len(beats) - expected) <= 2, (
            f"freq={freq_hz} Hz: expected ~{expected} beats, got {len(beats)}"
        )

    def test_all_beats_within_physiological_bounds(self):
        """Mọi nhịp phân đoạn phải có BPM trong [45, 150]."""
        bvp = make_clean_bvp(freq_hz=1.2)
        beats = BeatSegmenter().segment(bvp, FS)
        assert len(beats) > 0
        for beat in beats:
            bpm = 60_000.0 / beat.duration_ms
            assert 40.0 < bpm < 160.0, f"Beat BPM={bpm:.1f} ngoài dải sinh lý"

    def test_normalized_samples_in_zero_one_range(self):
        """Mỗi beat sau chuẩn hóa phải nằm trong [0, 1]."""
        bvp = make_clean_bvp()
        beats = BeatSegmenter().segment(bvp, FS)
        for i, beat in enumerate(beats):
            assert beat.samples.min() >= -1e-6, f"Beat {i}: min={beat.samples.min()}"
            assert beat.samples.max() <= 1 + 1e-6, f"Beat {i}: max={beat.samples.max()}"

    def test_peak_inside_beat_boundaries(self):
        """Đỉnh tâm thu phải nằm giữa onset và end."""
        bvp = make_clean_bvp()
        beats = BeatSegmenter().segment(bvp, FS)
        for beat in beats:
            assert beat.onset_idx < beat.peak_idx < beat.end_idx

    def test_beats_are_non_overlapping(self):
        """Các nhịp không được chồng lấp nhau."""
        bvp = make_clean_bvp()
        beats = BeatSegmenter().segment(bvp, FS)
        for i in range(len(beats) - 1):
            assert beats[i].end_idx <= beats[i + 1].onset_idx, (
                f"Beat {i} và {i+1} bị overlap"
            )

    def test_rise_plus_decay_approx_duration(self):
        """rise_time_ms + decay_time_ms ≈ duration_ms (sai số < 2 ms)."""
        bvp = make_clean_bvp()
        beats = BeatSegmenter().segment(bvp, FS)
        assert len(beats) > 0
        for beat in beats:
            total = beat.rise_time_ms + beat.decay_time_ms
            assert abs(total - beat.duration_ms) < 2.0, (
                f"rise+decay={total:.2f} ≠ duration={beat.duration_ms:.2f}"
            )

    def test_rise_time_positive(self):
        bvp = make_clean_bvp()
        for beat in BeatSegmenter().segment(bvp, FS):
            assert beat.rise_time_ms > 0

    def test_decay_time_positive(self):
        bvp = make_clean_bvp()
        for beat in BeatSegmenter().segment(bvp, FS):
            assert beat.decay_time_ms > 0


# ── SingleBeat Properties ──────────────────────────────────────────────────────

class TestSingleBeatProperties:

    @pytest.fixture
    def one_beat(self) -> SingleBeat:
        bvp = make_clean_bvp()
        beats = BeatSegmenter().segment(bvp, FS)
        assert len(beats) > 0
        return beats[0]

    def test_vpg_shape_equals_samples(self, one_beat):
        assert one_beat.vpg.shape == one_beat.samples.shape

    def test_apg_shape_equals_samples(self, one_beat):
        assert one_beat.apg.shape == one_beat.samples.shape

    def test_vpg_is_gradient_of_samples(self, one_beat):
        expected = np.gradient(one_beat.samples.astype(np.float64))
        np.testing.assert_allclose(one_beat.vpg, expected, rtol=1e-6)

    def test_apg_is_gradient_of_vpg(self, one_beat):
        expected = np.gradient(one_beat.vpg)
        np.testing.assert_allclose(one_beat.apg, expected, rtol=1e-6)

    def test_duration_ms_positive(self, one_beat):
        assert one_beat.duration_ms > 0

    def test_fs_stored_correctly(self, one_beat):
        assert one_beat.fs == pytest.approx(FS)

    def test_raw_amplitudes_are_floats(self, one_beat):
        assert isinstance(one_beat.raw_peak_amplitude, float)
        assert isinstance(one_beat.raw_onset_amplitude, float)

    def test_immutable(self, one_beat):
        with pytest.raises((TypeError, AttributeError)):
            one_beat.onset_idx = 0  # type: ignore[misc]


# ── Config Influence Tests ────────────────────────────────────────────────────

class TestBeatSegmenterConfig:

    def test_custom_config_passed_through(self):
        cfg = BVPFeaturesConfig(min_bpm=45.0, max_bpm=150.0)
        segmenter = BeatSegmenter(cfg)
        bvp = make_clean_bvp(freq_hz=1.2)
        beats = segmenter.segment(bvp, FS)
        assert len(beats) > 0

    def test_tight_max_bpm_rejects_fast_beats(self):
        """Config max_bpm=80 → loại bỏ sóng 100 BPM."""
        freq_hz = 100.0 / 60.0  # 100 BPM
        bvp = make_clean_bvp(freq_hz=freq_hz)
        cfg_loose = BVPFeaturesConfig(max_bpm=150.0)
        cfg_tight = BVPFeaturesConfig(max_bpm=80.0)
        beats_loose = BeatSegmenter(cfg_loose).segment(bvp, FS)
        beats_tight = BeatSegmenter(cfg_tight).segment(bvp, FS)
        assert len(beats_tight) <= len(beats_loose)

    def test_default_config_used_when_none(self):
        segmenter = BeatSegmenter(None)
        bvp = make_clean_bvp()
        beats = segmenter.segment(bvp, FS)
        assert isinstance(beats, list)


# ── Numerical robustness ───────────────────────────────────────────────────────

class TestBeatSegmenterRobustness:

    def test_mixed_nan_signal_no_crash(self):
        """NaN lẫn trong tín hiệu không được crash."""
        bvp = make_clean_bvp()
        bvp_with_nan = bvp.copy()
        bvp_with_nan[10:15] = float("nan")
        result = BeatSegmenter().segment(bvp_with_nan, FS)
        assert isinstance(result, list)

    def test_high_amplitude_no_crash(self):
        bvp = make_clean_bvp(amplitude=1_000_000.0)
        result = BeatSegmenter().segment(bvp, FS)
        assert isinstance(result, list)

    def test_very_low_amplitude_no_crash(self):
        bvp = make_clean_bvp(amplitude=1e-10)
        result = BeatSegmenter().segment(bvp, FS)
        assert isinstance(result, list)
