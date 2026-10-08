import csv
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from aivitals_engine.models.blood_pressure.features import BP_FEATURE_NAMES

SUBJECT_COLUMN = "subject_id"
SYSTOLIC_COLUMN = "sbp_mmhg"
DIASTOLIC_COLUMN = "dbp_mmhg"
TARGET_COLUMNS = (SYSTOLIC_COLUMN, DIASTOLIC_COLUMN)

FEATURE_PRIORS: dict[str, tuple[float, float]] = {
    "hrv_rmssd_ms": (40.0, 15.0),
    "hrv_sdnn_ms": (45.0, 15.0),
    "respiratory_rate_brpm": (15.0, 3.0),
    "mean_rise_time_ms": (230.0, 40.0),
    "mean_decay_time_ms": (520.0, 100.0),
    "std_rise_time_ms": (18.0, 5.0),
    "mean_systolic_ratio": (0.32, 0.04),
    "mean_pw25_ms": (450.0, 90.0),
    "mean_pw50_ms": (150.0, 35.0),
    "mean_pw75_ms": (80.0, 20.0),
    "mean_area_ratio": (0.6, 0.15),
    "aix_proxy": (-0.4, 0.15),
    "apg_aging_index": (-1.5, 2.0),
    "mean_pulse_amplitude": (3.0, 1.0),
    "pulse_amp_cv": (0.15, 0.05),
    "notch_relative_amp": (0.3, 0.1),
    "harmonic_ratio_h2": (0.6, 0.15),
    "harmonic_ratio_h3": (0.12, 0.05),
    "spectral_entropy": (0.5, 0.1),
    "in_band_power_ratio": (0.75, 0.15),
    "baseline_drift_slope": (0.0, 0.002),
    "bvp_skewness": (0.8, 0.3),
    "bvp_kurtosis": (0.3, 0.5),
    "ibi_std_ms": (45.0, 15.0),
}


@dataclass(frozen=True)
class BloodPressureDataset:
    features: np.ndarray
    targets: np.ndarray
    subject_ids: np.ndarray
    feature_names: tuple[str, ...]
    source: str

    @property
    def sample_count(self) -> int:
        return int(self.targets.shape[0])

    @property
    def subject_count(self) -> int:
        return int(np.unique(self.subject_ids).size)


def parse_number(text: str | None) -> float:
    if text is None or not text.strip():
        return np.nan
    return float(text)


def load_bp_dataset_csv(path: Path | str, feature_names: Sequence[str] = BP_FEATURE_NAMES) -> BloodPressureDataset:
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(f"Không tìm thấy file dữ liệu huyết áp: {source}")
    with source.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError("File dữ liệu huyết áp không có dòng nào")
    missing_columns = [column for column in (SUBJECT_COLUMN, *TARGET_COLUMNS) if column not in rows[0]]
    if missing_columns:
        raise ValueError(f"Thiếu cột bắt buộc: {', '.join(missing_columns)}")
    features = np.array([[parse_number(row.get(name)) for name in feature_names] for row in rows], dtype=float)
    targets = np.array([[parse_number(row[column]) for column in TARGET_COLUMNS] for row in rows], dtype=float)
    if not np.all(np.isfinite(targets)):
        raise ValueError("Cột sbp_mmhg / dbp_mmhg có giá trị trống hoặc không hợp lệ")
    subjects = np.array([row[SUBJECT_COLUMN] for row in rows])
    return BloodPressureDataset(features, targets, subjects, tuple(feature_names), str(source))


def write_bp_dataset_csv(dataset: BloodPressureDataset, path: Path | str) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([SUBJECT_COLUMN, *TARGET_COLUMNS, *dataset.feature_names])
        for subject, target_row, feature_row in zip(dataset.subject_ids, dataset.targets, dataset.features):
            values = ["" if np.isnan(value) else f"{value:.6g}" for value in feature_row]
            writer.writerow([subject, f"{target_row[0]:.1f}", f"{target_row[1]:.1f}", *values])
    return target


def generate_synthetic_bp_dataset(
    subject_count: int = 100,
    samples_per_subject: int = 4,
    missing_ratio: float = 0.05,
    seed: int = 0,
) -> BloodPressureDataset:
    rng = np.random.default_rng(seed)
    names = BP_FEATURE_NAMES
    index = {name: position for position, name in enumerate(names)}
    sample_count = subject_count * samples_per_subject
    subjects = np.repeat(np.arange(subject_count), samples_per_subject)
    age = rng.uniform(20, 75, subject_count)[subjects]
    sex_male = rng.integers(0, 2, subject_count)[subjects].astype(float)
    bmi = rng.normal(23, 3.5, subject_count)[subjects]
    subject_offset = rng.normal(0, 6, subject_count)[subjects]
    systolic = 95 + 0.55 * age + 1.1 * (bmi - 23) + 4 * sex_male + subject_offset + rng.normal(0, 4, sample_count)
    diastolic = 62 + 0.25 * age + 0.6 * (bmi - 23) + 2 * sex_male + 0.6 * subject_offset + rng.normal(0, 3, sample_count)
    features = np.full((sample_count, len(names)), np.nan)
    for name, (mean, spread) in FEATURE_PRIORS.items():
        features[:, index[name]] = rng.normal(mean, spread, sample_count)
    stiffness = (systolic - 120) / 20
    heart_rate = 72 + rng.normal(0, 10, sample_count)
    features[:, index["heart_rate_bpm"]] = heart_rate
    features[:, index["mean_ibi_ms"]] = 60000 / heart_rate
    features[:, index["ibi_mean_ms"]] = 60000 / heart_rate
    features[:, index["fundamental_freq_hz"]] = heart_rate / 60
    features[:, index["mean_rise_time_ms"]] += -25 * stiffness
    features[:, index["mean_systolic_ratio"]] += -0.02 * stiffness
    features[:, index["aix_proxy"]] += 0.08 * stiffness
    features[:, index["apg_aging_index"]] += 0.6 * stiffness
    features[:, index["age_years"]] = age
    features[:, index["sex_male"]] = sex_male
    features[:, index["bmi"]] = bmi
    holes = rng.random(features.shape) < missing_ratio
    features[holes] = np.nan
    return BloodPressureDataset(
        features=features,
        targets=np.column_stack([systolic, diastolic]),
        subject_ids=subjects.astype(str),
        feature_names=tuple(names),
        source="synthetic",
    )
