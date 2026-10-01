import numpy as np
import pytest

from aivitals_engine.quality import (
    FaceObservation,
    FaceQualityAnalyzer,
    FaceQualityIssue,
    InvalidTransitionError,
    MeasurementEvent,
    MeasurementFailure,
    MeasurementState,
    MeasurementStateMachine,
    export_state_contract,
    measure_frame_lighting,
)

analyzer = FaceQualityAnalyzer()


def observations(count=30, luma=130.0, box_width=200.0, jitter=0.0, detection_period=1, seed=0):
    rng = np.random.default_rng(seed)
    items = []
    for index in range(count):
        detected = index % detection_period == 0
        box = (220 + rng.normal(0, jitter), 140 + rng.normal(0, jitter), box_width, box_width) if detected else None
        items.append(FaceObservation(timestamp=index / 30.0, face_box=box, frame_size=(640, 480), mean_luma=luma))
    return items


def test_stable_well_lit_face_is_acceptable():
    report = analyzer.analyze(observations())
    assert report.is_acceptable
    assert report.overall_score == pytest.approx(1.0)


def test_dark_scene_is_flagged():
    report = analyzer.analyze(observations(luma=40.0))
    assert FaceQualityIssue.TOO_DARK in report.issues
    assert report.lighting_score == 0.0


def test_excessive_motion_is_flagged():
    report = analyzer.analyze(observations(jitter=20.0))
    assert FaceQualityIssue.EXCESSIVE_MOTION in report.issues
    assert report.motion_score < 0.5


def test_small_face_and_missing_detection_are_flagged():
    assert FaceQualityIssue.FACE_TOO_SMALL in analyzer.analyze(observations(box_width=50.0)).issues
    assert FaceQualityIssue.FACE_NOT_DETECTED in analyzer.analyze(observations(detection_period=2)).issues


def test_insufficient_observations():
    report = analyzer.analyze(observations(count=3))
    assert report.issues == (FaceQualityIssue.INSUFFICIENT_OBSERVATIONS,)


def test_measure_frame_lighting():
    assert measure_frame_lighting(np.full((10, 10, 3), 128, dtype=np.uint8)) == (pytest.approx(128.0), 0.0)
    assert measure_frame_lighting(np.full((10, 10, 3), 255, dtype=np.uint8))[1] == 1.0


def run_happy_path(machine: MeasurementStateMachine) -> None:
    for event in (
        MeasurementEvent.REQUEST_CAMERA,
        MeasurementEvent.PERMISSION_GRANTED,
        MeasurementEvent.START_MEASUREMENT,
        MeasurementEvent.FACE_FOUND,
        MeasurementEvent.ACQUISITION_STARTED,
        MeasurementEvent.WINDOW_FILLED,
        MeasurementEvent.QUALITY_PASSED,
        MeasurementEvent.RESULT_VALID,
    ):
        machine.dispatch(event)


def test_state_machine_happy_path():
    machine = MeasurementStateMachine()
    run_happy_path(machine)
    assert machine.state is MeasurementState.RESULT_READY
    assert len(machine.history) == 8
    assert machine.dispatch(MeasurementEvent.CONTINUE_MEASUREMENT) is MeasurementState.SIGNAL_ACQUIRING


def test_permission_denied_sets_failure():
    machine = MeasurementStateMachine()
    machine.dispatch(MeasurementEvent.REQUEST_CAMERA)
    assert machine.dispatch(MeasurementEvent.PERMISSION_DENIED) is MeasurementState.FAILED
    assert machine.failure is MeasurementFailure.CAMERA_PERMISSION_DENIED
    assert machine.dispatch(MeasurementEvent.RESET) is MeasurementState.IDLE
    assert machine.failure is None


def test_invalid_transition_raises():
    machine = MeasurementStateMachine()
    with pytest.raises(InvalidTransitionError):
        machine.dispatch(MeasurementEvent.FACE_FOUND)


def test_face_lost_returns_to_search_and_quality_retries_are_limited():
    machine = MeasurementStateMachine(max_quality_retries=1)
    for event in (
        MeasurementEvent.REQUEST_CAMERA,
        MeasurementEvent.PERMISSION_GRANTED,
        MeasurementEvent.START_MEASUREMENT,
        MeasurementEvent.FACE_FOUND,
    ):
        machine.dispatch(event)
    assert machine.dispatch(MeasurementEvent.FACE_LOST) is MeasurementState.FACE_SEARCH
    for event in (MeasurementEvent.FACE_FOUND, MeasurementEvent.ACQUISITION_STARTED, MeasurementEvent.WINDOW_FILLED):
        machine.dispatch(event)
    assert machine.dispatch(MeasurementEvent.QUALITY_FAILED) is MeasurementState.SIGNAL_ACQUIRING
    machine.dispatch(MeasurementEvent.WINDOW_FILLED)
    assert machine.dispatch(MeasurementEvent.QUALITY_FAILED) is MeasurementState.FAILED
    assert machine.failure is MeasurementFailure.SIGNAL_QUALITY_INSUFFICIENT


def test_cancel_and_contract_export():
    machine = MeasurementStateMachine()
    machine.dispatch(MeasurementEvent.REQUEST_CAMERA)
    assert machine.dispatch(MeasurementEvent.CANCEL) is MeasurementState.CANCELLED
    assert MeasurementEvent.RESET in machine.allowed_events()
    contract = export_state_contract()
    assert contract["states"] == [state.value for state in MeasurementState]
    assert {"from": "COMPUTING", "event": "RESULT_VALID", "to": "RESULT_READY"} in contract["transitions"]
    assert len(contract["failures"]) == len(MeasurementFailure)
