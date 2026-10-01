from collections.abc import Sequence

import numpy as np
from scipy import signal as scipy_signal

from aivitals_engine.models.deep.specs import InputLayout, InputRepresentation, OutputKind

EPSILON = 1e-7


def resize_frame(frame: np.ndarray, size: int) -> np.ndarray:
    import cv2

    resized = cv2.resize(np.asarray(frame), (size, size), interpolation=cv2.INTER_AREA)
    return resized.astype(np.float32)


def diff_normalize(frames: np.ndarray) -> np.ndarray:
    frames = frames.astype(np.float32)
    difference = (frames[1:] - frames[:-1]) / (frames[1:] + frames[:-1] + EPSILON)
    deviation = float(np.std(difference))
    difference = difference / deviation if deviation > EPSILON else difference
    padded = np.concatenate([difference, np.zeros_like(frames[:1])], axis=0)
    return np.nan_to_num(padded)


def standardize_frames(frames: np.ndarray) -> np.ndarray:
    frames = frames.astype(np.float32)
    deviation = float(np.std(frames))
    centered = frames - float(np.mean(frames))
    return np.nan_to_num(centered / deviation if deviation > EPSILON else centered)


REPRESENTATION_BUILDERS = {
    InputRepresentation.DIFF_NORMALIZED: diff_normalize,
    InputRepresentation.STANDARDIZED: standardize_frames,
}


def build_representation(frames: np.ndarray, representations: Sequence[InputRepresentation]) -> np.ndarray:
    if frames.ndim != 4 or frames.shape[-1] != 3:
        raise ValueError("frames phải có dạng (T, H, W, 3)")
    parts = [REPRESENTATION_BUILDERS[representation](frames) for representation in representations]
    return np.concatenate(parts, axis=-1)


def to_model_layout(representation: np.ndarray, layout: InputLayout, frame_depth: int | None) -> np.ndarray:
    channels_first = np.transpose(representation, (0, 3, 1, 2))
    if layout is InputLayout.VIDEO_VOLUME:
        return np.ascontiguousarray(np.transpose(channels_first, (1, 0, 2, 3))[None])
    if frame_depth:
        usable = (channels_first.shape[0] // frame_depth) * frame_depth
        channels_first = channels_first[:usable]
    return np.ascontiguousarray(channels_first)


def restore_pulse(model_output: np.ndarray, output_kind: OutputKind) -> np.ndarray:
    pulse = np.asarray(model_output, dtype=float).reshape(-1)
    if output_kind is OutputKind.PULSE_DERIVATIVE:
        pulse = np.cumsum(pulse)
    return scipy_signal.detrend(pulse, type="linear")
