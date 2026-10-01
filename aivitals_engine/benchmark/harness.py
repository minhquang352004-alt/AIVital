from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from time import perf_counter
from typing import Protocol

from aivitals_engine.benchmark.dataset import BenchmarkRecording
from aivitals_engine.benchmark.report import BenchmarkReport, WindowRecord
from aivitals_engine.config.vitals_config import VitalsConfig
from aivitals_engine.contracts.bvp_window import BVPWindow
from aivitals_engine.contracts.frame import FramePacket
from aivitals_engine.contracts.result import VitalCode, VitalsResult
from aivitals_engine.integration.vitals_service import VitalsService

TIME_EPSILON = 1e-6


class StreamingSignalSource(Protocol):
    name: str
    version: str

    def reset(self) -> None: ...

    def update(self, frame: FramePacket) -> None: ...

    def get_signal(self) -> BVPWindow | None: ...


MethodFactory = Callable[[], StreamingSignalSource]


@dataclass(frozen=True)
class BenchmarkConfig:
    window_seconds: float = 30.0
    step_seconds: float = 2.0
    hr_tolerance_bpm: float = 5.0
    rmssd_tolerance_ms: float = 15.0
    rr_tolerance_brpm: float = 3.0


class BenchmarkRunner:
    def __init__(
        self,
        method_factories: Mapping[str, MethodFactory],
        config: BenchmarkConfig | None = None,
        vitals_config: VitalsConfig | None = None,
    ) -> None:
        if not method_factories:
            raise ValueError("Cần ít nhất một method để benchmark")
        self._factories = dict(method_factories)
        self._config = config or BenchmarkConfig()
        self._vitals_config = vitals_config or VitalsConfig()

    def run(self, recordings: Sequence[BenchmarkRecording]) -> BenchmarkReport:
        started = perf_counter()
        records = [
            record
            for factory in self._factories.values()
            for recording in recordings
            for record in self._run_recording(factory, recording)
        ]
        return BenchmarkReport.from_records(records, self._config, perf_counter() - started)

    def _run_recording(self, factory: MethodFactory, recording: BenchmarkRecording) -> list[WindowRecord]:
        method = factory()
        method.reset()
        service = VitalsService(self._vitals_config)
        session_id = f"{method.name}:{recording.recording_id}"
        start_time = float(recording.timestamps[0])
        next_evaluation = start_time + self._config.window_seconds
        update_ms = 0.0
        records = []
        for frame in recording.frames():
            started = perf_counter()
            method.update(frame)
            update_ms += (perf_counter() - started) * 1000.0
            if frame.timestamp + TIME_EPSILON < next_evaluation:
                continue
            next_evaluation += self._config.step_seconds
            record = self._evaluate(method, service, session_id, recording, frame.timestamp - start_time, update_ms)
            update_ms = 0.0
            if record is not None:
                records.append(record)
        return records

    def _evaluate(
        self,
        method: StreamingSignalSource,
        service: VitalsService,
        session_id: str,
        recording: BenchmarkRecording,
        end_s: float,
        update_ms: float,
    ) -> WindowRecord | None:
        started = perf_counter()
        window = method.get_signal()
        signal_ms = update_ms + (perf_counter() - started) * 1000.0
        if window is None:
            return None
        started = perf_counter()
        result = service.compute(window, session_id)
        vitals_ms = (perf_counter() - started) * 1000.0
        return build_window_record(method, recording, result, end_s, window.duration_seconds, signal_ms, vitals_ms)


def build_window_record(
    method: StreamingSignalSource,
    recording: BenchmarkRecording,
    result: VitalsResult,
    end_s: float,
    window_duration_s: float,
    signal_ms: float,
    vitals_ms: float,
) -> WindowRecord:
    heart_rate = result.find_vital(VitalCode.HEART_RATE)
    rmssd = result.find_vital(VitalCode.HRV_RMSSD)
    respiratory = result.find_vital(VitalCode.RESPIRATORY_RATE)
    window_start_s = end_s - window_duration_s
    return WindowRecord(
        method=method.name,
        method_version=method.version,
        recording_id=recording.recording_id,
        subject_id=recording.subject_id,
        scenario=recording.scenario,
        window_end_s=round(end_s, 3),
        reference_hr_bpm=recording.reference_heart_rate(end_s - heart_rate.window.duration_seconds, end_s),
        estimated_hr_bpm=heart_rate.value,
        hr_status=heart_rate.status.value,
        hr_confidence=heart_rate.confidence,
        hr_issue_codes=tuple(issue.code for issue in heart_rate.issues),
        reference_rmssd_ms=recording.reference_rmssd(window_start_s, end_s),
        estimated_rmssd_ms=rmssd.value,
        hrv_status=rmssd.status.value,
        reference_rr_brpm=recording.reference_rr_brpm,
        estimated_rr_brpm=respiratory.value,
        rr_status=respiratory.status.value,
        signal_latency_ms=round(signal_ms, 3),
        vitals_latency_ms=round(vitals_ms, 3),
    )
