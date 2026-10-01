from collections.abc import Sequence
from datetime import UTC, datetime

from aivitals_engine.contracts.bvp_window import BVPWindow
from aivitals_engine.contracts.result import (
    VITAL_UNITS,
    AlgorithmInfo,
    MeasurementWindow,
    ModelInfo,
    ResultStatus,
    SignalSource,
    VitalCode,
    VitalsResult,
    VitalValue,
)
from aivitals_engine.validation.candidate import ValidationOutcome, VitalCandidate
from aivitals_engine.version import ENGINE_VERSION

VALUE_DECIMALS = 1
SCORE_DECIMALS = 3


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def to_datetime(timestamp: float) -> datetime:
    return datetime.fromtimestamp(timestamp, tz=UTC)


def build_measurement_window(start_timestamp: float, end_timestamp: float) -> MeasurementWindow:
    return MeasurementWindow(
        start=to_datetime(start_timestamp),
        end=to_datetime(end_timestamp),
        duration_seconds=round(max(0.0, end_timestamp - start_timestamp), SCORE_DECIMALS),
    )


def clip_score(value: float) -> float:
    return round(min(1.0, max(0.0, value)), SCORE_DECIMALS)


def build_vital_value(
    candidate: VitalCandidate,
    outcome: ValidationOutcome,
    reported_value: float | None,
    quality: float,
    window: MeasurementWindow,
    algorithm: AlgorithmInfo,
    model: ModelInfo | None = None,
) -> VitalValue:
    is_invalid = outcome.status is ResultStatus.INVALID or reported_value is None
    return VitalValue(
        code=candidate.code,
        value=None if is_invalid else round(reported_value, VALUE_DECIMALS),
        unit=VITAL_UNITS[candidate.code],
        timestamp=to_datetime(candidate.timestamp),
        window=window,
        quality=clip_score(quality),
        confidence=clip_score(candidate.confidence),
        status=ResultStatus.INVALID if is_invalid else outcome.status,
        issues=list(outcome.issues),
        algorithm=algorithm,
        model=model,
    )


def build_signal_source(window: BVPWindow) -> SignalSource:
    return SignalSource(
        rppg_method=window.method,
        rppg_method_version=window.method_version,
        sampling_rate_hz=window.sampling_rate_hz,
        signal_quality=window.signal_quality,
        missing_ratio=window.missing_ratio,
    )


def build_vitals_result(
    session_id: str, window: BVPWindow, vitals: Sequence[VitalValue], created_at: datetime
) -> VitalsResult:
    heart_rate = next(vital for vital in vitals if vital.code is VitalCode.HEART_RATE)
    return VitalsResult(
        session_id=session_id,
        engine_version=ENGINE_VERSION,
        created_at=created_at,
        source=build_signal_source(window),
        window=build_measurement_window(window.start_timestamp, window.end_timestamp),
        status=heart_rate.status,
        vitals=list(vitals),
        issues=list(heart_rate.issues),
    )
