from datetime import UTC, datetime, timedelta

import pytest

from aivitals_engine.benchmark.synthetic import synthesize_bvp_window
from aivitals_engine.contracts.result import (
    VITAL_UNITS,
    AlgorithmInfo,
    IssueSeverity,
    MeasurementWindow,
    ResultStatus,
    SignalSource,
    ValidationIssue,
    VitalCode,
    VitalsResult,
    VitalValue,
)
from aivitals_engine.explanation.llm_client import LLMCompletion
from aivitals_engine.version import ENGINE_VERSION

FIXED_TIME = datetime(2026, 1, 1, 8, 0, tzinfo=UTC)
TEST_ALGORITHM = AlgorithmInfo(name="test_algorithm", version="1.0.0")


class FakeLLM:
    def __init__(self, text: str) -> None:
        self.text = text
        self.calls: list[tuple[str, str]] = []

    def complete(self, system_prompt: str, user_prompt: str) -> LLMCompletion:
        self.calls.append((system_prompt, user_prompt))
        return LLMCompletion(text=self.text, model="fake-model")


def build_vital(code: VitalCode, value: float, status: ResultStatus, created_at: datetime) -> VitalValue:
    window = MeasurementWindow(start=created_at - timedelta(seconds=30), end=created_at, duration_seconds=30.0)
    severity = IssueSeverity.ERROR if status is ResultStatus.INVALID else IssueSeverity.WARNING
    issues = [] if status is ResultStatus.OK else [ValidationIssue(code="LOW_CONFIDENCE", severity=severity, message="test")]
    is_invalid = status is ResultStatus.INVALID
    return VitalValue(
        code=code,
        value=None if is_invalid else value,
        unit=VITAL_UNITS[code],
        timestamp=created_at,
        window=window,
        quality=0.8,
        confidence=0.0 if is_invalid else 0.9,
        status=status,
        issues=issues,
        algorithm=TEST_ALGORITHM,
    )


def build_result(
    values: dict[VitalCode, tuple[float, ResultStatus]],
    created_at: datetime = FIXED_TIME,
    session_id: str = "session-test",
) -> VitalsResult:
    values = dict(values)
    values.setdefault(VitalCode.HEART_RATE, (0.0, ResultStatus.INVALID))
    vitals = [build_vital(code, value, status, created_at) for code, (value, status) in values.items()]
    heart_rate = next(vital for vital in vitals if vital.code is VitalCode.HEART_RATE)
    return VitalsResult(
        session_id=session_id,
        engine_version=ENGINE_VERSION,
        created_at=created_at,
        source=SignalSource(rppg_method="POS", rppg_method_version="1.0.0", sampling_rate_hz=30.0, missing_ratio=0.0),
        window=MeasurementWindow(start=created_at - timedelta(seconds=30), end=created_at, duration_seconds=30.0),
        status=heart_rate.status,
        vitals=vitals,
        issues=list(heart_rate.issues),
    )


@pytest.fixture
def fixed_time():
    return FIXED_TIME


@pytest.fixture
def fixed_clock():
    return lambda: FIXED_TIME


@pytest.fixture
def make_result():
    return build_result


@pytest.fixture
def make_vital():
    return build_vital


@pytest.fixture
def fake_llm():
    return FakeLLM


@pytest.fixture(scope="session")
def clean_window():
    return synthesize_bvp_window(heart_rate_bpm=72.0, respiratory_rate_brpm=15.0, noise_std=0.1, seed=11)
