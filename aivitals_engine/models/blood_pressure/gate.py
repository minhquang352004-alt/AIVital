from dataclasses import dataclass, field

import numpy as np


@dataclass(frozen=True)
class DataSufficiencyCriteria:
    min_subjects: int = 85
    min_samples: int = 255
    systolic_low_mmhg: float = 100.0
    min_systolic_low_ratio: float = 0.05
    systolic_high_mmhg: float = 160.0
    min_systolic_high_ratio: float = 0.05
    systolic_elevated_mmhg: float = 140.0
    min_systolic_elevated_ratio: float = 0.20
    diastolic_low_mmhg: float = 60.0
    min_diastolic_low_ratio: float = 0.05
    diastolic_high_mmhg: float = 100.0
    min_diastolic_high_ratio: float = 0.05
    diastolic_elevated_mmhg: float = 85.0
    min_diastolic_elevated_ratio: float = 0.20


@dataclass(frozen=True)
class GateDecision:
    passed: bool
    subject_count: int
    sample_count: int
    reasons: tuple[str, ...]
    distribution: dict[str, float] = field(default_factory=dict)


def subject_mean_pressures(targets: np.ndarray, subject_ids: np.ndarray) -> np.ndarray:
    unique_subjects = np.unique(subject_ids)
    return np.array([targets[subject_ids == subject].mean(axis=0) for subject in unique_subjects])


def pressure_distribution(means: np.ndarray, criteria: DataSufficiencyCriteria) -> dict[str, float]:
    systolic, diastolic = means[:, 0], means[:, 1]
    return {
        "systolic_low": float(np.mean(systolic <= criteria.systolic_low_mmhg)),
        "systolic_high": float(np.mean(systolic >= criteria.systolic_high_mmhg)),
        "systolic_elevated": float(np.mean(systolic >= criteria.systolic_elevated_mmhg)),
        "diastolic_low": float(np.mean(diastolic <= criteria.diastolic_low_mmhg)),
        "diastolic_high": float(np.mean(diastolic >= criteria.diastolic_high_mmhg)),
        "diastolic_elevated": float(np.mean(diastolic >= criteria.diastolic_elevated_mmhg)),
    }


def distribution_minimums(criteria: DataSufficiencyCriteria) -> dict[str, float]:
    return {
        "systolic_low": criteria.min_systolic_low_ratio,
        "systolic_high": criteria.min_systolic_high_ratio,
        "systolic_elevated": criteria.min_systolic_elevated_ratio,
        "diastolic_low": criteria.min_diastolic_low_ratio,
        "diastolic_high": criteria.min_diastolic_high_ratio,
        "diastolic_elevated": criteria.min_diastolic_elevated_ratio,
    }


def evaluate_data_sufficiency(
    targets: np.ndarray, subject_ids: np.ndarray, criteria: DataSufficiencyCriteria | None = None
) -> GateDecision:
    criteria = criteria or DataSufficiencyCriteria()
    targets = np.asarray(targets, dtype=float)
    subject_ids = np.asarray(subject_ids)
    subject_count = int(np.unique(subject_ids).size)
    reasons = []
    if subject_count < criteria.min_subjects:
        reasons.append(f"Số subject {subject_count} nhỏ hơn yêu cầu {criteria.min_subjects}")
    if targets.shape[0] < criteria.min_samples:
        reasons.append(f"Số mẫu {targets.shape[0]} nhỏ hơn yêu cầu {criteria.min_samples}")
    distribution = pressure_distribution(subject_mean_pressures(targets, subject_ids), criteria) if subject_count else {}
    for key, minimum in distribution_minimums(criteria).items():
        if distribution.get(key, 0.0) < minimum:
            reasons.append(f"Phân bố huyết áp nhóm {key} là {distribution.get(key, 0.0):.2f}, cần tối thiểu {minimum:.2f}")
    return GateDecision(not reasons, subject_count, int(targets.shape[0]), tuple(reasons), distribution)
