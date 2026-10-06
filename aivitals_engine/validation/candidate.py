from dataclasses import dataclass

from aivitals_engine.contracts.result import ResultStatus, ValidationIssue, VitalCode


@dataclass(frozen=True)
class VitalCandidate:
    code: VitalCode
    value: float | None
    timestamp: float
    confidence: float
    window_duration_seconds: float
    signal_quality: float | None = None
    missing_ratio: float = 0.0
    failure_reason: str | None = None
    roi_values: tuple[float, ...] = ()


@dataclass(frozen=True)
class ValidationContext:
    previous_value: float | None = None
    previous_timestamp: float | None = None
    recent_values: tuple[float, ...] = ()


@dataclass(frozen=True)
class ValidationOutcome:
    status: ResultStatus
    issues: tuple[ValidationIssue, ...]

    @property
    def is_accepted(self) -> bool:
        return self.status is not ResultStatus.INVALID

    def issue_codes(self) -> list[str]:
        return [issue.code for issue in self.issues]
