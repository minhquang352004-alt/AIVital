from dataclasses import dataclass
from enum import Enum

class RPPGAlgorithm(str, Enum):
    GREEN = "GREEN"
    CHROM = "CHROM"
    POS = "POS"

@dataclass
class SignalConfig:
    fps: float = 30.0
    window_sec: float = 1.6          # Cửa sổ phân tích mặc định (1.6s cho POS/CHROM)
    detrend_lambda: float = 100.0    # Hệ số làm trơn khử trôi đường đẳng điện
    low_cutoff_hz: float = 0.75      # Tần số cắt thấp (0.75 Hz)
    high_cutoff_hz: float = 2.50     # Tần số cắt cao (2.5 Hz)

@dataclass
class ROIConfig:
    crop_forehead: bool = True
    crop_cheeks: bool = True
