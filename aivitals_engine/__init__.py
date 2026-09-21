"""
AIVitals Signal & rPPG Engine
Cấu trúc chuẩn gồm 9 modules:
- face: Nhận diện khuôn mặt
- roi: Trích xuất vùng da trán / má -> vector RGB
- signal: Tiền xử lý, lọc dải thông, khử trôi, nội suy FPS, reader
- rppg: Các thuật toán rPPG (GREEN, CHROM, POS) kế thừa RPPGMethod
- vitals: Tính toán sinh hiệu (HR từ FFT & Peak)
- quality: Đánh giá chất lượng tín hiệu BVP (SNR, SQI)
- validation: Đánh giá sai số y tế so với nhãn chuẩn (MAE, RMSE, Pearson)
- models: Khung giao diện cho các mô hình Deep Learning (V2)
- config: Cấu hình tham số sinh lý
"""

from .pipeline import SignalRPPGPipeline, BVPResult, BVPStreamPacket
from .signal_pipeline_realtime import RealtimeSignalPipeline, FrameResult
from .rppg.base import RPPGMethod
from .rppg.green import GREENMethod
from .rppg.chrom import CHROMMethod
from .rppg.pos import POSMethod
from .quality.sqi import calculate_bvp_quality, calculate_bvp_snr
from .signal.reader import load_sample, load_rgb_from_csv, load_rgb_from_video
from .signal.preprocess import preprocess_rgb
from .vitals.hr import calculate_fft_hr, calculate_peak_hr
from .vitals.hrv import calculate_hrv_from_bvp
from .vitals.rr import calculate_respiration_rate
from .validation.metrics import evaluate_vital_predictions
from .validation.validator import VitalsValidator

__version__ = "1.0.0"

__all__ = [
    "RealtimeSignalPipeline",
    "FrameResult",
    "SignalRPPGPipeline",
    "BVPResult",
    "BVPStreamPacket",
    "RPPGMethod",
    "GREENMethod",
    "CHROMMethod",
    "POSMethod",
    "calculate_bvp_quality",
    "calculate_bvp_snr",
    "load_sample",
    "load_rgb_from_csv",
    "load_rgb_from_video",
    "preprocess_rgb",
    "calculate_fft_hr",
    "calculate_peak_hr",
    "calculate_hrv_from_bvp",
    "calculate_respiration_rate",
    "evaluate_vital_predictions",
    "VitalsValidator",
]
