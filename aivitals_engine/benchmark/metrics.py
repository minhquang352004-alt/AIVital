from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

LIMITS_OF_AGREEMENT_FACTOR = 1.96
MIN_PAIRS_FOR_CORRELATION = 3
EPSILON = 1e-12


@dataclass(frozen=True)
class ErrorMetrics:
    count: int
    mae: float | None = None
    rmse: float | None = None
    mape: float | None = None
    bias: float | None = None
    loa_lower: float | None = None
    loa_upper: float | None = None
    pearson_r: float | None = None
    within_tolerance_ratio: float | None = None


def paired_values(reference: Sequence[float | None], estimated: Sequence[float | None]) -> tuple[np.ndarray, np.ndarray]:
    pairs = [(ref, est) for ref, est in zip(reference, estimated) if ref is not None and est is not None]
    if not pairs:
        return np.zeros(0), np.zeros(0)
    references, estimates = zip(*pairs)
    return np.array(references, dtype=float), np.array(estimates, dtype=float)


def correlation(reference: np.ndarray, estimated: np.ndarray) -> float | None:
    if reference.size < MIN_PAIRS_FOR_CORRELATION or np.std(reference) < EPSILON or np.std(estimated) < EPSILON:
        return None
    return float(np.corrcoef(reference, estimated)[0, 1])


def compute_error_metrics(
    reference: Sequence[float | None], estimated: Sequence[float | None], tolerance: float
) -> ErrorMetrics:
    references, estimates = paired_values(reference, estimated)
    if references.size == 0:
        return ErrorMetrics(count=0)
    errors = estimates - references
    deviation = float(errors.std(ddof=1)) if errors.size > 1 else 0.0
    bias = float(errors.mean())
    return ErrorMetrics(
        count=int(errors.size),
        mae=float(np.abs(errors).mean()),
        rmse=float(np.sqrt(np.mean(errors**2))),
        mape=float(np.mean(np.abs(errors) / np.maximum(np.abs(references), EPSILON)) * 100.0),
        bias=bias,
        loa_lower=bias - LIMITS_OF_AGREEMENT_FACTOR * deviation,
        loa_upper=bias + LIMITS_OF_AGREEMENT_FACTOR * deviation,
        pearson_r=correlation(references, estimates),
        within_tolerance_ratio=float(np.mean(np.abs(errors) <= tolerance)),
    )


def percentile(values: Sequence[float], quantile: float) -> float | None:
    if not values:
        return None
    return float(np.percentile(np.asarray(values, dtype=float), quantile))
