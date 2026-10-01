from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

import numpy as np

LUMA_WEIGHTS = np.array([0.299, 0.587, 0.114])
CLIPPED_LOW_LEVEL = 5
CLIPPED_HIGH_LEVEL = 250
EPSILON = 1e-9


class FaceQualityIssue(StrEnum):
    INSUFFICIENT_OBSERVATIONS = "INSUFFICIENT_OBSERVATIONS"
    FACE_NOT_DETECTED = "FACE_NOT_DETECTED"
    FACE_TOO_SMALL = "FACE_TOO_SMALL"
    EXCESSIVE_MOTION = "EXCESSIVE_MOTION"
    TOO_DARK = "TOO_DARK"
    TOO_BRIGHT = "TOO_BRIGHT"
    LIGHTING_UNSTABLE = "LIGHTING_UNSTABLE"
    PIXEL_CLIPPING = "PIXEL_CLIPPING"


@dataclass(frozen=True)
class FaceObservation:
    timestamp: float
    face_box: tuple[float, float, float, float] | None
    frame_size: tuple[int, int]
    mean_luma: float
    clipped_pixel_ratio: float = 0.0


@dataclass(frozen=True)
class FaceQualityConfig:
    min_observations: int = 10
    min_detection_ratio: float = 0.9
    ideal_face_width_ratio: float = 0.25
    min_face_width_ratio: float = 0.12
    motion_reference_speed: float = 0.25
    max_motion_speed: float = 0.35
    dark_luma: float = 50.0
    comfortable_low_luma: float = 80.0
    comfortable_high_luma: float = 190.0
    bright_luma: float = 230.0
    max_luma_variation: float = 0.08
    max_clipped_ratio: float = 0.05
    min_overall_score: float = 0.6


@dataclass(frozen=True)
class FaceQualityReport:
    detection_ratio: float
    motion_score: float
    lighting_score: float
    face_size_score: float
    overall_score: float
    issues: tuple[FaceQualityIssue, ...]

    @property
    def is_acceptable(self) -> bool:
        return not self.issues


def measure_frame_lighting(face_pixels_rgb: np.ndarray) -> tuple[float, float]:
    luma = np.asarray(face_pixels_rgb, dtype=float)[..., :3] @ LUMA_WEIGHTS
    clipped = (luma <= CLIPPED_LOW_LEVEL) | (luma >= CLIPPED_HIGH_LEVEL)
    return float(luma.mean()), float(clipped.mean())


def box_center(box: tuple[float, float, float, float]) -> np.ndarray:
    x, y, width, height = box
    return np.array([x + width / 2.0, y + height / 2.0])


class FaceQualityAnalyzer:
    def __init__(self, config: FaceQualityConfig | None = None) -> None:
        self._config = config or FaceQualityConfig()

    def analyze(self, observations: Sequence[FaceObservation]) -> FaceQualityReport:
        if len(observations) < self._config.min_observations:
            return FaceQualityReport(0.0, 0.0, 0.0, 0.0, 0.0, (FaceQualityIssue.INSUFFICIENT_OBSERVATIONS,))
        detected = [item for item in observations if item.face_box is not None]
        detection_ratio = len(detected) / len(observations)
        motion_speed = self._motion_speed(detected)
        motion_score = float(np.exp(-motion_speed / self._config.motion_reference_speed))
        lighting_score, lighting_issues = self._lighting(observations)
        size_ratio = self._face_width_ratio(detected)
        size_score = float(np.clip(size_ratio / self._config.ideal_face_width_ratio, 0.0, 1.0))
        overall = float(detection_ratio * motion_score * lighting_score * size_score) ** 0.25
        issues = self._issues(detection_ratio, motion_speed, size_ratio, overall, lighting_issues)
        return FaceQualityReport(detection_ratio, motion_score, lighting_score, size_score, overall, issues)

    def _motion_speed(self, detected: Sequence[FaceObservation]) -> float:
        if len(detected) < 2:
            return 0.0
        centers = np.array([box_center(item.face_box) for item in detected])
        widths = np.array([max(item.face_box[2], EPSILON) for item in detected])
        times = np.array([item.timestamp for item in detected])
        displacement = np.linalg.norm(np.diff(centers, axis=0), axis=1) / widths[1:]
        scale_change = np.abs(np.diff(widths)) / widths[1:]
        elapsed = np.maximum(np.diff(times), EPSILON)
        return float(np.mean((displacement + scale_change) / elapsed))

    def _face_width_ratio(self, detected: Sequence[FaceObservation]) -> float:
        if not detected:
            return 0.0
        return float(np.median([item.face_box[2] / item.frame_size[0] for item in detected]))

    def _lighting(self, observations: Sequence[FaceObservation]) -> tuple[float, list[FaceQualityIssue]]:
        luma = np.array([item.mean_luma for item in observations])
        mean_luma = float(luma.mean())
        variation = float(luma.std() / max(mean_luma, EPSILON))
        clipped = float(np.mean([item.clipped_pixel_ratio for item in observations]))
        level_score = self._luma_level_score(mean_luma)
        stability_score = float(np.clip(1.0 - variation / (2.0 * self._config.max_luma_variation), 0.0, 1.0))
        clipping_score = float(np.clip(1.0 - clipped / (2.0 * self._config.max_clipped_ratio), 0.0, 1.0))
        issues = self._lighting_issues(mean_luma, variation, clipped)
        return level_score * stability_score * clipping_score, issues

    def _luma_level_score(self, mean_luma: float) -> float:
        config = self._config
        if mean_luma < config.comfortable_low_luma:
            span = config.comfortable_low_luma - config.dark_luma
            return float(np.clip((mean_luma - config.dark_luma) / span, 0.0, 1.0))
        if mean_luma > config.comfortable_high_luma:
            span = config.bright_luma - config.comfortable_high_luma
            return float(np.clip((config.bright_luma - mean_luma) / span, 0.0, 1.0))
        return 1.0

    def _lighting_issues(self, mean_luma: float, variation: float, clipped: float) -> list[FaceQualityIssue]:
        issues = []
        if mean_luma < self._config.comfortable_low_luma:
            issues.append(FaceQualityIssue.TOO_DARK)
        if mean_luma > self._config.comfortable_high_luma:
            issues.append(FaceQualityIssue.TOO_BRIGHT)
        if variation > self._config.max_luma_variation:
            issues.append(FaceQualityIssue.LIGHTING_UNSTABLE)
        if clipped > self._config.max_clipped_ratio:
            issues.append(FaceQualityIssue.PIXEL_CLIPPING)
        return issues

    def _issues(
        self,
        detection_ratio: float,
        motion_speed: float,
        size_ratio: float,
        overall: float,
        lighting_issues: list[FaceQualityIssue],
    ) -> tuple[FaceQualityIssue, ...]:
        issues = []
        if detection_ratio < self._config.min_detection_ratio:
            issues.append(FaceQualityIssue.FACE_NOT_DETECTED)
        if size_ratio < self._config.min_face_width_ratio:
            issues.append(FaceQualityIssue.FACE_TOO_SMALL)
        if motion_speed > self._config.max_motion_speed:
            issues.append(FaceQualityIssue.EXCESSIVE_MOTION)
        return tuple(issues + lighting_issues)
