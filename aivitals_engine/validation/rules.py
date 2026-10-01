from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from aivitals_engine.config.vitals_config import PhysiologicalRange, ValidationConfig
from aivitals_engine.contracts.result import DetailValue, IssueSeverity, ValidationIssue, VitalCode
from aivitals_engine.validation.candidate import ValidationContext, VitalCandidate
from aivitals_engine.validation.issue_codes import IssueCode

DETAIL_PRECISION = 3


class ValidationRule(Protocol):
    def evaluate(self, candidate: VitalCandidate, context: ValidationContext) -> list[ValidationIssue]: ...


def make_issue(severity: IssueSeverity, code: IssueCode, message: str, **details: DetailValue) -> ValidationIssue:
    rounded = {key: round(value, DETAIL_PRECISION) if isinstance(value, float) else value for key, value in details.items()}
    return ValidationIssue(code=code, severity=severity, message=message, details=rounded)


def warning(code: IssueCode, message: str, **details: DetailValue) -> ValidationIssue:
    return make_issue(IssueSeverity.WARNING, code, message, **details)


def error(code: IssueCode, message: str, **details: DetailValue) -> ValidationIssue:
    return make_issue(IssueSeverity.ERROR, code, message, **details)


class ComputationRule:
    def evaluate(self, candidate: VitalCandidate, context: ValidationContext) -> list[ValidationIssue]:
        if candidate.value is not None:
            return []
        message = "Không tính được chỉ số từ tín hiệu hiện tại"
        return [error(IssueCode.COMPUTATION_FAILED, message, reason=candidate.failure_reason)]


@dataclass(frozen=True)
class WindowDurationRule:
    min_window_seconds: Mapping[VitalCode, float]

    def evaluate(self, candidate: VitalCandidate, context: ValidationContext) -> list[ValidationIssue]:
        required = self.min_window_seconds.get(candidate.code)
        if required is None or candidate.window_duration_seconds >= required:
            return []
        message = "Cửa sổ tín hiệu quá ngắn để tính chỉ số"
        return [
            error(
                IssueCode.WINDOW_TOO_SHORT,
                message,
                required_seconds=required,
                actual_seconds=candidate.window_duration_seconds,
            )
        ]


@dataclass(frozen=True)
class MissingDataRule:
    ok_limit: float
    invalid_limit: float

    def evaluate(self, candidate: VitalCandidate, context: ValidationContext) -> list[ValidationIssue]:
        ratio = candidate.missing_ratio
        if ratio > self.invalid_limit:
            return [error(IssueCode.MISSING_DATA_EXCESSIVE, "Thiếu quá nhiều khung hình trong cửa sổ đo", missing_ratio=ratio)]
        if ratio > self.ok_limit:
            return [warning(IssueCode.MISSING_DATA_HIGH, "Cửa sổ đo bị thiếu một phần khung hình", missing_ratio=ratio)]
        return []


@dataclass(frozen=True)
class SignalQualityRule:
    ok_threshold: float
    invalid_threshold: float

    def evaluate(self, candidate: VitalCandidate, context: ValidationContext) -> list[ValidationIssue]:
        quality = candidate.signal_quality
        if candidate.value is None or quality is None:
            return []
        if quality < self.invalid_threshold:
            return [error(IssueCode.SIGNAL_QUALITY_UNUSABLE, "Chất lượng tín hiệu không đủ để sử dụng", signal_quality=quality)]
        if quality < self.ok_threshold:
            return [warning(IssueCode.SIGNAL_QUALITY_LOW, "Chất lượng tín hiệu thấp", signal_quality=quality)]
        return []


@dataclass(frozen=True)
class PhysiologicalRangeRule:
    ranges: Mapping[VitalCode, PhysiologicalRange]

    def evaluate(self, candidate: VitalCandidate, context: ValidationContext) -> list[ValidationIssue]:
        allowed = self.ranges.get(candidate.code)
        if candidate.value is None or allowed is None or allowed.contains(candidate.value):
            return []
        message = "Giá trị nằm ngoài khoảng sinh lý hợp lý"
        return [
            error(
                IssueCode.OUT_OF_PHYSIOLOGICAL_RANGE,
                message,
                value=candidate.value,
                minimum=allowed.minimum,
                maximum=allowed.maximum,
            )
        ]


@dataclass(frozen=True)
class SuddenJumpRule:
    tolerance: Mapping[VitalCode, float]
    rate_per_second: Mapping[VitalCode, float]

    def evaluate(self, candidate: VitalCandidate, context: ValidationContext) -> list[ValidationIssue]:
        if not self._is_applicable(candidate, context):
            return []
        elapsed = max(0.0, candidate.timestamp - context.previous_timestamp)
        allowed_change = self.tolerance[candidate.code] + self.rate_per_second[candidate.code] * elapsed
        change = abs(candidate.value - context.previous_value)
        if change <= allowed_change:
            return []
        message = "Giá trị thay đổi đột ngột so với lần đo trước"
        return [warning(IssueCode.SUDDEN_JUMP, message, change=change, allowed_change=allowed_change, elapsed_seconds=elapsed)]

    def _is_applicable(self, candidate: VitalCandidate, context: ValidationContext) -> bool:
        return (
            candidate.value is not None
            and context.previous_value is not None
            and context.previous_timestamp is not None
            and candidate.code in self.tolerance
            and candidate.code in self.rate_per_second
        )


@dataclass(frozen=True)
class TemporalStabilityRule:
    std_limit: Mapping[VitalCode, float]
    min_values: int

    def evaluate(self, candidate: VitalCandidate, context: ValidationContext) -> list[ValidationIssue]:
        limit = self.std_limit.get(candidate.code)
        if candidate.value is None or limit is None:
            return []
        values = [*context.recent_values, candidate.value]
        if len(values) < self.min_values:
            return []
        deviation = float(np.std(values))
        if deviation <= limit:
            return []
        return [warning(IssueCode.TEMPORAL_UNSTABLE, "Kết quả dao động mạnh giữa các cửa sổ gần nhất", std=deviation, limit=limit)]


@dataclass(frozen=True)
class CrossRoiConsistencyRule:
    spread_limit: Mapping[VitalCode, float]

    def evaluate(self, candidate: VitalCandidate, context: ValidationContext) -> list[ValidationIssue]:
        limit = self.spread_limit.get(candidate.code)
        if candidate.value is None or limit is None or len(candidate.roi_values) < 2:
            return []
        roi_values = np.array(candidate.roi_values)
        spread = float(np.ptp(roi_values))
        deviation = float(abs(np.median(roi_values) - candidate.value))
        if max(spread, deviation) <= limit:
            return []
        message = "Kết quả giữa các vùng ROI không nhất quán"
        return [warning(IssueCode.CROSS_ROI_INCONSISTENT, message, roi_spread=spread, deviation=deviation, limit=limit)]


@dataclass(frozen=True)
class ConfidenceRule:
    ok_threshold: float
    invalid_threshold: float

    def evaluate(self, candidate: VitalCandidate, context: ValidationContext) -> list[ValidationIssue]:
        if candidate.value is None:
            return []
        confidence = candidate.confidence
        if confidence < self.invalid_threshold:
            return [error(IssueCode.VERY_LOW_CONFIDENCE, "Độ tin cậy quá thấp để trả kết quả", confidence=confidence)]
        if confidence < self.ok_threshold:
            return [warning(IssueCode.LOW_CONFIDENCE, "Độ tin cậy của kết quả thấp", confidence=confidence)]
        return []


def build_default_rules(config: ValidationConfig) -> tuple[ValidationRule, ...]:
    return (
        ComputationRule(),
        WindowDurationRule(config.min_window_seconds),
        MissingDataRule(config.missing_ratio_ok, config.missing_ratio_invalid),
        SignalQualityRule(config.signal_quality_ok, config.signal_quality_invalid),
        PhysiologicalRangeRule(config.ranges),
        SuddenJumpRule(config.jump_tolerance, config.jump_rate_per_second),
        TemporalStabilityRule(config.stability_std_limit, config.min_values_for_stability),
        CrossRoiConsistencyRule(config.cross_roi_spread_limit),
        ConfidenceRule(config.confidence_ok, config.confidence_invalid),
    )
