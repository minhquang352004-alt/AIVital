from collections.abc import Mapping
from dataclasses import dataclass, field

import numpy as np


@dataclass(frozen=True)
class FramePacket:
    timestamp: float
    roi_rgb_means: Mapping[str, np.ndarray] = field(default_factory=dict)
    face_detected: bool = True
    face_crop: np.ndarray | None = None

    def mean_rgb(self) -> np.ndarray | None:
        if not self.face_detected or not self.roi_rgb_means:
            return None
        stacked = np.stack([np.asarray(values, dtype=float) for values in self.roi_rgb_means.values()])
        return stacked.mean(axis=0)

    def roi_rgb(self, roi_name: str) -> np.ndarray | None:
        if not self.face_detected or roi_name not in self.roi_rgb_means:
            return None
        return np.asarray(self.roi_rgb_means[roi_name], dtype=float)
