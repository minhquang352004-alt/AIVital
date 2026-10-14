from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np

from aivitals_engine.benchmark.metrics import ErrorMetrics, compute_error_metrics
from aivitals_engine.benchmark.report import WindowRecord

CONFIDENCE_BINS: tuple[tuple[float, float], ...] = ((0.0, 0.3), (0.3, 0.6), (0.6, 0.8), (0.8, 1.0001))
WORST_WINDOW_COUNT = 5


@dataclass(frozen=True)
class GroupError:
    label: str
    windows: int
    metrics: ErrorMetrics


@dataclass(frozen=True)
class WorstWindow:
    scenario: str
    recording_id: str
    window_end_s: float
    reference_bpm: float
    estimated_bpm: float
    error_bpm: float
    status: str
    confidence: float
    issue_codes: tuple[str, ...]


@dataclass(frozen=True)
class MethodErrorAnalysis:
    method: str
    windows: int
    rejected_windows: int
    overall: ErrorMetrics
    by_scenario: list[GroupError] = field(default_factory=list)
    by_status: list[GroupError] = field(default_factory=list)
    by_confidence: list[GroupError] = field(default_factory=list)
    worst_windows: list[WorstWindow] = field(default_factory=list)


def has_estimate(record: WindowRecord) -> bool:
    return record.reference_hr_bpm is not None and record.estimated_hr_bpm is not None


def group_error(label: str, records: Sequence[WindowRecord], tolerance: float) -> GroupError:
    estimated = [record for record in records if has_estimate(record)]
    metrics = compute_error_metrics(
        [record.reference_hr_bpm for record in estimated],
        [record.estimated_hr_bpm for record in estimated],
        tolerance,
    )
    return GroupError(label=label, windows=len(records), metrics=metrics)


def confidence_label(low: float, high: float) -> str:
    return f"{low:.1f}–{min(high, 1.0):.1f}"


def worst_windows(records: Sequence[WindowRecord], count: int = WORST_WINDOW_COUNT) -> list[WorstWindow]:
    ranked = sorted(
        (record for record in records if has_estimate(record)),
        key=lambda record: abs(record.estimated_hr_bpm - record.reference_hr_bpm),
        reverse=True,
    )
    return [
        WorstWindow(
            scenario=record.scenario,
            recording_id=record.recording_id,
            window_end_s=record.window_end_s,
            reference_bpm=round(record.reference_hr_bpm, 1),
            estimated_bpm=record.estimated_hr_bpm,
            error_bpm=round(record.estimated_hr_bpm - record.reference_hr_bpm, 1),
            status=record.hr_status,
            confidence=record.hr_confidence,
            issue_codes=record.hr_issue_codes,
        )
        for record in ranked[:count]
    ]


def analyse_method(method: str, records: Sequence[WindowRecord], tolerance: float) -> MethodErrorAnalysis:
    scenarios = sorted({record.scenario for record in records})
    statuses = sorted({record.hr_status for record in records})
    return MethodErrorAnalysis(
        method=method,
        windows=len(records),
        rejected_windows=sum(1 for record in records if record.estimated_hr_bpm is None),
        overall=group_error("all", records, tolerance).metrics,
        by_scenario=[group_error(name, [r for r in records if r.scenario == name], tolerance) for name in scenarios],
        by_status=[group_error(name, [r for r in records if r.hr_status == name], tolerance) for name in statuses],
        by_confidence=[
            group_error(confidence_label(low, high), [r for r in records if low <= r.hr_confidence < high], tolerance)
            for low, high in CONFIDENCE_BINS
        ],
        worst_windows=worst_windows(records),
    )


def analyse_heart_rate_errors(records: Sequence[WindowRecord], tolerance: float = 5.0) -> list[MethodErrorAnalysis]:
    methods = sorted({record.method for record in records})
    return [analyse_method(method, [r for r in records if r.method == method], tolerance) for method in methods]


def calibration_arrays(records: Sequence[WindowRecord]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    usable = [record for record in records if has_estimate(record)]
    confidence = np.array([record.hr_confidence for record in usable], dtype=float)
    errors = np.array([abs(record.estimated_hr_bpm - record.reference_hr_bpm) for record in usable], dtype=float)
    groups = np.array([record.recording_id for record in usable])
    return confidence, errors, groups
