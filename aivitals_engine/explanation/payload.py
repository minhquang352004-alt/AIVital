import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import numpy as np

from aivitals_engine.contracts.result import ResultStatus, VitalCode, VitalsResult, VitalValue
from aivitals_engine.health.assessment import HealthAssessment

VALUE_DECIMALS = 1
MIN_RESULTS_FOR_TREND = 2
NUMBER_PATTERN = re.compile(r"\d+(?:[.,]\d+)?")


class ExplanationKind(StrEnum):
    REPORT = "report"
    QUESTION = "question"
    TREND_SUMMARY = "trend_summary"


class ResultNotValidatedError(ValueError):
    pass


@dataclass(frozen=True)
class ExplanationPayload:
    data: dict[str, Any]
    allowed_numbers: tuple[float, ...]
    source_result_ids: tuple[str, ...]


def extract_numbers(text: str) -> list[float]:
    return [float(match.replace(",", ".")) for match in NUMBER_PATTERN.findall(text)]


def vital_entry(vital: VitalValue) -> dict[str, Any]:
    return {
        "metric": vital.code.value,
        "value": round(vital.value, VALUE_DECIMALS),
        "unit": vital.unit,
        "confidence": vital.confidence,
        "measured_at": vital.timestamp.isoformat(),
    }


def ensure_validated(result: VitalsResult) -> list[VitalValue]:
    accepted = result.accepted_vitals()
    if result.status is ResultStatus.INVALID or not accepted:
        raise ResultNotValidatedError("Chỉ được gửi kết quả đã validate và có ít nhất một chỉ số OK sang tầng giải thích")
    return accepted


def build_result_payload(result: VitalsResult, assessment: HealthAssessment | None = None) -> ExplanationPayload:
    accepted = ensure_validated(result)
    if assessment is not None and assessment.source_result_id != result.result_id:
        raise ValueError("Health assessment không thuộc về kết quả đo này")
    data: dict[str, Any] = {
        "result_id": result.result_id,
        "measured_at": result.window.end.isoformat(),
        "vitals": [vital_entry(vital) for vital in accepted],
        "unavailable_metrics": [vital.code.value for vital in result.vitals if vital.status is not ResultStatus.OK],
    }
    if assessment is not None:
        data["findings"] = [
            {
                "code": finding.code,
                "metric": finding.metric.value,
                "evidence_level": finding.evidence_level.value,
                "interpretation": finding.interpretation,
                "caution": finding.caution,
            }
            for finding in assessment.findings
        ]
        data["disclaimer"] = assessment.disclaimer
    allowed = [round(vital.value, VALUE_DECIMALS) for vital in accepted]
    if assessment is not None:
        allowed += [number for finding in assessment.findings for number in extract_numbers(finding.interpretation + " " + finding.caution)]
    return ExplanationPayload(data=data, allowed_numbers=tuple(allowed), source_result_ids=(result.result_id,))


def metric_trend(code: VitalCode, results: Sequence[VitalsResult]) -> dict[str, Any] | None:
    values = [vital.value for result in results for vital in result.accepted_vitals() if vital.code is code]
    if len(values) < MIN_RESULTS_FOR_TREND:
        return None
    return {
        "metric": code.value,
        "count": len(values),
        "first": round(values[0], VALUE_DECIMALS),
        "last": round(values[-1], VALUE_DECIMALS),
        "mean": round(float(np.mean(values)), VALUE_DECIMALS),
        "min": round(float(np.min(values)), VALUE_DECIMALS),
        "max": round(float(np.max(values)), VALUE_DECIMALS),
    }


def build_trend_payload(results: Sequence[VitalsResult]) -> ExplanationPayload:
    ordered = sorted((result for result in results if result.status is not ResultStatus.INVALID), key=lambda item: item.created_at)
    trends = [trend for code in VitalCode if (trend := metric_trend(code, ordered)) is not None]
    if not trends:
        raise ResultNotValidatedError("Cần tối thiểu 2 kết quả đã validate cho cùng một chỉ số để tóm tắt xu hướng")
    allowed = tuple(float(trend[key]) for trend in trends for key in ("first", "last", "mean", "min", "max"))
    data = {
        "period_start": ordered[0].created_at.isoformat(),
        "period_end": ordered[-1].created_at.isoformat(),
        "trends": trends,
    }
    return ExplanationPayload(data=data, allowed_numbers=allowed, source_result_ids=tuple(result.result_id for result in ordered))
