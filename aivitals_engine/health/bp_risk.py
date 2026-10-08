from collections.abc import Mapping

import numpy as np

from aivitals_engine.contracts.result import ModelInfo, ResultStatus, VitalsResult
from aivitals_engine.health.risk_model import EvidenceLevel, HealthRiskOutput, RiskCategory
from aivitals_engine.models.blood_pressure.interface import BloodPressureEstimate, BloodPressureModel

BP_RISK_CODE = "blood_pressure_category"
BP_RISK_MODEL_NAME = "bp_category_risk"
NORMAL_SYSTOLIC_MMHG = 120.0
NORMAL_DIASTOLIC_MMHG = 80.0
ELEVATED_SYSTOLIC_MMHG = 140.0
ELEVATED_DIASTOLIC_MMHG = 90.0
SCORE_SYSTOLIC_FLOOR = 110.0
SCORE_SYSTOLIC_SPAN = 50.0
SCORE_DIASTOLIC_FLOOR = 70.0
SCORE_DIASTOLIC_SPAN = 30.0
SCORE_DECIMALS = 3


def classify_blood_pressure(sbp_mmhg: float, dbp_mmhg: float) -> RiskCategory:
    if sbp_mmhg >= ELEVATED_SYSTOLIC_MMHG or dbp_mmhg >= ELEVATED_DIASTOLIC_MMHG:
        return RiskCategory.ELEVATED
    if sbp_mmhg >= NORMAL_SYSTOLIC_MMHG or dbp_mmhg >= NORMAL_DIASTOLIC_MMHG:
        return RiskCategory.MODERATE
    return RiskCategory.LOW


def blood_pressure_score(sbp_mmhg: float, dbp_mmhg: float) -> float:
    systolic = (sbp_mmhg - SCORE_SYSTOLIC_FLOOR) / SCORE_SYSTOLIC_SPAN
    diastolic = (dbp_mmhg - SCORE_DIASTOLIC_FLOOR) / SCORE_DIASTOLIC_SPAN
    return round(float(np.clip(max(systolic, diastolic), 0.0, 1.0)), SCORE_DECIMALS)


class BloodPressureRiskModel:
    def __init__(self, bp_model: BloodPressureModel, version: str = "0.1.0") -> None:
        self._bp_model = bp_model
        self._version = version

    @property
    def model_info(self) -> ModelInfo:
        return ModelInfo(name=BP_RISK_MODEL_NAME, version=self._version)

    def assess(self, result: VitalsResult, features: Mapping[str, float | None]) -> HealthRiskOutput:
        return self.from_estimate(self._bp_model.predict(features), result.result_id)

    def from_estimate(self, estimate: BloodPressureEstimate, source_result_id: str) -> HealthRiskOutput:
        is_invalid = estimate.status is ResultStatus.INVALID
        return HealthRiskOutput(
            risk_code=BP_RISK_CODE,
            score=None if is_invalid else blood_pressure_score(estimate.sbp_mmhg, estimate.dbp_mmhg),
            category=None if is_invalid else classify_blood_pressure(estimate.sbp_mmhg, estimate.dbp_mmhg),
            status=estimate.status,
            evidence_level=EvidenceLevel.INSUFFICIENT,
            model=self.model_info,
            source_result_id=source_result_id,
            issues=list(estimate.issues),
        )
