from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np

from aivitals_engine.config.vitals_config import ValidationConfig
from aivitals_engine.contracts.result import IssueSeverity, ResultStatus
from aivitals_engine.validation.candidate import ValidationOutcome

STATUS_ACCEPTED = "ACCEPTED"
STATUS_SUSPICIOUS = "SUSPICIOUS"
STATUS_REJECTED = "REJECTED"

REPORT_STATUS_BY_RESULT: Dict[ResultStatus, str] = {
    ResultStatus.OK: STATUS_ACCEPTED,
    ResultStatus.BAD: STATUS_SUSPICIOUS,
    ResultStatus.INVALID: STATUS_REJECTED,
}

VITAL_NAME_ALIASES: Dict[str, str] = {
    "hr": "heart_rate",
    "heart_rate": "heart_rate",
    "rr": "respiratory_rate",
    "respiration_rate": "respiratory_rate",
    "respiratory_rate": "respiratory_rate",
    "rmssd": "hrv_rmssd",
    "hrv_rmssd": "hrv_rmssd",
    "sdnn": "hrv_sdnn",
    "hrv_sdnn": "hrv_sdnn",
    "mean_ibi": "hrv_mean_ibi",
    "hrv_mean_ibi": "hrv_mean_ibi",
}

HRV_METRIC_KEYS = ("rmssd", "sdnn", "mean_ibi")


@dataclass
class ValidationRuleResult:
    rule_name: str
    passed: bool
    message: str
    severity: str = "WARNING"


@dataclass
class VitalsValidationReport:
    is_valid: bool
    status: str
    results: List[ValidationRuleResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "status": self.status,
            "rule_details": [
                {
                    "rule": r.rule_name,
                    "passed": r.passed,
                    "message": r.message,
                    "severity": r.severity,
                }
                for r in self.results
            ],
        }


def summarize_status(results: List[ValidationRuleResult]) -> str:
    failed = {result.severity for result in results if not result.passed}
    if IssueSeverity.ERROR.value in failed:
        return STATUS_REJECTED
    if IssueSeverity.WARNING.value in failed:
        return STATUS_SUSPICIOUS
    return STATUS_ACCEPTED


def report_from_outcome(outcome: ValidationOutcome) -> VitalsValidationReport:
    results = [
        ValidationRuleResult(rule_name=issue.code, passed=False, message=issue.message, severity=issue.severity.value)
        for issue in outcome.issues
    ]
    status = REPORT_STATUS_BY_RESULT[outcome.status]
    return VitalsValidationReport(is_valid=status != STATUS_REJECTED, status=status, results=results)


class VitalsValidator:
    def __init__(self, max_hr_jump: float = 25.0, config: Optional[ValidationConfig] = None) -> None:
        self.max_hr_jump = max_hr_jump
        self._config = config or ValidationConfig()
        self._last_hr: Optional[float] = None

    def reset(self) -> None:
        self._last_hr = None

    def check_physiological_range(self, vital_name: str, value: float) -> ValidationRuleResult:
        rule_name = f"physiological_range:{vital_name}"
        code = VITAL_NAME_ALIASES.get(vital_name.lower())
        ranges = {key.value: limits for key, limits in self._config.ranges.items()}
        if code is None or code not in ranges:
            return ValidationRuleResult(rule_name, False, f"Không có ngưỡng sinh lý cho '{vital_name}'", "ERROR")
        limits = ranges[code]
        if value is None or not np.isfinite(value):
            return ValidationRuleResult(rule_name, False, f"{vital_name} không có giá trị hợp lệ", "ERROR")
        if not limits.contains(float(value)):
            message = f"{vital_name}={value:.1f} nằm ngoài khoảng [{limits.minimum:g}, {limits.maximum:g}]"
            return ValidationRuleResult(rule_name, False, message, "ERROR")
        return ValidationRuleResult(rule_name, True, f"{vital_name} nằm trong khoảng sinh lý", "INFO")

    def check_sudden_jump(self, current_hr: float) -> ValidationRuleResult:
        previous = self._last_hr
        self._last_hr = float(current_hr)
        if previous is None:
            return ValidationRuleResult("sudden_jump", True, "Chưa có giá trị trước để so sánh", "INFO")
        jump = abs(float(current_hr) - previous)
        if jump > self.max_hr_jump:
            message = f"Nhịp tim thay đổi {jump:.1f} bpm so với lần trước, vượt ngưỡng {self.max_hr_jump:g} bpm"
            return ValidationRuleResult("sudden_jump", False, message, "WARNING")
        return ValidationRuleResult("sudden_jump", True, f"Nhịp tim thay đổi {jump:.1f} bpm", "INFO")

    def check_signal_window(
        self, signal: np.ndarray, min_duration_sec: float = 4.0, fs: float = 30.0
    ) -> ValidationRuleResult:
        samples = np.asarray(signal, dtype=float).ravel()
        if samples.size == 0 or not np.all(np.isfinite(samples)):
            return ValidationRuleResult("signal_window", False, "Tín hiệu rỗng hoặc chứa NaN", "ERROR")
        duration = samples.size / fs
        if duration < min_duration_sec:
            message = f"Cửa sổ tín hiệu {duration:.1f}s ngắn hơn yêu cầu {min_duration_sec:g}s"
            return ValidationRuleResult("signal_window", False, message, "ERROR")
        return ValidationRuleResult("signal_window", True, f"Cửa sổ tín hiệu {duration:.1f}s", "INFO")

    def validate_vitals(
        self,
        hr: Optional[float] = None,
        rr: Optional[float] = None,
        hrv_metrics: Optional[Dict[str, float]] = None,
        bvp_signal: Optional[np.ndarray] = None,
        fs: float = 30.0,
    ) -> VitalsValidationReport:
        results: List[ValidationRuleResult] = []
        if bvp_signal is not None:
            results.append(self.check_signal_window(bvp_signal, fs=fs))
        if hr is not None:
            results.append(self.check_physiological_range("heart_rate", hr))
            results.append(self.check_sudden_jump(hr))
        if rr is not None:
            results.append(self.check_physiological_range("respiratory_rate", rr))
        for key in HRV_METRIC_KEYS:
            value = (hrv_metrics or {}).get(key)
            if value is not None and np.isfinite(value):
                results.append(self.check_physiological_range(key, value))
        status = summarize_status(results)
        return VitalsValidationReport(is_valid=status != STATUS_REJECTED, status=status, results=results)
