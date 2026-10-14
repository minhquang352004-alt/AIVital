import hashlib
from pathlib import Path

import joblib
import numpy as np
from sklearn.isotonic import IsotonicRegression

MIN_CALIBRATION_SAMPLES = 20
DEFAULT_BIN_COUNT = 10


class CalibratorNotFittedError(RuntimeError):
    pass


def expected_calibration_error(confidence: np.ndarray, correct: np.ndarray, bin_count: int = DEFAULT_BIN_COUNT) -> float:
    confidence = np.asarray(confidence, dtype=float)
    correct = np.asarray(correct, dtype=float)
    if confidence.size == 0:
        return 0.0
    edges = np.linspace(0.0, 1.0, bin_count + 1)
    bin_indices = np.clip(np.digitize(confidence, edges[1:-1]), 0, bin_count - 1)
    error = 0.0
    for bin_index in range(bin_count):
        members = bin_indices == bin_index
        if np.any(members):
            gap = abs(confidence[members].mean() - correct[members].mean())
            error += gap * members.mean()
    return float(error)


class ConfidenceCalibrator:
    def __init__(self, error_tolerance: float = 5.0) -> None:
        self._error_tolerance = error_tolerance
        self._model: IsotonicRegression | None = None

    @property
    def error_tolerance(self) -> float:
        return self._error_tolerance

    @property
    def is_fitted(self) -> bool:
        return self._model is not None

    def fit(self, raw_confidence: np.ndarray, absolute_errors: np.ndarray) -> "ConfidenceCalibrator":
        raw_confidence = np.asarray(raw_confidence, dtype=float)
        absolute_errors = np.asarray(absolute_errors, dtype=float)
        if raw_confidence.shape != absolute_errors.shape:
            raise ValueError("raw_confidence và absolute_errors phải cùng kích thước")
        if raw_confidence.size < MIN_CALIBRATION_SAMPLES:
            raise ValueError(f"Cần tối thiểu {MIN_CALIBRATION_SAMPLES} mẫu để hiệu chỉnh confidence")
        correct = (np.abs(absolute_errors) <= self._error_tolerance).astype(float)
        self._model = IsotonicRegression(y_min=0.0, y_max=1.0, increasing=True, out_of_bounds="clip")
        self._model.fit(raw_confidence, correct)
        return self

    def transform(self, raw_confidence: np.ndarray | float) -> np.ndarray:
        if self._model is None:
            raise CalibratorNotFittedError("Calibrator chưa được fit")
        values = np.atleast_1d(np.asarray(raw_confidence, dtype=float))
        return np.clip(self._model.predict(values), 0.0, 1.0)

    def evaluate(self, raw_confidence: np.ndarray, absolute_errors: np.ndarray) -> dict[str, float]:
        correct = (np.abs(np.asarray(absolute_errors, dtype=float)) <= self._error_tolerance).astype(float)
        return {
            "ece_before": expected_calibration_error(np.asarray(raw_confidence, dtype=float), correct),
            "ece_after": expected_calibration_error(self.transform(raw_confidence), correct),
        }

    def save(self, path: Path | str) -> Path:
        if self._model is None:
            raise CalibratorNotFittedError("Calibrator chưa được fit")
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"error_tolerance": self._error_tolerance, "model": self._model}, target)
        return target

    @classmethod
    def load(cls, path: Path | str, checksum_sha256: str | None = None) -> "ConfidenceCalibrator":
        if checksum_sha256 is not None and hashlib.sha256(Path(path).read_bytes()).hexdigest() != checksum_sha256:
            raise ValueError("Checksum file calibrator không khớp, từ chối nạp")
        payload = joblib.load(path)
        calibrator = cls(error_tolerance=payload["error_tolerance"])
        calibrator._model = payload["model"]
        return calibrator
