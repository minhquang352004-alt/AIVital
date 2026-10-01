from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class MeasurementState(StrEnum):
    IDLE = "IDLE"
    CAMERA_PERMISSION = "CAMERA_PERMISSION"
    CAMERA_READY = "CAMERA_READY"
    FACE_SEARCH = "FACE_SEARCH"
    FACE_LOCKED = "FACE_LOCKED"
    SIGNAL_ACQUIRING = "SIGNAL_ACQUIRING"
    QUALITY_CHECK = "QUALITY_CHECK"
    COMPUTING = "COMPUTING"
    RESULT_READY = "RESULT_READY"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class MeasurementEvent(StrEnum):
    REQUEST_CAMERA = "REQUEST_CAMERA"
    PERMISSION_GRANTED = "PERMISSION_GRANTED"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    CAMERA_ERROR = "CAMERA_ERROR"
    START_MEASUREMENT = "START_MEASUREMENT"
    FACE_FOUND = "FACE_FOUND"
    FACE_LOST = "FACE_LOST"
    FACE_SEARCH_TIMEOUT = "FACE_SEARCH_TIMEOUT"
    ACQUISITION_STARTED = "ACQUISITION_STARTED"
    WINDOW_FILLED = "WINDOW_FILLED"
    QUALITY_PASSED = "QUALITY_PASSED"
    QUALITY_FAILED = "QUALITY_FAILED"
    RESULT_VALID = "RESULT_VALID"
    RESULT_INVALID = "RESULT_INVALID"
    CONTINUE_MEASUREMENT = "CONTINUE_MEASUREMENT"
    CANCEL = "CANCEL"
    RESET = "RESET"


class MeasurementFailure(StrEnum):
    CAMERA_PERMISSION_DENIED = "CAMERA_PERMISSION_DENIED"
    CAMERA_UNAVAILABLE = "CAMERA_UNAVAILABLE"
    FACE_NOT_FOUND = "FACE_NOT_FOUND"
    SIGNAL_QUALITY_INSUFFICIENT = "SIGNAL_QUALITY_INSUFFICIENT"
    MEASUREMENT_INVALID = "MEASUREMENT_INVALID"


FAILURE_MESSAGES: dict[MeasurementFailure, str] = {
    MeasurementFailure.CAMERA_PERMISSION_DENIED: "Bạn chưa cấp quyền camera. Hãy cho phép camera để bắt đầu đo.",
    MeasurementFailure.CAMERA_UNAVAILABLE: "Không mở được camera. Hãy kiểm tra thiết bị hoặc ứng dụng khác đang dùng camera.",
    MeasurementFailure.FACE_NOT_FOUND: "Không tìm thấy khuôn mặt. Hãy nhìn thẳng vào camera và giữ mặt trong khung.",
    MeasurementFailure.SIGNAL_QUALITY_INSUFFICIENT: "Tín hiệu chưa đủ tốt. Hãy ngồi yên và đo ở nơi đủ sáng.",
    MeasurementFailure.MEASUREMENT_INVALID: "Kết quả đo không hợp lệ. Hãy thử đo lại.",
}

TERMINAL_STATES = frozenset({MeasurementState.RESULT_READY, MeasurementState.FAILED, MeasurementState.CANCELLED})
ACTIVE_FACE_STATES = (MeasurementState.FACE_LOCKED, MeasurementState.SIGNAL_ACQUIRING, MeasurementState.QUALITY_CHECK)

TRANSITIONS: dict[tuple[MeasurementState, MeasurementEvent], MeasurementState] = {
    (MeasurementState.IDLE, MeasurementEvent.REQUEST_CAMERA): MeasurementState.CAMERA_PERMISSION,
    (MeasurementState.CAMERA_PERMISSION, MeasurementEvent.PERMISSION_GRANTED): MeasurementState.CAMERA_READY,
    (MeasurementState.CAMERA_PERMISSION, MeasurementEvent.PERMISSION_DENIED): MeasurementState.FAILED,
    (MeasurementState.CAMERA_READY, MeasurementEvent.START_MEASUREMENT): MeasurementState.FACE_SEARCH,
    (MeasurementState.FACE_SEARCH, MeasurementEvent.FACE_FOUND): MeasurementState.FACE_LOCKED,
    (MeasurementState.FACE_SEARCH, MeasurementEvent.FACE_SEARCH_TIMEOUT): MeasurementState.FAILED,
    (MeasurementState.FACE_LOCKED, MeasurementEvent.ACQUISITION_STARTED): MeasurementState.SIGNAL_ACQUIRING,
    (MeasurementState.SIGNAL_ACQUIRING, MeasurementEvent.WINDOW_FILLED): MeasurementState.QUALITY_CHECK,
    (MeasurementState.QUALITY_CHECK, MeasurementEvent.QUALITY_PASSED): MeasurementState.COMPUTING,
    (MeasurementState.QUALITY_CHECK, MeasurementEvent.QUALITY_FAILED): MeasurementState.SIGNAL_ACQUIRING,
    (MeasurementState.COMPUTING, MeasurementEvent.RESULT_VALID): MeasurementState.RESULT_READY,
    (MeasurementState.COMPUTING, MeasurementEvent.RESULT_INVALID): MeasurementState.FAILED,
    (MeasurementState.RESULT_READY, MeasurementEvent.CONTINUE_MEASUREMENT): MeasurementState.SIGNAL_ACQUIRING,
    **{(state, MeasurementEvent.FACE_LOST): MeasurementState.FACE_SEARCH for state in ACTIVE_FACE_STATES},
    **{
        (state, MeasurementEvent.CAMERA_ERROR): MeasurementState.FAILED
        for state in MeasurementState
        if state not in TERMINAL_STATES and state is not MeasurementState.IDLE
    },
    **{(state, MeasurementEvent.CANCEL): MeasurementState.CANCELLED for state in MeasurementState if state not in TERMINAL_STATES},
    **{(state, MeasurementEvent.RESET): MeasurementState.IDLE for state in TERMINAL_STATES},
}

FAILURE_BY_EVENT: dict[MeasurementEvent, MeasurementFailure] = {
    MeasurementEvent.PERMISSION_DENIED: MeasurementFailure.CAMERA_PERMISSION_DENIED,
    MeasurementEvent.CAMERA_ERROR: MeasurementFailure.CAMERA_UNAVAILABLE,
    MeasurementEvent.FACE_SEARCH_TIMEOUT: MeasurementFailure.FACE_NOT_FOUND,
    MeasurementEvent.QUALITY_FAILED: MeasurementFailure.SIGNAL_QUALITY_INSUFFICIENT,
    MeasurementEvent.RESULT_INVALID: MeasurementFailure.MEASUREMENT_INVALID,
}


FRONTEND_ONLY_STATES = frozenset({MeasurementState.FAILED, MeasurementState.CANCELLED})
DATABASE_STATUS_BY_STATE: dict[MeasurementState, str] = {
    MeasurementState.IDLE: "CREATED",
    MeasurementState.RESULT_READY: "COMPLETED",
    MeasurementState.FAILED: "FAILED",
    MeasurementState.CANCELLED: "STOPPED",
}
DEFAULT_DATABASE_STATUS = "RUNNING"


def database_mapping(state: MeasurementState) -> dict[str, str | None]:
    return {
        "state": state.value,
        "measurements_state": None if state in FRONTEND_ONLY_STATES else state.value,
        "measurements_status": DATABASE_STATUS_BY_STATE.get(state, DEFAULT_DATABASE_STATUS),
    }

class InvalidTransitionError(ValueError):
    def __init__(self, state: MeasurementState, event: MeasurementEvent) -> None:
        super().__init__(f"Không thể xử lý sự kiện {event} khi đang ở trạng thái {state}")
        self.state = state
        self.event = event


@dataclass(frozen=True)
class TransitionRecord:
    source: MeasurementState
    event: MeasurementEvent
    target: MeasurementState


@dataclass
class MeasurementStateMachine:
    max_quality_retries: int = 3
    state: MeasurementState = MeasurementState.IDLE
    failure: MeasurementFailure | None = None
    quality_retries: int = 0
    history: list[TransitionRecord] = field(default_factory=list)

    def allowed_events(self) -> list[MeasurementEvent]:
        return [event for (state, event) in TRANSITIONS if state is self.state]

    def dispatch(self, event: MeasurementEvent) -> MeasurementState:
        target = TRANSITIONS.get((self.state, event))
        if target is None:
            raise InvalidTransitionError(self.state, event)
        target = self._apply_retry_policy(event, target)
        self._record(event, target)
        return self.state

    def _apply_retry_policy(self, event: MeasurementEvent, target: MeasurementState) -> MeasurementState:
        if event is not MeasurementEvent.QUALITY_FAILED:
            return target
        self.quality_retries += 1
        return MeasurementState.FAILED if self.quality_retries > self.max_quality_retries else target

    def _record(self, event: MeasurementEvent, target: MeasurementState) -> None:
        self.history.append(TransitionRecord(self.state, event, target))
        self.state = target
        if target is MeasurementState.FAILED:
            self.failure = FAILURE_BY_EVENT.get(event)
        if target is MeasurementState.IDLE:
            self.failure = None
            self.quality_retries = 0


def export_state_contract() -> dict[str, Any]:
    return {
        "states": [state.value for state in MeasurementState],
        "events": [event.value for event in MeasurementEvent],
        "terminal_states": sorted(state.value for state in TERMINAL_STATES),
        "transitions": [
            {"from": source.value, "event": event.value, "to": target.value}
            for (source, event), target in sorted(TRANSITIONS.items())
        ],
        "failures": [
            {"code": failure.value, "message": FAILURE_MESSAGES[failure]} for failure in MeasurementFailure
        ],
        "failure_by_event": {event.value: failure.value for event, failure in FAILURE_BY_EVENT.items()},
        "database_mapping": [database_mapping(state) for state in MeasurementState],
    }
