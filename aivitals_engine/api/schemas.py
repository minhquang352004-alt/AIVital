from pydantic import BaseModel, ConfigDict, Field

from aivitals_engine.contracts.bvp_window import BVPWindow
from aivitals_engine.contracts.result import VitalCode, VitalsResult
from aivitals_engine.explanation.payload import ExplanationKind
from aivitals_engine.health.assessment import HealthAssessment
from aivitals_engine.validation.candidate import ValidationContext, VitalCandidate

MAX_SAMPLES = 36_000
MAX_ROI_COUNT = 16
MAX_TREND_RESULTS = 200


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BVPWindowRequest(RequestModel):
    session_id: str = Field(min_length=1, max_length=128)
    samples: list[float] = Field(min_length=8, max_length=MAX_SAMPLES)
    sampling_rate_hz: float = Field(gt=0, le=1000)
    start_timestamp: float = Field(ge=0)
    method: str = Field(min_length=1, max_length=64)
    method_version: str = Field(min_length=1, max_length=32)
    signal_quality: float | None = Field(default=None, ge=0, le=1)
    missing_ratio: float = Field(default=0.0, ge=0, le=1)
    raw_samples: list[float] | None = Field(default=None, max_length=MAX_SAMPLES)
    roi_samples: dict[str, list[float]] = Field(default_factory=dict, max_length=MAX_ROI_COUNT)
    roi_agreement: float | None = Field(default=None, ge=-1, le=1)

    def to_window(self) -> BVPWindow:
        return BVPWindow(
            samples=self.samples,
            sampling_rate_hz=self.sampling_rate_hz,
            start_timestamp=self.start_timestamp,
            method=self.method,
            method_version=self.method_version,
            signal_quality=self.signal_quality,
            missing_ratio=self.missing_ratio,
            raw_samples=self.raw_samples,
            roi_samples=self.roi_samples,
            roi_agreement=self.roi_agreement,
        )


class ValidationCheckRequest(RequestModel):
    code: VitalCode
    value: float | None
    timestamp: float
    confidence: float = Field(ge=0, le=1)
    window_duration_seconds: float = Field(ge=0)
    signal_quality: float | None = Field(default=None, ge=0, le=1)
    missing_ratio: float = Field(default=0.0, ge=0, le=1)
    roi_values: list[float] = Field(default_factory=list, max_length=MAX_ROI_COUNT)
    roi_agreement: float | None = Field(default=None, ge=-1, le=1)
    previous_value: float | None = None
    previous_timestamp: float | None = None
    recent_values: list[float] = Field(default_factory=list, max_length=50)

    def to_candidate(self) -> VitalCandidate:
        return VitalCandidate(
            code=self.code,
            value=self.value,
            timestamp=self.timestamp,
            confidence=self.confidence,
            window_duration_seconds=self.window_duration_seconds,
            signal_quality=self.signal_quality,
            missing_ratio=self.missing_ratio,
            roi_values=tuple(self.roi_values),
            roi_agreement=self.roi_agreement,
        )

    def to_context(self) -> ValidationContext:
        return ValidationContext(
            previous_value=self.previous_value,
            previous_timestamp=self.previous_timestamp,
            recent_values=tuple(self.recent_values),
        )


class ExplanationRequest(RequestModel):
    kind: ExplanationKind
    result: VitalsResult | None = None
    results: list[VitalsResult] = Field(default_factory=list, max_length=MAX_TREND_RESULTS)
    assessment: HealthAssessment | None = None
    question: str | None = Field(default=None, max_length=500)
