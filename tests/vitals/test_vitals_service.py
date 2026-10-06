import json
from dataclasses import replace

import numpy as np
import pytest

from aivitals_engine.benchmark.synthetic import synthesize_bvp_window
from aivitals_engine.contracts.bvp_window import BVPWindow
from aivitals_engine.contracts.result import ResultStatus, VitalCode, VitalsResult
from aivitals_engine.integration.vitals_service import VitalsService
from aivitals_engine.validation.issue_codes import IssueCode


def test_clean_window_produces_ok_result(clean_window, fixed_clock, fixed_time):
    window, recording = clean_window
    result = VitalsService(clock=fixed_clock).compute(window, "clean")
    end = window.duration_seconds
    heart_rate = result.find_vital(VitalCode.HEART_RATE)
    respiratory = result.find_vital(VitalCode.RESPIRATORY_RATE)
    rmssd = result.find_vital(VitalCode.HRV_RMSSD)
    assert result.status is ResultStatus.OK
    assert result.created_at == fixed_time
    assert heart_rate.value == pytest.approx(recording.reference_heart_rate(end - 10.0, end), abs=2.0)
    assert respiratory.value == pytest.approx(15.0, abs=1.5)
    assert rmssd.value == pytest.approx(recording.reference_rmssd(0.0, end), rel=0.35)
    assert all(0.0 <= vital.confidence <= 1.0 for vital in result.vitals)
    assert {vital.code for vital in result.vitals} == set(VitalCode)


def test_result_serializes_to_schema(clean_window):
    window, _ = clean_window
    result = VitalsService().compute(window, "schema")
    assert VitalsResult.model_validate(json.loads(result.model_dump_json())) == result


def test_unusable_signal_quality_is_rejected():
    rng = np.random.default_rng(3)
    window = BVPWindow(rng.normal(size=900), 30.0, 0.0, "POS", "1.0.0", signal_quality=0.2)
    result = VitalsService().compute(window, "noise")
    heart_rate = result.find_vital(VitalCode.HEART_RATE)
    assert result.status is ResultStatus.INVALID
    assert heart_rate.value is None
    assert IssueCode.SIGNAL_QUALITY_UNUSABLE in [issue.code for issue in heart_rate.issues]


def test_pure_noise_without_sqi_is_not_ok():
    rng = np.random.default_rng(4)
    window = BVPWindow(rng.normal(size=900), 30.0, 0.0, "POS", "1.0.0")
    result = VitalsService().compute(window, "noise")
    assert result.status is not ResultStatus.OK
    assert result.find_vital(VitalCode.HRV_RMSSD).status is ResultStatus.INVALID


def test_sudden_jump_across_windows_is_flagged():
    service = VitalsService()
    first, _ = synthesize_bvp_window(heart_rate_bpm=70.0, seed=1)
    second, _ = synthesize_bvp_window(heart_rate_bpm=110.0, seed=2)
    service.compute(first, "jump")
    result = service.compute(replace(second, start_timestamp=first.start_timestamp + 2.0), "jump")
    heart_rate = result.find_vital(VitalCode.HEART_RATE)
    assert heart_rate.status is ResultStatus.BAD
    assert IssueCode.SUDDEN_JUMP in [issue.code for issue in heart_rate.issues]


def test_short_window_marks_hrv_and_rr_invalid():
    window, _ = synthesize_bvp_window(duration_seconds=12.0, seed=5)
    result = VitalsService().compute(window, "short")
    assert result.find_vital(VitalCode.HEART_RATE).status is ResultStatus.OK
    for code in (VitalCode.HRV_RMSSD, VitalCode.HRV_SDNN, VitalCode.HRV_MEAN_IBI, VitalCode.RESPIRATORY_RATE):
        vital = result.find_vital(code)
        assert vital.status is ResultStatus.INVALID
        assert IssueCode.WINDOW_TOO_SHORT in [issue.code for issue in vital.issues]


def test_session_reset(clean_window):
    window, _ = clean_window
    service = VitalsService()
    service.compute(window, "session-a")
    assert service.active_sessions() == ["session-a"]
    assert service.reset_session("session-a")
    assert not service.reset_session("session-a")
