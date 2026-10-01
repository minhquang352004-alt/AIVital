from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from aivitals_engine.benchmark.synthetic import SyntheticRecording, build_synthetic_suite
from aivitals_engine.contracts.frame import FramePacket

MIN_BEATS_FOR_REFERENCE = 3
SYNTHETIC_SOURCE = "synthetic"


@dataclass(frozen=True)
class BenchmarkRecording:
    recording_id: str
    subject_id: str
    timestamps: np.ndarray
    roi_rgb: dict[str, np.ndarray]
    face_detected: np.ndarray
    reference_beat_times_s: np.ndarray | None = None
    reference_hr_times_s: np.ndarray | None = None
    reference_hr_bpm: np.ndarray | None = None
    reference_rr_brpm: float | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def scenario(self) -> str:
        return self.metadata.get("scenario", "unknown")

    def frames(self) -> Iterator[FramePacket]:
        for index, timestamp in enumerate(self.timestamps):
            roi_means = {name: values[index] for name, values in self.roi_rgb.items()}
            yield FramePacket(timestamp=float(timestamp), roi_rgb_means=roi_means, face_detected=bool(self.face_detected[index]))

    def reference_intervals(self, start_s: float, end_s: float) -> np.ndarray | None:
        if self.reference_beat_times_s is None:
            return None
        beats = self.reference_beat_times_s
        return np.diff(beats[(beats >= start_s) & (beats <= end_s)]) * 1000.0

    def reference_heart_rate(self, start_s: float, end_s: float) -> float | None:
        intervals = self.reference_intervals(start_s, end_s)
        if intervals is not None:
            return float(60000.0 / intervals.mean()) if intervals.size >= MIN_BEATS_FOR_REFERENCE else None
        if self.reference_hr_times_s is None or self.reference_hr_bpm is None:
            return None
        inside = (self.reference_hr_times_s >= start_s) & (self.reference_hr_times_s <= end_s)
        return float(self.reference_hr_bpm[inside].mean()) if np.any(inside) else None

    def reference_rmssd(self, start_s: float, end_s: float) -> float | None:
        intervals = self.reference_intervals(start_s, end_s)
        if intervals is None or intervals.size < MIN_BEATS_FOR_REFERENCE:
            return None
        return float(np.sqrt(np.mean(np.diff(intervals) ** 2)))


def recording_from_synthetic(recording: SyntheticRecording) -> BenchmarkRecording:
    scenario = recording.scenario
    return BenchmarkRecording(
        recording_id=f"{SYNTHETIC_SOURCE}-{scenario.name}-{scenario.seed}",
        subject_id=f"{SYNTHETIC_SOURCE}-{scenario.seed}",
        timestamps=recording.timestamps,
        roi_rgb=recording.roi_rgb,
        face_detected=recording.face_detected,
        reference_beat_times_s=recording.beat_times_s,
        reference_rr_brpm=scenario.respiratory_rate_brpm,
        metadata=dict(recording.metadata),
    )


def optional_array(data: np.lib.npyio.NpzFile, key: str) -> np.ndarray | None:
    return np.asarray(data[key]) if key in data.files else None


def load_npz_recording(path: Path | str) -> BenchmarkRecording:
    path = Path(path)
    with np.load(path, allow_pickle=False) as data:
        roi_names = [str(name) for name in data["roi_names"]]
        roi_stack = np.asarray(data["roi_rgb"], dtype=float)
        rr_reference = optional_array(data, "reference_rr_brpm")
        return BenchmarkRecording(
            recording_id=str(data["recording_id"]) if "recording_id" in data.files else path.stem,
            subject_id=str(data["subject_id"]),
            timestamps=np.asarray(data["timestamps"], dtype=float),
            roi_rgb={name: roi_stack[index] for index, name in enumerate(roi_names)},
            face_detected=np.asarray(data["face_detected"], dtype=bool),
            reference_beat_times_s=optional_array(data, "reference_beat_times_s"),
            reference_hr_times_s=optional_array(data, "reference_hr_times_s"),
            reference_hr_bpm=optional_array(data, "reference_hr_bpm"),
            reference_rr_brpm=None if rr_reference is None else float(rr_reference),
            metadata={"scenario": str(data["scenario"]) if "scenario" in data.files else "unknown", "source": str(path)},
        )


def save_npz_recording(recording: BenchmarkRecording, path: Path | str) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    roi_names = sorted(recording.roi_rgb)
    arrays = {
        "recording_id": np.array(recording.recording_id),
        "subject_id": np.array(recording.subject_id),
        "scenario": np.array(recording.scenario),
        "timestamps": recording.timestamps,
        "roi_names": np.array(roi_names),
        "roi_rgb": np.stack([recording.roi_rgb[name] for name in roi_names]),
        "face_detected": recording.face_detected,
    }
    optional = {
        "reference_beat_times_s": recording.reference_beat_times_s,
        "reference_hr_times_s": recording.reference_hr_times_s,
        "reference_hr_bpm": recording.reference_hr_bpm,
        "reference_rr_brpm": None if recording.reference_rr_brpm is None else np.array(recording.reference_rr_brpm),
    }
    arrays.update({key: value for key, value in optional.items() if value is not None})
    np.savez_compressed(target, **arrays)
    return target


def load_dataset(source: str, seed: int = 7, duration_seconds: float = 60.0) -> list[BenchmarkRecording]:
    if source == SYNTHETIC_SOURCE:
        return [recording_from_synthetic(item) for item in build_synthetic_suite(seed, duration_seconds)]
    directory = Path(source)
    if not directory.is_dir():
        raise FileNotFoundError(f"Không tìm thấy thư mục dataset: {directory}")
    recordings = [load_npz_recording(path) for path in sorted(directory.glob("*.npz"))]
    if not recordings:
        raise FileNotFoundError(f"Thư mục {directory} không có file .npz nào")
    return recordings
