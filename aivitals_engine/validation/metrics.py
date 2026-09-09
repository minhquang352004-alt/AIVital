"""
AIVitals Validation Metrics Module
Đánh giá độ chính xác giữa tín hiệu/chỉ số dự đoán và nhãn chuẩn y tế (Ground Truth).
Kế thừa & tối ưu từ rPPG-Toolbox/evaluation/metrics.py
"""

from typing import Dict, Union, List
import numpy as np


def calculate_mae(predictions: np.ndarray, labels: np.ndarray) -> float:
    """Mean Absolute Error (Sai số tuyệt đối trung bình)."""
    p = np.asarray(predictions, dtype=np.float64)
    y = np.asarray(labels, dtype=np.float64)
    return float(np.mean(np.abs(p - y)))


def calculate_rmse(predictions: np.ndarray, labels: np.ndarray) -> float:
    """Root Mean Squared Error (Căn bậc hai sai số bình phương trung bình)."""
    p = np.asarray(predictions, dtype=np.float64)
    y = np.asarray(labels, dtype=np.float64)
    return float(np.sqrt(np.mean((p - y) ** 2)))


def calculate_mape(predictions: np.ndarray, labels: np.ndarray) -> float:
    """Mean Absolute Percentage Error (Tỷ lệ phần trăm sai số tuyệt đối trung bình)."""
    p = np.asarray(predictions, dtype=np.float64)
    y = np.asarray(labels, dtype=np.float64)
    non_zero = y != 0
    if not np.any(non_zero):
        return 0.0
    return float(np.mean(np.abs((p[non_zero] - y[non_zero]) / y[non_zero])) * 100.0)


def calculate_pearson(predictions: np.ndarray, labels: np.ndarray) -> float:
    """Hệ số tương quan tuyến tính Pearson (r)."""
    p = np.asarray(predictions, dtype=np.float64).flatten()
    y = np.asarray(labels, dtype=np.float64).flatten()
    if len(p) < 2 or np.std(p) == 0 or np.std(y) == 0:
        return 0.0
    corr_matrix = np.corrcoef(p, y)
    return float(corr_matrix[0, 1])


def evaluate_vital_predictions(
    predictions: Union[List[float], np.ndarray],
    ground_truth: Union[List[float], np.ndarray]
) -> Dict[str, float]:
    """
    Tính toàn bộ các chỉ số kiểm thử y tế cơ bản giữa dự đoán và nhãn tham chiếu.

    Returns:
        Dict gồm MAE, RMSE, MAPE, Pearson
    """
    p = np.asarray(predictions, dtype=np.float64)
    y = np.asarray(ground_truth, dtype=np.float64)

    return {
        "MAE": calculate_mae(p, y),
        "RMSE": calculate_rmse(p, y),
        "MAPE": calculate_mape(p, y),
        "Pearson": calculate_pearson(p, y)
    }
