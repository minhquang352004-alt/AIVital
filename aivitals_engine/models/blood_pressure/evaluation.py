from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

import numpy as np
from sklearn.model_selection import GroupKFold

AAMI_MAX_MEAN_ERROR_MMHG = 5.0
AAMI_MAX_ERROR_SD_MMHG = 8.0
BHS_GRADE_THRESHOLDS = (
    ("A", (0.60, 0.85, 0.95)),
    ("B", (0.50, 0.75, 0.90)),
    ("C", (0.40, 0.65, 0.85)),
)
MIN_SAMPLES_FOR_CORRELATION = 3
EPSILON = 1e-12


class MatrixRegressor(Protocol):
    def fit(self, features: np.ndarray, targets: np.ndarray) -> "MatrixRegressor": ...

    def predict_matrix(self, features: np.ndarray) -> np.ndarray: ...


@dataclass(frozen=True)
class PressureErrorStats:
    mean_absolute_error: float
    mean_error: float
    error_sd: float
    pearson_r: float | None
    within_5: float
    within_10: float
    within_15: float

    @property
    def meets_aami(self) -> bool:
        return abs(self.mean_error) <= AAMI_MAX_MEAN_ERROR_MMHG and self.error_sd <= AAMI_MAX_ERROR_SD_MMHG

    @property
    def bhs_grade(self) -> str:
        observed = (self.within_5, self.within_10, self.within_15)
        for grade, thresholds in BHS_GRADE_THRESHOLDS:
            if all(value >= threshold for value, threshold in zip(observed, thresholds)):
                return grade
        return "D"


@dataclass(frozen=True)
class BloodPressureEvaluation:
    sample_count: int
    systolic: PressureErrorStats
    diastolic: PressureErrorStats


@dataclass(frozen=True)
class CrossValidationReport:
    subject_count: int
    folds: tuple[BloodPressureEvaluation, ...]
    pooled: BloodPressureEvaluation


def pearson_correlation(reference: np.ndarray, predicted: np.ndarray) -> float | None:
    if reference.size < MIN_SAMPLES_FOR_CORRELATION:
        return None
    if np.std(reference) < EPSILON or np.std(predicted) < EPSILON:
        return None
    return float(np.corrcoef(reference, predicted)[0, 1])


def pressure_error_stats(reference: np.ndarray, predicted: np.ndarray) -> PressureErrorStats:
    reference = np.asarray(reference, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    errors = predicted - reference
    absolute = np.abs(errors)
    return PressureErrorStats(
        mean_absolute_error=float(absolute.mean()),
        mean_error=float(errors.mean()),
        error_sd=float(errors.std(ddof=1)) if errors.size > 1 else 0.0,
        pearson_r=pearson_correlation(reference, predicted),
        within_5=float(np.mean(absolute <= 5.0)),
        within_10=float(np.mean(absolute <= 10.0)),
        within_15=float(np.mean(absolute <= 15.0)),
    )


def evaluate_blood_pressure(targets: np.ndarray, predictions: np.ndarray) -> BloodPressureEvaluation:
    targets = np.asarray(targets, dtype=float)
    predictions = np.asarray(predictions, dtype=float)
    if targets.shape != predictions.shape or targets.ndim != 2 or targets.shape[1] != 2:
        raise ValueError("targets và predictions phải cùng dạng (n, 2)")
    return BloodPressureEvaluation(
        sample_count=int(targets.shape[0]),
        systolic=pressure_error_stats(targets[:, 0], predictions[:, 0]),
        diastolic=pressure_error_stats(targets[:, 1], predictions[:, 1]),
    )


def subject_independent_cross_validation(
    model_factory: Callable[[], MatrixRegressor],
    features: np.ndarray,
    targets: np.ndarray,
    subject_ids: np.ndarray,
    n_splits: int = 5,
) -> CrossValidationReport:
    features = np.asarray(features, dtype=float)
    targets = np.asarray(targets, dtype=float)
    subject_ids = np.asarray(subject_ids)
    subject_count = int(np.unique(subject_ids).size)
    if subject_count < n_splits:
        raise ValueError(f"Cần tối thiểu {n_splits} subject để chia {n_splits} fold")
    pooled_predictions = np.full_like(targets, np.nan)
    folds = []
    for train_index, test_index in GroupKFold(n_splits=n_splits).split(features, targets, groups=subject_ids):
        if set(subject_ids[train_index]) & set(subject_ids[test_index]):
            raise RuntimeError("Phát hiện rò rỉ subject giữa tập train và test")
        model = model_factory().fit(features[train_index], targets[train_index])
        fold_predictions = model.predict_matrix(features[test_index])
        pooled_predictions[test_index] = fold_predictions
        folds.append(evaluate_blood_pressure(targets[test_index], fold_predictions))
    return CrossValidationReport(subject_count, tuple(folds), evaluate_blood_pressure(targets, pooled_predictions))
