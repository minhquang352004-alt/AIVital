"""
AIVitals Vitals Module - Heart Rate (HR)
Trích xuất nhịp tim (BPM) từ sóng BVP bằng FFT hoặc Peak Detection.
Kế thừa & tối ưu từ rPPG-Toolbox/evaluation/post_process.py
"""

from dataclasses import dataclass
from typing import Optional

import numpy as np
import scipy.signal

from aivitals_engine.config.vitals_config import BeatDetectionConfig, HeartRateConfig
from aivitals_engine.contracts.bvp_window import BVPWindow
from aivitals_engine.contracts.result import AlgorithmInfo
from aivitals_engine.vitals.beats import BeatExtractor, BeatSeries
from aivitals_engine.vitals.failures import ComputationFailure
from aivitals_engine.vitals.preprocess import prepare_pulse_signal
from aivitals_engine.vitals.spectral import SpectralPeak, find_spectral_peak

HEART_RATE_ALGORITHM = AlgorithmInfo(name="hr_spectral_peak_fusion", version="0.1.0")
UNKNOWN_AGREEMENT = 0.5


@dataclass(frozen=True)
class HeartRateEstimate:
    bpm: float | None
    spectral_bpm: float | None = None
    peak_bpm: float | None = None
    snr_db: float | None = None
    method_agreement: float = 0.0
    beats: BeatSeries | None = None
    analysed_seconds: float = 0.0
    failure_reason: ComputationFailure | None = None


def compute_peak_rate(beats: BeatSeries, min_beats: int) -> float | None:
    if beats.clean_interval_count < min_beats:
        return None
    return float(60000.0 / np.median(beats.clean_ibi_ms))


def compute_agreement(spectral_bpm: float, peak_bpm: float | None, tolerance_bpm: float) -> float:
    if peak_bpm is None:
        return UNKNOWN_AGREEMENT
    return float(np.clip(1.0 - abs(spectral_bpm - peak_bpm) / (2.0 * tolerance_bpm), 0.0, 1.0))


class HeartRateEstimator:
    algorithm = HEART_RATE_ALGORITHM

    def __init__(self, config: HeartRateConfig | None = None, beat_config: BeatDetectionConfig | None = None) -> None:
        self._config = config or HeartRateConfig()
        self._beat_extractor = BeatExtractor(beat_config)

    def estimate(self, window: BVPWindow) -> HeartRateEstimate:
        segment = window.tail(self._config.analysis_window_seconds)
        duration = segment.duration_seconds
        if duration < self._config.min_window_seconds:
            return HeartRateEstimate(bpm=None, analysed_seconds=duration, failure_reason=ComputationFailure.WINDOW_TOO_SHORT)
        prepared = prepare_pulse_signal(segment.samples, segment.sampling_rate_hz, self._config.band)
        peak = self._spectral_peak(prepared, segment.sampling_rate_hz)
        if peak is None:
            return HeartRateEstimate(bpm=None, analysed_seconds=duration, failure_reason=ComputationFailure.NO_SPECTRAL_PEAK)
        beats = self._beat_extractor.extract_from_prepared(prepared, segment.sampling_rate_hz)
        return self._fuse(peak, beats, duration)

    def estimate_spectral_bpm(self, samples: np.ndarray, sampling_rate_hz: float) -> float | None:
        if samples.size / sampling_rate_hz < self._config.min_window_seconds:
            return None
        prepared = prepare_pulse_signal(samples, sampling_rate_hz, self._config.band)
        peak = self._spectral_peak(prepared, sampling_rate_hz)
        return None if peak is None else peak.per_minute

    def _spectral_peak(self, prepared: np.ndarray, sampling_rate_hz: float) -> SpectralPeak | None:
        return find_spectral_peak(
            prepared,
            sampling_rate_hz,
            self._config.band,
            self._config.spectral_resolution_hz,
            self._config.snr_tolerance_hz,
            self._config.subharmonic_power_ratio,
        )

    def _fuse(self, peak: SpectralPeak, beats: BeatSeries, duration: float) -> HeartRateEstimate:
        spectral_bpm = peak.per_minute
        peak_bpm = compute_peak_rate(beats, self._config.min_beats_for_peak_rate)
        tolerance = self._config.method_agreement_bpm
        fused_bpm = spectral_bpm
        if peak_bpm is not None and abs(spectral_bpm - peak_bpm) <= tolerance:
            fused_bpm = (spectral_bpm + peak_bpm) / 2.0
        return HeartRateEstimate(
            bpm=float(fused_bpm),
            spectral_bpm=float(spectral_bpm),
            peak_bpm=peak_bpm,
            snr_db=peak.snr_db,
            method_agreement=compute_agreement(spectral_bpm, peak_bpm, tolerance),
            beats=beats,
            analysed_seconds=duration,
        )


def _next_power_of_2(x: int) -> int:
    """Tính lũy thừa 2 gần nhất để tối ưu FFT periodogram."""
    return 1 if x == 0 else 2 ** (x - 1).bit_length()


def calculate_fft_hr(
    bvp_signal: np.ndarray,
    fs: float = 30.0,
    low_cutoff_hz: float = 0.75,
    high_cutoff_hz: float = 2.50
) -> float:
    """
    Ước lượng nhịp tim (BPM) qua biến đổi Fourier (FFT Periodogram).
    Tham chiếu: rPPG-Toolbox evaluation/post_process.py (_calculate_fft_hr)

    Args:
        bvp_signal: Tín hiệu BVP 1D
        fs: Tần số lấy mẫu (FPS)
        low_cutoff_hz: Tần số cắt thấp (0.75 Hz = 45 BPM)
        high_cutoff_hz: Tần số cắt cao (2.50 Hz = 150 BPM)

    Returns:
        Nhịp tim ước lượng (BPM)
    """
    sig = np.asarray(bvp_signal, dtype=np.float64).flatten()
    if len(sig) < 16:
        return 0.0

    nfft = max(512, _next_power_of_2(len(sig)))
    f_ppg, pxx_ppg = scipy.signal.periodogram(sig, fs=fs, nfft=nfft, detrend=False)

    mask = (f_ppg >= low_cutoff_hz) & (f_ppg <= high_cutoff_hz)
    if not np.any(mask):
        return 0.0

    band_f = f_ppg[mask]
    band_pxx = pxx_ppg[mask]

    peak_freq = band_f[np.argmax(band_pxx)]
    return float(peak_freq * 60.0)


def calculate_peak_hr(bvp_signal: np.ndarray, fs: float = 30.0) -> float:
    """
    Ước lượng nhịp tim (BPM) qua phát hiện khoảng cách giữa các đỉnh xung (Peak Detection).
    Tham chiếu: rPPG-Toolbox evaluation/post_process.py (_calculate_peak_hr)

    Args:
        bvp_signal: Tín hiệu BVP 1D
        fs: Tần số lấy mẫu (FPS)

    Returns:
        Nhịp tim ước lượng (BPM)
    """
    sig = np.asarray(bvp_signal, dtype=np.float64).flatten()
    if len(sig) < 16:
        return 0.0

    # Khoảng cách tối thiểu giữa 2 đỉnh là 0.4s (tương ứng nhịp tối đa 150 BPM)
    min_dist = max(1, int(fs * 0.4))
    peaks, _ = scipy.signal.find_peaks(sig, distance=min_dist)
    if len(peaks) < 2:
        return 0.0

    mean_diff = np.mean(np.diff(peaks))
    if mean_diff <= 0:
        return 0.0

    return float(60.0 / (mean_diff / fs))
