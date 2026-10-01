from typing import Any

from aivitals_engine.contracts.result import ResultStatus, VitalCode, VitalsResult, VitalValue

DISCLAIMER = "Kết quả chỉ mang tính tham khảo sức khỏe, không dùng để chẩn đoán hay thay thế thiết bị y tế."

GOOD_QUALITY = 0.7
FAIR_QUALITY = 0.4

FRONTEND_METRICS: dict[VitalCode, tuple[str, str]] = {
    VitalCode.HEART_RATE: ("heart_rate", "bpm"),
    VitalCode.HRV_RMSSD: ("hrv_rmssd", "ms"),
    VitalCode.RESPIRATORY_RATE: ("respiration_rate", "breaths_per_minute"),
}


def quality_label(vital: VitalValue) -> str:
    if vital.status is ResultStatus.INVALID:
        return "REJECTED"
    if vital.quality >= GOOD_QUALITY:
        return "GOOD"
    if vital.quality >= FAIR_QUALITY:
        return "FAIR"
    return "POOR"


def quality_score(vital: VitalValue) -> int:
    return int(round(vital.quality * 100))


def algorithm_version(result: VitalsResult) -> str:
    source = result.source
    return f"{source.rppg_method}-{source.rppg_method_version}+vitals-{result.engine_version}"


def accepted_metrics(result: VitalsResult) -> dict[str, dict[str, Any]]:
    metrics: dict[str, dict[str, Any]] = {}
    for code, (key, unit) in FRONTEND_METRICS.items():
        vital = result.find_vital(code)
        if vital is None or vital.status is ResultStatus.INVALID or vital.value is None:
            continue
        metrics[key] = {"value": vital.value, "unit": unit, "confidence": vital.confidence}
    return metrics


def iso_utc(result: VitalsResult) -> str:
    return result.created_at.isoformat().replace("+00:00", "Z")


def to_measurement_result(result: VitalsResult | None, measurement_id: str) -> dict[str, Any]:
    if result is None:
        return {"measurement_id": measurement_id, "status": "PENDING", "quality": "POOR", "disclaimer": DISCLAIMER}
    heart_rate = result.find_vital(VitalCode.HEART_RATE)
    rejected = heart_rate is None or heart_rate.status is ResultStatus.INVALID
    payload: dict[str, Any] = {
        "measurement_id": measurement_id,
        "status": "REJECTED" if rejected else "READY",
        "quality": "REJECTED" if rejected else quality_label(heart_rate),
        "quality_score": 0 if heart_rate is None else quality_score(heart_rate),
        "measured_at": iso_utc(result),
        "algorithm_version": algorithm_version(result),
        "disclaimer": DISCLAIMER,
    }
    metrics = accepted_metrics(result)
    if metrics:
        payload["metrics"] = metrics
    return payload


def to_measurement_patch(result: VitalsResult) -> dict[str, Any]:
    metrics = accepted_metrics(result)
    heart_rate = result.find_vital(VitalCode.HEART_RATE)
    rejected = heart_rate is None or heart_rate.status is ResultStatus.INVALID
    return {
        "status": "FAILED" if rejected else "COMPLETED",
        "state": "QUALITY_CHECK" if rejected else "RESULT_READY",
        "heart_rate": metrics.get("heart_rate", {}).get("value"),
        "respiration_rate": metrics.get("respiration_rate", {}).get("value"),
        "hrv_rmssd": metrics.get("hrv_rmssd", {}).get("value"),
        "quality_score": None if heart_rate is None else quality_score(heart_rate),
    }


def to_validation_rows(result: VitalsResult) -> list[dict[str, Any]]:
    return [
        {
            "vital": vital.code.value,
            "status": vital.status.value,
            "reason": ", ".join(issue.code for issue in vital.issues) or None,
            "validator_version": result.engine_version,
            "details": {issue.code: issue.message for issue in vital.issues},
        }
        for vital in result.vitals
    ]
