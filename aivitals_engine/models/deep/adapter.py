from collections import deque
from dataclasses import asdict
from pathlib import Path
from time import perf_counter
from typing import Any, Protocol

import numpy as np

from aivitals_engine.contracts.bvp_window import BVPWindow
from aivitals_engine.contracts.frame import FramePacket
from aivitals_engine.models.deep.preprocessing import (
    build_representation,
    resize_frame,
    restore_pulse,
    to_model_layout,
)
from aivitals_engine.models.deep.specs import DeepModelSpec

MIN_SAMPLES_FOR_RATE = 2
FPS_TOLERANCE_RATIO = 0.1
DEFAULT_STRIDE_SECONDS = 1.0


def resample_frames(frames: np.ndarray, timestamps: np.ndarray, target_fps: float) -> np.ndarray:
    count = frames.shape[0]
    uniform = timestamps[0] + np.arange(count) / target_fps
    positions = np.interp(uniform, timestamps, np.arange(count, dtype=float))
    lower = np.floor(positions).astype(int)
    upper = np.minimum(lower + 1, count - 1)
    weights = (positions - lower).reshape(-1, *([1] * (frames.ndim - 1)))
    return (1.0 - weights) * frames[lower] + weights * frames[upper]


class InferenceRunner(Protocol):
    def run(self, model_input: np.ndarray) -> np.ndarray: ...


class TorchInferenceRunner:
    def __init__(self, module, device: str | None = None) -> None:
        import torch

        self._torch = torch
        self._device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self._module = module.to(self._device).eval()

    @property
    def device(self) -> str:
        return self._device

    def run(self, model_input: np.ndarray) -> np.ndarray:
        tensor = self._torch.from_numpy(np.ascontiguousarray(model_input, dtype=np.float32)).to(self._device)
        with self._torch.inference_mode():
            output = self._module(tensor)
        if isinstance(output, (tuple, list)):
            output = output[0]
        return output.detach().float().cpu().numpy()


class OnnxInferenceRunner:
    def __init__(self, model_path: Path | str, providers: list[str] | None = None) -> None:
        import onnxruntime

        available = providers or onnxruntime.get_available_providers()
        self._session = onnxruntime.InferenceSession(str(model_path), providers=available)
        self._input_name = self._session.get_inputs()[0].name

    def run(self, model_input: np.ndarray) -> np.ndarray:
        outputs = self._session.run(None, {self._input_name: model_input.astype(np.float32)})
        return np.asarray(outputs[0])


class DeepRPPGAdapter:
    def __init__(
        self,
        spec: DeepModelSpec,
        runner: InferenceRunner,
        model_version: str = "0.0.0",
        checksum_sha256: str | None = None,
        stride_frames: int | None = None,
    ) -> None:
        self.name = spec.name
        self.version = model_version
        self._spec = spec
        self._runner = runner
        self._checksum = checksum_sha256
        self._frames: deque[np.ndarray] = deque(maxlen=spec.chunk_frames)
        self._timestamps: deque[float] = deque(maxlen=spec.chunk_frames)
        self._missing: deque[bool] = deque(maxlen=spec.chunk_frames)
        self._last_latency_ms: float | None = None
        self._stride = stride_frames or max(1, int(round(DEFAULT_STRIDE_SECONDS * spec.target_fps)))
        self._frames_since_inference = 0
        self._cached_window: BVPWindow | None = None

    @property
    def stride_frames(self) -> int:
        return self._stride

    def reset(self) -> None:
        self._frames.clear()
        self._timestamps.clear()
        self._missing.clear()
        self._last_latency_ms = None
        self._frames_since_inference = 0
        self._cached_window = None

    def update(self, frame: FramePacket) -> None:
        has_crop = frame.face_detected and frame.face_crop is not None
        if not has_crop and not self._frames:
            return
        crop = resize_frame(frame.face_crop, self._spec.frame_size) if has_crop else self._frames[-1]
        self._frames.append(crop)
        self._timestamps.append(frame.timestamp)
        self._missing.append(not has_crop)
        self._frames_since_inference += 1

    def get_signal(self) -> BVPWindow | None:
        if len(self._frames) < self._spec.chunk_frames:
            return None
        if self._cached_window is not None and self._frames_since_inference < self._stride:
            return self._cached_window
        self._cached_window = self._infer()
        self._frames_since_inference = 0
        return self._cached_window

    def _infer(self) -> BVPWindow:
        frames, sampling_rate = self._aligned_frames()
        representation = build_representation(frames, self._spec.representations)
        model_input = to_model_layout(representation, self._spec.layout, self._spec.frame_depth)
        started = perf_counter()
        output = self._runner.run(model_input)
        self._last_latency_ms = (perf_counter() - started) * 1000.0
        pulse = restore_pulse(output, self._spec.output)
        timestamps = list(self._timestamps)[-pulse.size :]
        return BVPWindow(
            samples=pulse,
            sampling_rate_hz=sampling_rate,
            start_timestamp=timestamps[0],
            method=self.name,
            method_version=self.version,
            missing_ratio=float(np.mean(self._missing)),
        )

    def _aligned_frames(self) -> tuple[np.ndarray, float]:
        frames = np.stack(self._frames)
        measured = self._sampling_rate()
        target = self._spec.target_fps
        if abs(measured - target) <= FPS_TOLERANCE_RATIO * target:
            return frames, measured
        return resample_frames(frames, np.asarray(self._timestamps), target).astype(np.float32), target

    def get_quality(self) -> float | None:
        return None

    def get_metadata(self) -> dict[str, Any]:
        spec = {key: str(value) if not isinstance(value, (int, float, type(None))) else value for key, value in asdict(self._spec).items()}
        return {
            "method": self.name,
            "version": self.version,
            "checksum_sha256": self._checksum,
            "buffered_frames": len(self._frames),
            "last_inference_latency_ms": self._last_latency_ms,
            "stride_frames": self._stride,
            "spec": spec,
        }

    def _sampling_rate(self) -> float:
        if len(self._timestamps) < MIN_SAMPLES_FOR_RATE:
            return self._spec.target_fps
        elapsed = self._timestamps[-1] - self._timestamps[0]
        if elapsed <= 0:
            return self._spec.target_fps
        return (len(self._timestamps) - 1) / elapsed
