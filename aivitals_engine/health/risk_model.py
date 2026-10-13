from collections.abc import Mapping
from enum import StrEnum
from typing import Literal, Protocol

from pydantic import Field, model_validator

from aivitals_engine.contracts.result import ContractModel, ModelInfo, ResultStatus, ValidationIssue, VitalsResult


class EvidenceLevel(StrEnum):
    ESTABLISHED = "established"
    PROMISING = "promising"
    INSUFFICIENT = "insufficient"
    NOT_RECOMMENDED = "not_recommended"


class RiskCategory(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    ELEVATED = "elevated"


class HealthRiskOutput(ContractModel):
    risk_code: str = Field(min_length=1)
    score: float | None = Field(default=None, ge=0, le=1)
    category: RiskCategory | None = None
    status: ResultStatus
    evidence_level: EvidenceLevel
    intended_use: Literal["research_only"] = "research_only"
    is_diagnosis: Literal[False] = False
    model: ModelInfo
    source_result_id: str
    issues: list[ValidationIssue] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_consistency(self) -> "HealthRiskOutput":
        if self.status is ResultStatus.INVALID and (self.score is not None or self.category is not None):
            raise ValueError("Kết quả rủi ro INVALID không được mang score hoặc category")
        if self.status is not ResultStatus.INVALID and self.score is None:
            raise ValueError("Kết quả rủi ro OK/BAD bắt buộc có score")
        return self


class HealthRiskModel(Protocol):
    @property
    def model_info(self) -> ModelInfo: ...

    def assess(self, result: VitalsResult, features: Mapping[str, float | None]) -> HealthRiskOutput: ...
