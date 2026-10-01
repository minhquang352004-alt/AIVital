from collections import deque
from dataclasses import dataclass

import numpy as np

MAD_TO_SIGMA = 1.4826


@dataclass(frozen=True)
class TrackedValue:
    raw: float
    smoothed: float
    is_outlier: bool


@dataclass(frozen=True)
class TrackerConfig:
    history_size: int = 10
    smoothing_alpha: float = 0.5
    outlier_sigma: float = 3.5
    min_spread: float = 3.0
    min_history_for_outlier: int = 3
    max_consecutive_outliers: int = 3


class TemporalTracker:
    def __init__(self, config: TrackerConfig | None = None) -> None:
        self._config = config or TrackerConfig()
        self._history: deque[tuple[float, float]] = deque(maxlen=self._config.history_size)
        self._smoothed: float | None = None
        self._consecutive_outliers = 0

    @property
    def last_accepted(self) -> tuple[float, float] | None:
        if self._smoothed is None or not self._history:
            return None
        return self._history[-1][0], self._smoothed

    @property
    def recent_values(self) -> tuple[float, ...]:
        return tuple(value for _, value in self._history)

    def reset(self) -> None:
        self._history.clear()
        self._smoothed = None
        self._consecutive_outliers = 0

    def update(self, value: float, timestamp: float) -> TrackedValue:
        if self._is_outlier(value):
            self._consecutive_outliers += 1
            if self._consecutive_outliers < self._config.max_consecutive_outliers:
                return TrackedValue(raw=value, smoothed=self._smoothed, is_outlier=True)
            self.reset()
        self._consecutive_outliers = 0
        self._history.append((timestamp, value))
        alpha = self._config.smoothing_alpha
        self._smoothed = value if self._smoothed is None else alpha * value + (1.0 - alpha) * self._smoothed
        return TrackedValue(raw=value, smoothed=self._smoothed, is_outlier=False)

    def _is_outlier(self, value: float) -> bool:
        values = np.array(self.recent_values)
        if values.size < self._config.min_history_for_outlier:
            return False
        median = np.median(values)
        spread = max(MAD_TO_SIGMA * np.median(np.abs(values - median)), self._config.min_spread)
        return bool(abs(value - median) > self._config.outlier_sigma * spread)
