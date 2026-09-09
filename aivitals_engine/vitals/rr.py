"""
AIVitals Vitals Module - Respiration Rate (RR)
Theo SOURCE_AUDIT.md (Mục 8.2): rPPG-Toolbox KHÔNG trích xuất nhịp thở cho các thuật toán Unsupervised (POS, CHROM, GREEN).
File này định nghĩa Interface / Skeleton chuẩn cho Task K2.1 do Khoa phụ trách tự triển khai.
"""

from typing import Optional
import numpy as np


def calculate_respiration_rate(
    bvp_signal: np.ndarray,
    fs: float = 30.0,
    low_cutoff_hz: float = 0.15,
    high_cutoff_hz: float = 0.40
) -> float:
    """
    Ước lượng nhịp thở (Respiration Rate - breaths per minute / rpm).
    Dải tần sinh lý hô hấp thông thường: 0.15 Hz - 0.40 Hz (9 - 24 nhịp/phút).
    
    [Task K2.1 - Khoa phụ trách]: Triển khai lọc dải thông hô hấp trên sóng BVP và tìm đỉnh phổ FFT
    hoặc đếm đỉnh sóng dao động chậm RSA để ước lượng nhịp thở.
    """
    raise NotImplementedError("Khoa phụ trách triển khai calculate_respiration_rate theo Task K2.1.")
