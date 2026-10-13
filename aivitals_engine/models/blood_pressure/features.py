from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np

from aivitals_engine.contracts.result import VitalCode, VitalsResult
from aivitals_engine.features.schema import _FEATURE_VECTOR_VERSION, BVPFeatures

BP_FEATURE_SET_VERSION = f"bp_features_v2+bvp_{_FEATURE_VECTOR_VERSION}"

VITAL_FEATURE_NAMES: dict[VitalCode, str] = {
    VitalCode.HEART_RATE: "heart_rate_bpm",
    VitalCode.HRV_RMSSD: "hrv_rmssd_ms",
    VitalCode.HRV_SDNN: "hrv_sdnn_ms",
    VitalCode.HRV_MEAN_IBI: "mean_ibi_ms",
    VitalCode.RESPIRATORY_RATE: "respiratory_rate_brpm",
}

DEMOGRAPHIC_FEATURE_NAMES: tuple[str, ...] = ("age_years", "sex_male", "bmi")

BP_FEATURE_NAMES: tuple[str, ...] = (
    *VITAL_FEATURE_NAMES.values(),
    *BVPFeatures.feature_names(),
    *DEMOGRAPHIC_FEATURE_NAMES,
)


@dataclass(frozen=True)
class Demographics:
    age_years: float | None = None
    sex_male: bool | None = None
    height_cm: float | None = None
    weight_kg: float | None = None

    @property
    def bmi(self) -> float | None:
        if not self.height_cm or not self.weight_kg:
            return None
        height_m = self.height_cm / 100.0
        return self.weight_kg / (height_m * height_m)

    def to_features(self) -> dict[str, float | None]:
        return {
            "age_years": self.age_years,
            "sex_male": None if self.sex_male is None else float(self.sex_male),
            "bmi": self.bmi,
        }


@dataclass(frozen=True)
class FeatureVector:
    names: tuple[str, ...]
    values: np.ndarray
    feature_set_version: str

    @property
    def missing_names(self) -> list[str]:
        return [name for name, value in zip(self.names, self.values) if np.isnan(value)]

    @property
    def missing_ratio(self) -> float:
        return len(self.missing_names) / len(self.names) if self.names else 1.0


def finite_or_none(value: float | None) -> float | None:
    if value is None:
        return None
    number = float(value)
    return number if np.isfinite(number) else None


def build_feature_vector(
    features: Mapping[str, float | None],
    names: Sequence[str] = BP_FEATURE_NAMES,
    feature_set_version: str = BP_FEATURE_SET_VERSION,
) -> FeatureVector:
    values = np.array([np.nan if finite_or_none(features.get(name)) is None else float(features[name]) for name in names])
    return FeatureVector(names=tuple(names), values=values, feature_set_version=feature_set_version)


def extract_vital_features(result: VitalsResult) -> dict[str, float]:
    return {
        VITAL_FEATURE_NAMES[vital.code]: vital.value
        for vital in result.accepted_vitals()
        if vital.code in VITAL_FEATURE_NAMES and vital.value is not None
    }


def extract_bvp_features(features: BVPFeatures) -> dict[str, float | None]:
    return {name: finite_or_none(value) for name, value in zip(BVPFeatures.feature_names(), features.to_numpy())}


def build_bp_features(
    result: VitalsResult | None = None,
    bvp_features: BVPFeatures | None = None,
    demographics: Demographics | None = None,
) -> dict[str, float | None]:
    features: dict[str, float | None] = dict.fromkeys(BP_FEATURE_NAMES)
    if result is not None:
        features.update(extract_vital_features(result))
    if bvp_features is not None:
        features.update(extract_bvp_features(bvp_features))
    if demographics is not None:
        features.update(demographics.to_features())
    return features
