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
        algorithm: Union[str, RPPGMethod]
    ) -> BVPResult:
        """
        Chạy pipeline trên mảng RGB đã có sẵn.
        Tham số algorithm có thể là tên thuật toán ('POS', 'CHROM', 'GREEN')
        hoặc bất kỳ instance nào kế thừa RPPGMethod (bao gồm cả Deep Learning Models).
        """
        preprocessed_rgb = preprocess_rgb(rgb_array)
        if isinstance(algorithm, RPPGMethod):
            algo = algorithm
            algo.fps = fs
        else:
            algo = self.get_algorithm(algorithm, fs=fs)
        
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
        algorithm: Union[str, RPPGMethod]
    ) -> BVPResult:
        """Chạy pipeline từ đường dẫn file (video hoặc CSV)"""
        rgb_array, fs = load_sample(source_path, default_fps=self.default_fps)
        return self.run_on_rgb(rgb_array, fs, algorithm)

