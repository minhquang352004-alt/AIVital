from collections.abc import Mapping
from dataclasses import dataclass, field, replace

import numpy as np


def as_finite_vector(values, name: str) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    if array.ndim != 1:
        raise ValueError(f"{name} phải là mảng 1 chiều")
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} chứa giá trị NaN hoặc vô cực")
    return array


def validate_unit_interval(value: float | None, name: str) -> None:
    if value is not None and not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} phải nằm trong khoảng [0, 1]")


@dataclass(frozen=True)
class BVPWindow:
    samples: np.ndarray
    sampling_rate_hz: float
    start_timestamp: float
    method: str
    method_version: str
    signal_quality: float | None = None
    missing_ratio: float = 0.0
    raw_samples: np.ndarray | None = None
    roi_samples: Mapping[str, np.ndarray] = field(default_factory=dict)

    def __post_init__(self) -> None:
        samples = as_finite_vector(self.samples, "samples")
        if self.sampling_rate_hz <= 0:
            raise ValueError("sampling_rate_hz phải lớn hơn 0")
        validate_unit_interval(self.missing_ratio, "missing_ratio")
        validate_unit_interval(self.signal_quality, "signal_quality")
        object.__setattr__(self, "samples", samples)
        object.__setattr__(self, "raw_samples", self._companion(self.raw_samples, "raw_samples", samples.size))
        roi_samples = {
            name: self._companion(values, f"roi_samples[{name}]", samples.size)
            for name, values in self.roi_samples.items()
        }
        object.__setattr__(self, "roi_samples", roi_samples)

    @staticmethod
    def _companion(values, name: str, expected_size: int) -> np.ndarray | None:
        if values is None:
            return None
        array = as_finite_vector(values, name)
        if array.size != expected_size:
            raise ValueError(f"{name} phải có cùng số mẫu với samples")
        return array

    @property
    def duration_seconds(self) -> float:
        return self.samples.size / self.sampling_rate_hz

    @property
    def end_timestamp(self) -> float:
        return self.start_timestamp + self.duration_seconds

    def tail(self, seconds: float) -> "BVPWindow":
        count = int(round(seconds * self.sampling_rate_hz))
        if count >= self.samples.size:
            return self
        offset = self.samples.size - count
        return replace(
            self,
            samples=self.samples[offset:],
            start_timestamp=self.start_timestamp + offset / self.sampling_rate_hz,
            raw_samples=None if self.raw_samples is None else self.raw_samples[offset:],
            roi_samples={name: values[offset:] for name, values in self.roi_samples.items()},
        )
