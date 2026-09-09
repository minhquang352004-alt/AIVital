"""
AIVitals Validation Framework - Quality Gate & Rule Validator
Theo SOURCE_AUDIT.md: rPPG-Toolbox chỉ có các metric offline so sánh nhãn chuẩn (MAE, RMSE, Pearson),
hoàn toàn KHÔNG CÓ rule Quality Gate kiểm tra runtime.
File này định nghĩa Interface / Skeleton chuẩn cho Task K2.3 do Khoa phụ trách tự triển khai.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import numpy as np


@dataclass
class ValidationRuleResult:
    """Kết quả kiểm tra của một quy tắc (Rule)"""
    rule_name: str
    passed: bool
    message: str
    severity: str = "WARNING"  # "INFO", "WARNING", "ERROR"


@dataclass
class VitalsValidationReport:
    """Báo cáo tổng hợp kiểm thử chất lượng sinh hiệu"""
    is_valid: bool
    status: str  # "ACCEPTED", "SUSPICIOUS", "REJECTED"
    results: List[ValidationRuleResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "status": self.status,
            "rule_details": [
                {
                    "rule": r.rule_name,
                    "passed": r.passed,
                    "message": r.message,
                    "severity": r.severity
                }
                for r in self.results
            ]
        }


class VitalsValidator:
    """
    Quality Gate Framework để kiểm tra dữ liệu sinh hiệu trước khi gửi lên API / Database.
    
    [Task K2.3 - Khoa phụ trách]: Triển khai các rule kiểm tra:
    - check_physiological_range: Kiểm tra range sinh lý (HR, RR, SDNN, RMSSD).
    - check_sudden_jump: Phát hiện nhảy đột biến tức thời do nhiễu động.
    - check_signal_window: Kiểm tra missing window hoặc độ dài tín hiệu không đủ.
    """

    def __init__(self, max_hr_jump: float = 25.0):
        self.max_hr_jump = max_hr_jump

    def check_physiological_range(self, vital_name: str, value: float) -> ValidationRuleResult:
        """Kiểm tra giá trị có nằm trong phạm vi sinh lý bình thường hay không."""
        raise NotImplementedError("Khoa phụ trách triển khai check_physiological_range theo Task K2.3.")

    def check_sudden_jump(self, current_hr: float) -> ValidationRuleResult:
        """Kiểm tra hiện tượng đột biến tức thời (sudden jump) của nhịp tim giữa các cửa sổ."""
        raise NotImplementedError("Khoa phụ trách triển khai check_sudden_jump theo Task K2.3.")

    def check_signal_window(self, signal: np.ndarray, min_duration_sec: float = 4.0, fs: float = 30.0) -> ValidationRuleResult:
        """Kiểm tra độ dài cửa sổ tín hiệu BVP có bị thiếu (missing window) không."""
        raise NotImplementedError("Khoa phụ trách triển khai check_signal_window theo Task K2.3.")

    def validate_vitals(
        self,
        hr: Optional[float] = None,
        rr: Optional[float] = None,
        hrv_metrics: Optional[Dict[str, float]] = None,
        bvp_signal: Optional[np.ndarray] = None,
        fs: float = 30.0
    ) -> VitalsValidationReport:
        """
        Đánh giá tổng hợp toàn bộ các rule kiểm thử sinh hiệu.
        """
        raise NotImplementedError("Khoa phụ trách triển khai validate_vitals theo Task K2.3.")
