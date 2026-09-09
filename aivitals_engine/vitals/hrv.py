"""
AIVitals Vitals Module - Heart Rate Variability (HRV)
Theo SOURCE_AUDIT.md (Mục 8.1): rPPG-Toolbox hoàn toàn KHÔNG CÓ mã nguồn tính toán HRV.
File này định nghĩa Interface / Skeleton chuẩn cho Task K2.1 do Khoa phụ trách tự triển khai.
"""

from typing import Dict, Optional
import numpy as np


def extract_rr_intervals(bvp_signal: np.ndarray, fs: float = 30.0) -> np.ndarray:
    """
    Trích xuất khoảng cách giữa các đỉnh liên tiếp (IBI / RR-intervals tính bằng mili-giây).
    
    [Task K2.1 - Khoa phụ trách]: Triển khai thuật toán phát hiện đỉnh tâm thu (Systolic Peak Detection)
    và tính khoảng cách giữa các đỉnh liên tiếp: IBI_i = t_i - t_(i-1).
    """
    raise NotImplementedError("Khoa phụ trách triển khai extract_rr_intervals theo Task K2.1.")


def calculate_hrv_metrics(rr_intervals_ms: np.ndarray) -> Dict[str, float]:
    """
    Tính các chỉ số HRV miền thời gian (SDNN, RMSSD, pNN50).
    
    [Task K2.1 - Khoa phụ trách]: Triển khai công thức tính:
    - SDNN: Độ lệch chuẩn của các khoảng RR.
    - RMSSD: Căn bậc hai trung bình bình phương các hiệu số liên tiếp.
    - pNN50: Tỷ lệ phần trăm các hiệu số liên tiếp > 50ms (hoặc dùng thư viện neurokit2).
    """
    raise NotImplementedError("Khoa phụ trách triển khai calculate_hrv_metrics theo Task K2.1.")


def calculate_hrv_from_bvp(bvp_signal: np.ndarray, fs: float = 30.0) -> Dict[str, float]:
    """
    Interface hàm chuẩn tính HRV từ sóng BVP.
    
    [Task K2.1 - Khoa phụ trách]: Kết nối extract_rr_intervals -> calculate_hrv_metrics.
    """
    raise NotImplementedError("Khoa phụ trách triển khai calculate_hrv_from_bvp theo Task K2.1.")
