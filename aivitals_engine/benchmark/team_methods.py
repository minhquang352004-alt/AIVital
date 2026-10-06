from collections import deque
from collections.abc import Callable
from typing import Any

import numpy as np

from aivitals_engine.contracts.bvp_window import BVPWindow
from aivitals_engine.contracts.frame import FramePacket
from aivitals_engine.rppg.base import RPPGMethod
from aivitals_engine.rppg.chrom import CHROMMethod
from aivitals_engine.rppg.green import GREENMethod
from aivitals_engine.rppg.pos import POSMethod
from aivitals_engine.vitals.preprocess import detrend_signal

MIN_SIGNAL_SECONDS = 4.0
EPSILON = 1e-9

TEAM_METHODS: dict[str, Callable[..., RPPGMethod]] = {
    "GREEN": GREENMethod,
    "CHROM": CHROMMethod,
    "POS": POSMethod,
}


def green_intensity(rgb: np.ndarray) -> np.ndarray:
    return -(rgb[:, 1] / max(float(rgb[:, 1].mean()), EPSILON) - 1.0)


class TeamRPPGSource:
    def __init__(self, name: str, window_seconds: float = 30.0, nominal_sampling_rate_hz: float = 30.0) -> None:
        if name not in TEAM_METHODS:
            raise ValueError(f"Method {name} không thuộc danh sách {sorted(TEAM_METHODS)}")
        self.name = name
        self._factory = TEAM_METHODS[name]
        self.version = self._factory(fps=nominal_sampling_rate_hz).version
        self._window_seconds = window_seconds
        self._nominal_rate = nominal_sampling_rate_hz
        self._capacity = int(round(window_seconds * nominal_sampling_rate_hz))
        self.reset()

    def reset(self) -> None:
        self._timestamps: deque[float] = deque(maxlen=self._capacity)
        self._missing: deque[bool] = deque(maxlen=self._capacity)
        self._roi_traces: dict[str, deque[np.ndarray]] = {}
        self._last_rgb: dict[str, np.ndarray] = {}

    def update(self, frame: FramePacket) -> None:
        detected = frame.face_detected and bool(frame.roi_rgb_means)
        if not detected and not self._last_rgb:
            return
        if detected:
            self._last_rgb = {name: np.asarray(values, dtype=float) for name, values in frame.roi_rgb_means.items()}
        self._timestamps.append(frame.timestamp)
        self._missing.append(not detected)
        for name, values in self._last_rgb.items():
            self._roi_traces.setdefault(name, deque(maxlen=self._capacity)).append(values)

    def get_signal(self) -> BVPWindow | None:
        count = len(self._timestamps)
        roi_rgb = {name: np.array(trace) for name, trace in self._roi_traces.items() if len(trace) == count}
        sampling_rate = self._sampling_rate()
        if not roi_rgb or count < MIN_SIGNAL_SECONDS * sampling_rate:
            return None
        method = self._factory(fps=sampling_rate)
        mean_rgb = np.mean(np.stack(list(roi_rgb.values())), axis=0)
        roi_samples = {name: method.process(rgb) for name, rgb in roi_rgb.items()} if len(roi_rgb) > 1 else {}
        return BVPWindow(
            samples=method.process(mean_rgb),
            sampling_rate_hz=sampling_rate,
            start_timestamp=self._timestamps[0],
            method=self.name,
            method_version=self.version,
            missing_ratio=float(np.mean(self._missing)),
            raw_samples=detrend_signal(green_intensity(mean_rgb)),
            roi_samples=roi_samples,
        )

    def get_metadata(self) -> dict[str, Any]:
        return {
            "method": self.name,
            "version": self.version,
            "window_seconds": self._window_seconds,
            "buffered_frames": len(self._timestamps),
            "roi_names": sorted(self._roi_traces),
        }

    def _sampling_rate(self) -> float:
        if len(self._timestamps) < 2:
            return self._nominal_rate
        elapsed = self._timestamps[-1] - self._timestamps[0]
        return (len(self._timestamps) - 1) / elapsed if elapsed > 0 else self._nominal_rate
