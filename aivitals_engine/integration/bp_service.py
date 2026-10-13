from dataclasses import dataclass
from typing import Optional

from aivitals_engine.contracts.result import VitalsResult
from aivitals_engine.features import BVPFeatures
from aivitals_engine.health.bp_risk import BloodPressureRiskModel
from aivitals_engine.health.risk_model import HealthRiskOutput
from aivitals_engine.models.blood_pressure.features import Demographics, build_bp_features
from aivitals_engine.models.blood_pressure.interface import BloodPressureEstimate, BloodPressureModel


@dataclass(frozen=True)
class BloodPressureAssessment:
    estimate: BloodPressureEstimate
    risk: HealthRiskOutput


class BloodPressureService:
    def __init__(self, model: Optional[BloodPressureModel] = None) -> None:
        self._model = model
        self._risk_model = None if model is None else BloodPressureRiskModel(model)

    @property
    def is_available(self) -> bool:
        return self._model is not None

    def assess(
        self,
        result: VitalsResult,
        bvp_features: Optional[BVPFeatures] = None,
        demographics: Optional[Demographics] = None,
    ) -> Optional[BloodPressureAssessment]:
        if self._model is None or self._risk_model is None:
            return None
        features = build_bp_features(result, bvp_features, demographics)
        estimate = self._model.predict(features)
        return BloodPressureAssessment(estimate=estimate, risk=self._risk_model.from_estimate(estimate, result.result_id))
