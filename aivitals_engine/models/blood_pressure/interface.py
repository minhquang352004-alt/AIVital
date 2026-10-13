from collections.abc import Mapping
from enum import StrEnum
from typing import Literal, Protocol

from pydantic import Field, model_validator

from aivitals_engine.contracts.result import ContractModel, ModelInfo, ResultStatus, ValidationIssue


class BloodPressureUse(StrEnum):
    RESEARCH_ONLY = "research_only"
    WELLNESS_ESTIMATE = "wellness_estimate"


class ModelNotFittedError(RuntimeError):
    pass


class BloodPressureEstimate(ContractModel):
    sbp_mmhg: float | None
    dbp_mmhg: float | None
    unit: Literal["mmHg"] = "mmHg"
    confidence: float = Field(ge=0, le=1)
    status: ResultStatus
    intended_use: BloodPressureUse
    model: ModelInfo
    feature_set_version: str
    missing_features: list[str] = Field(default_factory=list)
    issues: list[ValidationIssue] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_consistency(self) -> "BloodPressureEstimate":
        has_values = self.sbp_mmhg is not None and self.dbp_mmhg is not None
        if self.status is ResultStatus.INVALID and (self.sbp_mmhg is not None or self.dbp_mmhg is not None):
            raise ValueError("Ước tính huyết áp INVALID không được mang giá trị")
        if self.status is not ResultStatus.INVALID and not has_values:
            raise ValueError("Ước tính huyết áp OK/BAD bắt buộc có SBP và DBP")
        return self


class BloodPressureModel(Protocol):
    @property
    def model_info(self) -> ModelInfo: ...

    @property
    def feature_names(self) -> tuple[str, ...]: ...

    def predict(self, features: Mapping[str, float | None]) -> BloodPressureEstimate: ...
