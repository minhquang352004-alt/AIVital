import math
from dataclasses import replace

import numpy as np
import pytest

import aivitals_engine
from aivitals_engine.benchmark.synthetic import SyntheticScenario, generate_recording
from aivitals_engine.contracts.result import ResultStatus, VitalCode
from aivitals_engine.integration.frontend_mapper import (
    to_measurement_patch,
    to_measurement_result,
    to_validation_rows,
)
from aivitals_engine.integration.realtime_vitals import RealtimeVitalsConfig, RealtimeVitalsEngine
from aivitals_engine.integration.vitals_service import VitalsService
from aivitals_engine.signal_pipeline_realtime import FrameResult
from aivitals_engine.validation.validator import VitalsValidator


class ReplayPipeline:
    def __init__(self, recording, ready_after_sec: float = 8.0, quality_state: str | None = None) -> None:
        self._rgb = np.mean(np.stack(list(recording.roi_rgb.values())), axis=0)
        self._start = float(recording.timestamps[0])
        self._ready_after = ready_after_sec
        self._quality_state = quality_state

    def process_frame(self, frame_index, timestamp):
        ready = timestamp - self._start >= self._ready_after
        result = FrameResult(
            is_ready=ready,
            status="OK" if ready else "BUFFERING",
            bvp_signal=np.zeros(10) if ready else None,
            quality_sqi=0.82,
            raw_rgb=self._rgb[frame_index],
            method_name="POS",
            method_version="1.0",
        )
        if self._quality_state is not None:
            result.quality_state = self._quality_state
        return result

    def reset(self) -> None:
        pass


@pytest.fixture(scope="module")
def recording():
    return generate_recording(SyntheticScenario(heart_rate_bpm=72.0, respiratory_rate_brpm=15.0, duration_seconds=40.0, seed=5))


def replay(engine, recording):
    updates = [engine.process_frame(index, float(ts)) for index, ts in enumerate(recording.timestamps)]
    return [update for update in updates if update.has_new_vitals]


def test_legacy_functions_return_real_values(clean_window):
    window, _ = clean_window
    fs = window.sampling_rate_hz
    assert aivitals_engine.calculate_fft_hr(window.samples, fs) == pytest.approx(72.0, abs=2.0)
    hrv = aivitals_engine.calculate_hrv_from_bvp(window.samples, fs)
    assert set(hrv) == {"sdnn", "rmssd", "pnn50", "mean_ibi"}
    assert hrv["mean_ibi"] == pytest.approx(60000.0 / 72.0, rel=0.05)
    rr = aivitals_engine.calculate_respiration_rate(window.samples, fs, raw_signal=window.raw_samples)
    assert rr == pytest.approx(15.0, abs=1.5)


def test_legacy_hrv_handles_short_signal():
    hrv = aivitals_engine.calculate_hrv_from_bvp(np.zeros(20), 30.0)
    assert all(math.isnan(value) for value in hrv.values())
    assert aivitals_engine.calculate_respiration_rate(np.zeros(60), 30.0) == 0.0


def test_vitals_validator_statuses():
    validator = VitalsValidator(max_hr_jump=20.0)
    accepted = validator.validate_vitals(hr=72.0, rr=15.0, hrv_metrics={"rmssd": 40.0}, bvp_signal=np.ones(300))
    assert accepted.status == "ACCEPTED" and accepted.is_valid
    suspicious = validator.validate_vitals(hr=110.0)
    assert suspicious.status == "SUSPICIOUS"
    rejected = validator.validate_vitals(hr=250.0, bvp_signal=np.ones(30))
    assert rejected.status == "REJECTED" and not rejected.is_valid
    assert {detail["rule"] for detail in rejected.to_dict()["rule_details"]} >= {"signal_window", "physiological_range:heart_rate"}


def test_unknown_vital_name_is_rejected():
    result = VitalsValidator().check_physiological_range("spo2", 98.0)
    assert not result.passed and result.severity == "ERROR"


def test_frontend_result_matches_quang_contract(clean_window, fixed_clock):
    window, _ = clean_window
    result = VitalsService(clock=fixed_clock).compute(window, "measurement-1")
    payload = to_measurement_result(result, "measurement-1")
    assert payload["status"] == "READY"
    assert payload["quality"] in {"GOOD", "FAIR", "POOR"}
    assert 0 <= payload["quality_score"] <= 100
    assert payload["measured_at"] == "2026-01-01T08:00:00Z"
    assert set(payload["metrics"]) == {"heart_rate", "hrv_rmssd", "respiration_rate"}
    assert payload["metrics"]["respiration_rate"]["unit"] == "breaths_per_minute"
    assert 0.0 <= payload["metrics"]["heart_rate"]["confidence"] <= 1.0
    patch = to_measurement_patch(result)
    assert patch["status"] == "COMPLETED" and patch["state"] == "RESULT_READY"
    assert patch["heart_rate"] == payload["metrics"]["heart_rate"]["value"]
    assert {row["status"] for row in to_validation_rows(result)} <= {"OK", "BAD", "INVALID"}


def test_frontend_result_pending_and_rejected(clean_window):
    assert to_measurement_result(None, "m")["status"] == "PENDING"
    window, _ = clean_window
    result = VitalsService().compute(replace(window, signal_quality=0.1), "low-quality")
    assert result.find_vital(VitalCode.HEART_RATE).status is ResultStatus.INVALID
    payload = to_measurement_result(result, "m")
    assert payload["status"] == "REJECTED" and payload["quality"] == "REJECTED"
    assert "heart_rate" not in payload.get("metrics", {})
    patch = to_measurement_patch(result)
    assert patch["heart_rate"] is None
    assert patch["status"] == "FAILED" and patch["state"] == "QUALITY_CHECK"


def test_realtime_engine_uses_long_window_for_hrv_and_rr(recording):
    engine = RealtimeVitalsEngine("rt", pipeline=ReplayPipeline(recording), config=RealtimeVitalsConfig(update_interval_sec=2.0))
    updates = replay(engine, recording)
    assert updates
    first, last = updates[0], updates[-1]
    assert first.window_seconds == pytest.approx(8.0, abs=0.2)
    assert first.vitals.find_vital(VitalCode.HRV_RMSSD).status is ResultStatus.INVALID
    assert last.window_seconds >= 30.0
    heart_rate = last.vitals.find_vital(VitalCode.HEART_RATE)
    assert heart_rate.value == pytest.approx(72.0, abs=3.0)
    respiratory = last.vitals.find_vital(VitalCode.RESPIRATORY_RATE)
    assert respiratory.status is not ResultStatus.INVALID
    assert respiratory.value == pytest.approx(15.0, abs=2.0)
    assert last.vitals.source.rppg_method == "POS"
    assert engine.latest_measurement_result("rt")["status"] == "READY"


def test_realtime_engine_respects_quality_gate(recording):
    engine = RealtimeVitalsEngine("gate", pipeline=ReplayPipeline(recording, quality_state="REJECTED"))
    assert replay(engine, recording) == []
    assert engine.latest_measurement_result("gate")["status"] == "PENDING"


def test_realtime_engine_reset(recording):
    engine = RealtimeVitalsEngine("reset", pipeline=ReplayPipeline(recording))
    replay(engine, recording)
    assert engine.latest_result is not None
    engine.reset()
    assert engine.latest_result is None
    assert engine.missing_ratio() == 0.0
