from collections.abc import Mapping
from dataclasses import dataclass, field

from aivitals_engine.contracts.result import VitalCode


@dataclass(frozen=True)
class FrequencyBand:
    low_hz: float
    high_hz: float

    def __post_init__(self) -> None:
        if not 0 < self.low_hz < self.high_hz:
            raise ValueError("Dải tần không hợp lệ: cần 0 < low_hz < high_hz")

    def contains(self, frequency_hz: float) -> bool:
        return self.low_hz <= frequency_hz <= self.high_hz


@dataclass(frozen=True)
class PhysiologicalRange:
    minimum: float
    maximum: float

    def contains(self, value: float) -> bool:
        return self.minimum <= value <= self.maximum


@dataclass(frozen=True)
class BeatDetectionConfig:
    pulse_band: FrequencyBand = FrequencyBand(0.7, 3.0)
    min_bpm: float = 40.0
    max_bpm: float = 180.0
    min_prominence: float = 0.3
    expected_period_fraction: float = 0.6
    subharmonic_power_ratio: float = 0.5
    local_median_kernel: int = 5
    local_median_tolerance: float = 0.25

    @property
    def min_ibi_ms(self) -> float:
        return 60000.0 / self.max_bpm

    @property
    def max_ibi_ms(self) -> float:
        return 60000.0 / self.min_bpm


@dataclass(frozen=True)
class HeartRateConfig:
    band: FrequencyBand = FrequencyBand(0.7, 3.0)
    analysis_window_seconds: float = 10.0
    min_window_seconds: float = 6.0
    spectral_resolution_hz: float = 0.005
    snr_tolerance_hz: float = 0.1
    method_agreement_bpm: float = 5.0
    min_beats_for_peak_rate: int = 4
    subharmonic_power_ratio: float = 0.5


@dataclass(frozen=True)
class HRVConfig:
    min_window_seconds: float = 30.0
    min_clean_intervals: int = 20
    max_artifact_ratio: float = 0.2
    min_pulse_snr_db: float = 5.0
    snr_midpoint_db: float = 6.0
    snr_slope: float = 0.6


@dataclass(frozen=True)
class RespiratoryRateConfig:
    band: FrequencyBand = FrequencyBand(0.1, 0.5)
    min_window_seconds: float = 30.0
    resample_hz: float = 4.0
    spectral_resolution_hz: float = 0.002
    snr_tolerance_hz: float = 0.03
    max_component_spread_brpm: float = 4.0
    min_beats_for_modulation: int = 12


@dataclass(frozen=True)
class ConfidenceConfig:
    snr_midpoint_db: float = 2.0
    snr_slope: float = 0.5
    stability_tolerance_bpm: float = 5.0
    snr_weight: float = 0.35
    signal_quality_weight: float = 0.30
    agreement_weight: float = 0.20
    stability_weight: float = 0.15


def default_min_window_seconds() -> dict[VitalCode, float]:
    return {
        VitalCode.HEART_RATE: 6.0,
        VitalCode.HRV_RMSSD: 30.0,
        VitalCode.HRV_SDNN: 30.0,
        VitalCode.HRV_MEAN_IBI: 30.0,
        VitalCode.RESPIRATORY_RATE: 30.0,
    }


def default_physiological_ranges() -> dict[VitalCode, PhysiologicalRange]:
    return {
        VitalCode.HEART_RATE: PhysiologicalRange(40.0, 180.0),
        VitalCode.HRV_RMSSD: PhysiologicalRange(5.0, 250.0),
        VitalCode.HRV_SDNN: PhysiologicalRange(5.0, 300.0),
        VitalCode.HRV_MEAN_IBI: PhysiologicalRange(330.0, 1500.0),
        VitalCode.RESPIRATORY_RATE: PhysiologicalRange(6.0, 30.0),
    }


@dataclass(frozen=True)
class ValidationConfig:
    signal_quality_ok: float = 0.6
    signal_quality_invalid: float = 0.3
    confidence_ok: float = 0.6
    confidence_invalid: float = 0.3
    missing_ratio_ok: float = 0.1
    missing_ratio_invalid: float = 0.3
    min_values_for_stability: int = 4
    min_window_seconds: Mapping[VitalCode, float] = field(default_factory=default_min_window_seconds)
    ranges: Mapping[VitalCode, PhysiologicalRange] = field(default_factory=default_physiological_ranges)
    jump_tolerance: Mapping[VitalCode, float] = field(
        default_factory=lambda: {VitalCode.HEART_RATE: 8.0, VitalCode.RESPIRATORY_RATE: 4.0}
    )
    jump_rate_per_second: Mapping[VitalCode, float] = field(
        default_factory=lambda: {VitalCode.HEART_RATE: 3.0, VitalCode.RESPIRATORY_RATE: 0.5}
    )
    stability_std_limit: Mapping[VitalCode, float] = field(
        default_factory=lambda: {VitalCode.HEART_RATE: 8.0, VitalCode.RESPIRATORY_RATE: 4.0}
    )
    cross_roi_spread_limit: Mapping[VitalCode, float] = field(
        default_factory=lambda: {VitalCode.HEART_RATE: 10.0}
    )


@dataclass(frozen=True)
class VitalsConfig:
    beats: BeatDetectionConfig = field(default_factory=BeatDetectionConfig)
    heart_rate: HeartRateConfig = field(default_factory=HeartRateConfig)
    hrv: HRVConfig = field(default_factory=HRVConfig)
    respiratory_rate: RespiratoryRateConfig = field(default_factory=RespiratoryRateConfig)
    confidence: ConfidenceConfig = field(default_factory=ConfidenceConfig)
    validation: ValidationConfig = field(default_factory=ValidationConfig)
    tracker_history_size: int = 10
    tracker_smoothing_alpha: float = 0.5
