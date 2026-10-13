import hashlib
from collections.abc import Mapping, Sequence
from pathlib import Path

import joblib
import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from aivitals_engine.config.vitals_config import PhysiologicalRange
from aivitals_engine.contracts.result import ModelInfo, ResultStatus, ValidationIssue
from aivitals_engine.models.blood_pressure.features import BP_FEATURE_NAMES, FeatureVector, build_feature_vector
from aivitals_engine.models.blood_pressure.interface import BloodPressureEstimate, BloodPressureUse, ModelNotFittedError
from aivitals_engine.validation.issue_codes import IssueCode
from aivitals_engine.validation.rules import error, warning
from aivitals_engine.validation.vital_validator import resolve_status

BP_BASELINE_NAME = "bp_ridge_baseline"
SYSTOLIC_RANGE = PhysiologicalRange(70.0, 220.0)
DIASTOLIC_RANGE = PhysiologicalRange(40.0, 130.0)
MIN_PULSE_PRESSURE_MMHG = 10.0
MAX_MISSING_FEATURE_RATIO = 0.3
RESIDUAL_REFERENCE_MMHG = 15.0
MIN_TRAINING_SAMPLES = 10
TARGET_COLUMNS = 2
VALUE_DECIMALS = 1
CHECKSUM_CHUNK_BYTES = 1 << 20
TRAINING_RANGE_PERCENTILES = (0.0, 100.0)


def file_sha256(path: Path | str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(CHECKSUM_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def training_bounds(features: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    observed = ~np.all(np.isnan(features), axis=0)
    low = np.full(features.shape[1], -np.inf)
    high = np.full(features.shape[1], np.inf)
    low[observed], high[observed] = np.nanpercentile(features[:, observed], TRAINING_RANGE_PERCENTILES, axis=0)
    return low, high


class RidgeBloodPressureModel:
    def __init__(
        self,
        version: str = "0.1.0",
        alpha: float = 1.0,
        feature_names: Sequence[str] = BP_FEATURE_NAMES,
        product_enabled: bool = False,
        checksum_sha256: str | None = None,
    ) -> None:
        self._version = version
        self._alpha = alpha
        self._feature_names = tuple(feature_names)
        self._product_enabled = product_enabled
        self._checksum = checksum_sha256
        self._pipeline = make_pipeline(
            SimpleImputer(strategy="median", keep_empty_features=True), StandardScaler(), Ridge(alpha=alpha)
        )
        self._residual_std: np.ndarray | None = None
        self._feature_low: np.ndarray | None = None
        self._feature_high: np.ndarray | None = None

    @property
    def model_info(self) -> ModelInfo:
        return ModelInfo(name=BP_BASELINE_NAME, version=self._version, checksum_sha256=self._checksum)

    @property
    def feature_names(self) -> tuple[str, ...]:
        return self._feature_names

    @property
    def is_fitted(self) -> bool:
        return self._residual_std is not None

    def fit(self, features: np.ndarray, targets: np.ndarray) -> "RidgeBloodPressureModel":
        features = np.asarray(features, dtype=float)
        targets = np.asarray(targets, dtype=float)
        if features.ndim != 2 or features.shape[1] != len(self._feature_names):
            raise ValueError(f"features phải có dạng (n, {len(self._feature_names)})")
        if targets.shape != (features.shape[0], TARGET_COLUMNS):
            raise ValueError("targets phải có dạng (n, 2) gồm SBP và DBP")
        if features.shape[0] < MIN_TRAINING_SAMPLES:
            raise ValueError(f"Cần tối thiểu {MIN_TRAINING_SAMPLES} mẫu để huấn luyện")
        self._pipeline.fit(features, targets)
        self._feature_low, self._feature_high = training_bounds(features)
        self._residual_std = np.std(targets - self._pipeline.predict(features), axis=0)
        return self

    def predict_matrix(self, features: np.ndarray) -> np.ndarray:
        self._ensure_fitted()
        return self._pipeline.predict(np.asarray(features, dtype=float))

    def predict(self, features: Mapping[str, float | None]) -> BloodPressureEstimate:
        self._ensure_fitted()
        vector = build_feature_vector(features, self._feature_names)
        clipped, outside = self._clip_to_training_range(vector.values)
        systolic, diastolic = (float(value) for value in self._pipeline.predict(clipped[None, :])[0])
        issues = self._issues(vector, systolic, diastolic, outside)
        status = resolve_status(issues)
        is_invalid = status is ResultStatus.INVALID
        return BloodPressureEstimate(
            sbp_mmhg=None if is_invalid else round(systolic, VALUE_DECIMALS),
            dbp_mmhg=None if is_invalid else round(diastolic, VALUE_DECIMALS),
            confidence=0.0 if is_invalid else self._confidence(vector.missing_ratio),
            status=status,
            intended_use=BloodPressureUse.WELLNESS_ESTIMATE if self._product_enabled else BloodPressureUse.RESEARCH_ONLY,
            model=self.model_info,
            feature_set_version=vector.feature_set_version,
            missing_features=vector.missing_names,
            issues=issues,
        )

    def save(self, path: Path | str) -> Path:
        self._ensure_fitted()
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": self._version,
            "alpha": self._alpha,
            "feature_names": self._feature_names,
            "product_enabled": self._product_enabled,
            "pipeline": self._pipeline,
            "residual_std": self._residual_std,
            "feature_low": self._feature_low,
            "feature_high": self._feature_high,
        }
        joblib.dump(payload, target)
        return target

    @classmethod
    def load(cls, path: Path | str, checksum_sha256: str | None = None) -> "RidgeBloodPressureModel":
        if checksum_sha256 is not None and file_sha256(path) != checksum_sha256:
            raise ValueError("Checksum file model huyết áp không khớp, từ chối nạp")
        payload = joblib.load(path)
        model = cls(
            version=payload["version"],
            alpha=payload["alpha"],
            feature_names=payload["feature_names"],
            product_enabled=payload["product_enabled"],
            checksum_sha256=checksum_sha256,
        )
        model._pipeline = payload["pipeline"]
        model._residual_std = payload["residual_std"]
        model._feature_low = payload.get("feature_low")
        model._feature_high = payload.get("feature_high")
        return model

    def _ensure_fitted(self) -> None:
        if not self.is_fitted:
            raise ModelNotFittedError("Model huyết áp chưa được huấn luyện")

    def _clip_to_training_range(self, values: np.ndarray) -> tuple[np.ndarray, list[str]]:
        if self._feature_low is None or self._feature_high is None:
            return values, []
        clipped = np.clip(values, self._feature_low, self._feature_high)
        changed = ~np.isnan(values) & (clipped != values)
        return clipped, [name for name, flag in zip(self._feature_names, changed) if flag]

    def _issues(
        self, vector: FeatureVector, systolic: float, diastolic: float, outside: list[str] | None = None
    ) -> list[ValidationIssue]:
        issues = []
        if outside:
            message = "Một số đặc trưng nằm ngoài khoảng dữ liệu huấn luyện và đã được giới hạn lại"
            issues.append(warning(IssueCode.FEATURES_OUT_OF_TRAINING_RANGE, message, features=", ".join(outside)))
        if vector.missing_ratio > MAX_MISSING_FEATURE_RATIO:
            message = "Thiếu quá nhiều đặc trưng đầu vào cho model huyết áp"
            issues.append(error(IssueCode.MISSING_FEATURES, message, missing_ratio=vector.missing_ratio))
        elif vector.missing_names:
            message = "Một số đặc trưng đầu vào bị thiếu và đã được điền giá trị trung vị"
            issues.append(warning(IssueCode.MISSING_FEATURES, message, missing_ratio=vector.missing_ratio))
        if not SYSTOLIC_RANGE.contains(systolic) or not DIASTOLIC_RANGE.contains(diastolic):
            message = "Huyết áp dự đoán nằm ngoài khoảng hợp lý"
            issues.append(error(IssueCode.OUT_OF_PHYSIOLOGICAL_RANGE, message, sbp=systolic, dbp=diastolic))
        if systolic - diastolic < MIN_PULSE_PRESSURE_MMHG:
            message = "Hiệu áp dự đoán không hợp lý"
            issues.append(error(IssueCode.PULSE_PRESSURE_INVALID, message, pulse_pressure=systolic - diastolic))
        return issues

    def _confidence(self, missing_ratio: float) -> float:
        residual = float(np.mean(self._residual_std))
        score = (1.0 - missing_ratio) * np.exp(-residual / RESIDUAL_REFERENCE_MMHG)
        return round(float(np.clip(score, 0.0, 1.0)), 3)
