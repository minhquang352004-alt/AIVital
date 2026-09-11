import os
from dataclasses import dataclass
from typing import Dict, Any, Optional, Union
import numpy as np
import pandas as pd

from aivitals_engine.config.settings import RPPGAlgorithm
from aivitals_engine.signal.reader import load_sample
from aivitals_engine.signal.preprocess import preprocess_rgb
from aivitals_engine.rppg.base import RPPGMethod
from aivitals_engine.rppg.green import GREENMethod
from aivitals_engine.rppg.chrom import CHROMMethod
from aivitals_engine.rppg.pos import POSMethod

@dataclass
class BVPStreamPacket:
    """
    Data Contract gói dữ liệu BVP thời gian thực bàn giao cho module Vitals.
    Sliding window chuẩn 8.0 giây (~240 mẫu ở 30 FPS).
    """
    bvp_signal: np.ndarray    # Mảng 1D BVP đã lọc (độ dài ~240 mẫu ở 8s @ 30 FPS)
    fps: float = 30.0         # Tần số lấy mẫu thực tế/chuẩn hóa
    quality_sqi: float = 1.0  # Điểm tin cậy tín hiệu (0.0 - 1.0)
    status: str = "OK"        # "OK" | "BUFFERING" | "FACE_LOST" | "LOW_QUALITY"
    progress: float = 1.0     # Tiến độ nạp đủ buffer ban đầu (0.0 -> 1.0)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bvp_signal": self.bvp_signal.tolist() if isinstance(self.bvp_signal, np.ndarray) else list(self.bvp_signal),
            "fps": self.fps,
            "quality_sqi": self.quality_sqi,
            "status": self.status,
            "progress": self.progress
        }

@dataclass
class BVPResult:
    """Kết quả đầu ra của module Signal / rPPG"""
    method: str
    version: str
    sampling_rate: int
    signal_length: int
    quality: float
    bvp_signal: np.ndarray

    def to_metadata(self) -> Dict[str, Any]:
        return {
            "method": self.method,
            "version": self.version,
            "sampling_rate": self.sampling_rate,
            "signal_length": self.signal_length,
            "quality": self.quality
        }

    def to_stream_packet(self, window_sec: float = 8.0, status_override: Optional[str] = None) -> BVPStreamPacket:
        """
        Chuyển đổi kết quả BVP sang gói dữ liệu chuẩn BVPStreamPacket bàn giao cho module Vitals.
        Lấy cửa sổ window_sec gần nhất (mặc định 8.0s ~ 240 mẫu ở 30 FPS).
        """
        target_len = int(round(self.sampling_rate * window_sec))
        sig_len = len(self.bvp_signal)

        if sig_len == 0:
            return BVPStreamPacket(
                bvp_signal=np.array([], dtype=np.float64),
                fps=float(self.sampling_rate),
                quality_sqi=0.0,
                status="BUFFERING",
                progress=0.0
            )

        if sig_len >= target_len:
            packet_signal = self.bvp_signal[-target_len:]
            progress = 1.0
            status = "LOW_QUALITY" if self.quality < 0.40 else "OK"
        else:
            packet_signal = self.bvp_signal
            progress = round(sig_len / target_len, 2)
            status = "BUFFERING"

        if status_override is not None:
            status = status_override

        return BVPStreamPacket(
            bvp_signal=packet_signal,
            fps=float(self.sampling_rate),
            quality_sqi=float(self.quality),
            status=status,
            progress=float(progress)
        )

    def save_csv(self, output_path: str) -> str:
        """Lưu chuỗi sóng BVP ra file CSV"""
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        df = pd.DataFrame({
            "sample_index": np.arange(len(self.bvp_signal)),
            "bvp": self.bvp_signal
        })
        df.to_csv(output_path, index=False)
        return output_path

class SignalRPPGPipeline:
    """
    Pipeline thực thi Signal / rPPG:
    Input (Video / RGB) -> Signal Extraction -> Preprocessing -> rPPG (GREEN/CHROM/POS/Deep Model) -> BVP -> Quality -> Metadata
    """

    def __init__(self, fps: Optional[float] = None):
        self.default_fps = fps or 30.0

    def get_algorithm(self, name: str, fs: float) -> RPPGMethod:
        upper = name.upper()
        if upper == "POS":
            return POSMethod(fps=fs)
        elif upper == "CHROM":
            return CHROMMethod(fps=fs)
        elif upper == "GREEN":
            return GREENMethod(fps=fs)
        else:
            raise ValueError(f"Thuật toán không được hỗ trợ: {name}. Chọn 'GREEN', 'CHROM', hoặc 'POS'.")

    def run_on_rgb(
        self,
        rgb_array: np.ndarray,
        fs: float,
        algorithm: Optional[Union[str, RPPGMethod]] = None,
        algorithm_name: Optional[Union[str, RPPGMethod]] = None
    ) -> BVPResult:
        """
        Chạy pipeline trên mảng RGB đã có sẵn.
        Tham số algorithm (hoặc algorithm_name) có thể là tên thuật toán ('POS', 'CHROM', 'GREEN')
        hoặc bất kỳ instance nào kế thừa RPPGMethod (bao gồm cả Deep Learning Models).
        """
        algo_choice = algorithm if algorithm is not None else algorithm_name
        if algo_choice is None:
            algo_choice = "POS"

        preprocessed_rgb = preprocess_rgb(rgb_array)
        if isinstance(algo_choice, RPPGMethod):
            algo = algo_choice
            algo.fps = fs
        else:
            algo = self.get_algorithm(algo_choice, fs=fs)
        
        algo.reset()
        algo.update(preprocessed_rgb)
        bvp = algo.get_signal()
        quality = algo.get_quality()
        meta = algo.get_metadata()

        return BVPResult(
            method=meta["method"],
            version=meta["version"],
            sampling_rate=meta["sampling_rate"],
            signal_length=meta["signal_length"],
            quality=meta["quality"],
            bvp_signal=bvp
        )

    def run_on_file(
        self,
        source_path: str,
        algorithm: Optional[Union[str, RPPGMethod]] = None,
        algorithm_name: Optional[Union[str, RPPGMethod]] = None
    ) -> BVPResult:
        """Chạy pipeline từ đường dẫn file (video hoặc CSV)"""
        algo_choice = algorithm if algorithm is not None else algorithm_name
        if algo_choice is None:
            algo_choice = "POS"
        rgb_array, fs = load_sample(source_path, default_fps=self.default_fps)
        return self.run_on_rgb(rgb_array, fs, algorithm=algo_choice)

