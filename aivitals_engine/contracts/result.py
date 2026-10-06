from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

RESULT_SCHEMA_VERSION = "1.0.0"


class VitalCode(StrEnum):
    HEART_RATE = "heart_rate"
    HRV_RMSSD = "hrv_rmssd"
    HRV_SDNN = "hrv_sdnn"
    HRV_MEAN_IBI = "hrv_mean_ibi"
    RESPIRATORY_RATE = "respiratory_rate"


VITAL_UNITS: dict[VitalCode, str] = {
    VitalCode.HEART_RATE: "bpm",
    VitalCode.HRV_RMSSD: "ms",
    VitalCode.HRV_SDNN: "ms",
    VitalCode.HRV_MEAN_IBI: "ms",
    VitalCode.RESPIRATORY_RATE: "brpm",
}


class ResultStatus(StrEnum):
    OK = "OK"
    BAD = "BAD"
    INVALID = "INVALID"


class IssueSeverity(StrEnum):
    WARNING = "WARNING"
    ERROR = "ERROR"


DetailValue = float | int | str | bool | None


class ContractModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ValidationIssue(ContractModel):
    code: str = Field(min_length=1)
    severity: IssueSeverity
    message: str
    details: dict[str, DetailValue] = Field(default_factory=dict)


class AlgorithmInfo(ContractModel):
    name: str = Field(min_length=1)
    version: str = Field(min_length=1)


class ModelInfo(ContractModel):
    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    checksum_sha256: str | None = Field(default=None, pattern="^[a-f0-9]{64}$")


class MeasurementWindow(ContractModel):
    start: datetime
    end: datetime
    duration_seconds: float = Field(ge=0)


class VitalValue(ContractModel):
    code: VitalCode
    value: float | None
    unit: str
    timestamp: datetime
    window: MeasurementWindow
    quality: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    status: ResultStatus
    issues: list[ValidationIssue] = Field(default_factory=list)
    algorithm: AlgorithmInfo
    model: ModelInfo | None = None

    @model_validator(mode="after")
    def check_consistency(self) -> "VitalValue":
        if self.unit != VITAL_UNITS[self.code]:
            raise ValueError(f"Đơn vị của {self.code} phải là {VITAL_UNITS[self.code]}")
        if self.status is ResultStatus.INVALID and self.value is not None:
            raise ValueError("Kết quả INVALID không được mang giá trị")
        if self.status is not ResultStatus.INVALID and self.value is None:
            raise ValueError("Kết quả OK/BAD bắt buộc có giá trị")
        return self


class SignalSource(ContractModel):
    rppg_method: str = Field(min_length=1)
    rppg_method_version: str = Field(min_length=1)
    sampling_rate_hz: float = Field(gt=0)
    signal_quality: float | None = Field(default=None, ge=0, le=1)
    missing_ratio: float = Field(ge=0, le=1)


class VitalsResult(ContractModel):
    schema_version: Literal["1.0.0"] = RESULT_SCHEMA_VERSION
    result_id: str = Field(default_factory=lambda: str(uuid4()))
    session_id: str = Field(min_length=1)
    engine_version: str = Field(min_length=1)
    created_at: datetime
    source: SignalSource
    window: MeasurementWindow
    status: ResultStatus
    vitals: list[VitalValue]
    issues: list[ValidationIssue] = Field(default_factory=list)

    def find_vital(self, code: VitalCode) -> VitalValue | None:
        return next((vital for vital in self.vitals if vital.code is code), None)

    def accepted_vitals(self) -> list[VitalValue]:
        return [vital for vital in self.vitals if vital.status is ResultStatus.OK]
