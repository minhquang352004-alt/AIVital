from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from aivitals_engine.config.vitals_config import ConfidenceConfig, HRVConfig
from aivitals_engine.vitals.hrv import HRVEstimate
from aivitals_engine.vitals.rr import RespiratoryRateEstimate

EXPECTED_RESPIRATORY_COMPONENTS = 3
MIN_VALUES_FOR_STABILITY = 2


@dataclass(frozen=True)
class ConfidenceInputs:
    snr_db: float | None = None
    signal_quality: float | None = None
    method_agreement: float | None = None
    temporal_stability: float | None = None
    missing_ratio: float = 0.0


def clip_unit(value: float) -> float:
    return float(np.clip(value, 0.0, 1.0))


def snr_to_score(snr_db: float, config: ConfidenceConfig) -> float:
    return float(1.0 / (1.0 + np.exp(-config.snr_slope * (snr_db - config.snr_midpoint_db))))


def stability_score(recent_values: Sequence[float], tolerance: float) -> float | None:
    if len(recent_values) < MIN_VALUES_FOR_STABILITY:
        return None
    return float(np.exp(-np.std(recent_values) / tolerance))


def compute_confidence(inputs: ConfidenceInputs, config: ConfidenceConfig | None = None) -> float:
    config = config or ConfidenceConfig()
    weighted_scores = [
        (None if inputs.snr_db is None else snr_to_score(inputs.snr_db, config), config.snr_weight),
        (inputs.signal_quality, config.signal_quality_weight),
        (inputs.method_agreement, config.agreement_weight),
        (inputs.temporal_stability, config.stability_weight),
    ]
    available = [(score, weight) for score, weight in weighted_scores if score is not None]
    if not available:
        return 0.0
    total_weight = sum(weight for _, weight in available)
    score = sum(score * weight for score, weight in available) / total_weight
    return clip_unit(score * (1.0 - inputs.missing_ratio))


def derive_hrv_confidence(heart_rate_confidence: float, estimate: HRVEstimate, config: HRVConfig) -> float:
    if not estimate.is_available or estimate.pulse_snr_db is None:
        return 0.0
    coverage = min(1.0, estimate.clean_interval_count / (2.0 * config.min_clean_intervals))
    cleanliness = 1.0 - estimate.artifact_ratio
    snr_factor = 1.0 / (1.0 + np.exp(-config.snr_slope * (estimate.pulse_snr_db - config.snr_midpoint_db)))
    return clip_unit(heart_rate_confidence * (0.5 + 0.5 * coverage) * cleanliness * snr_factor)


def derive_respiratory_confidence(
    heart_rate_confidence: float, estimate: RespiratoryRateEstimate, max_spread_brpm: float
) -> float:
    if estimate.brpm is None:
        return 0.0
    component_count = len(estimate.component_brpm)
    count_factor = min(1.0, component_count / EXPECTED_RESPIRATORY_COMPONENTS)
    agreement = 0.0
    if component_count >= 2 and estimate.component_spread_brpm is not None:
        agreement = 1.0 - estimate.component_spread_brpm / max_spread_brpm
    return clip_unit(heart_rate_confidence * (0.5 + 0.25 * count_factor + 0.25 * agreement))
