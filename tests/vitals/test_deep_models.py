import numpy as np
import pytest

from aivitals_engine.contracts.frame import FramePacket
from aivitals_engine.models.deep.preprocessing import (
    build_representation,
    diff_normalize,
    restore_pulse,
    to_model_layout,
)
from aivitals_engine.models.deep.specs import (
    DEEP_MODEL_SPECS,
    PHYSNET_SPEC,
    TSCAN_SPEC,
    InputLayout,
    IntegrationTier,
    OutputKind,
)
from aivitals_engine.vitals.hr import HeartRateEstimator

pytest.importorskip("cv2")

from aivitals_engine.models.deep.adapter import DeepRPPGAdapter


class SineDerivativeRunner:
    def __init__(self, frequency_hz: float, fps: float) -> None:
        self.frequency_hz = frequency_hz
        self.fps = fps
        self.input_shapes = []

    def run(self, model_input: np.ndarray) -> np.ndarray:
        self.input_shapes.append(model_input.shape)
        times = np.arange(model_input.shape[0]) / self.fps
        pulse = np.sin(2 * np.pi * self.frequency_hz * times)
        return np.diff(pulse, prepend=pulse[0])[:, None]


def random_frames(count: int, size: int = 8) -> np.ndarray:
    return np.random.default_rng(0).uniform(50, 200, size=(count, size, size, 3))


def test_diff_normalize_shape_and_padding():
    output = diff_normalize(random_frames(10))
    assert output.shape == (10, 8, 8, 3)
    assert np.all(output[-1] == 0)


def test_representation_and_layouts():
    representation = build_representation(random_frames(185), TSCAN_SPEC.representations)
    assert representation.shape[-1] == TSCAN_SPEC.channel_count == 6
    assert to_model_layout(representation, InputLayout.FRAME_STACK, 10).shape == (180, 6, 8, 8)
    volume = build_representation(random_frames(128), PHYSNET_SPEC.representations)
    assert to_model_layout(volume, InputLayout.VIDEO_VOLUME, None).shape == (1, 3, 128, 8, 8)
    with pytest.raises(ValueError):
        build_representation(np.zeros((4, 8, 8)), TSCAN_SPEC.representations)


def test_restore_pulse_integrates_derivative():
    times = np.arange(300) / 30.0
    pulse = np.sin(2 * np.pi * 1.2 * times)
    restored = restore_pulse(np.diff(pulse, prepend=pulse[0]), OutputKind.PULSE_DERIVATIVE)
    assert np.corrcoef(restored, pulse)[0, 1] > 0.99


def test_specs_have_unique_priorities():
    priorities = [spec.integration_priority for spec in DEEP_MODEL_SPECS.values()]
    assert sorted(priorities) == [1, 2, 3, 4]
    assert DEEP_MODEL_SPECS["tscan"].integration_tier is IntegrationTier.REALTIME_CANDIDATE
    assert TSCAN_SPEC.window_seconds == pytest.approx(6.0)


def feed_frames(adapter: DeepRPPGAdapter, count: int, missing_every: int | None = None) -> None:
    rng = np.random.default_rng(1)
    for index in range(count):
        missing = missing_every is not None and index > 0 and index % missing_every == 0
        crop = None if missing else rng.integers(0, 255, size=(96, 96, 3), dtype=np.uint8)
        adapter.update(FramePacket(timestamp=1000.0 + index / 30.0, face_detected=not missing, face_crop=crop))


def test_deep_adapter_produces_bvp_window():
    runner = SineDerivativeRunner(1.5, 30.0)
    adapter = DeepRPPGAdapter(TSCAN_SPEC, runner, model_version="1.0.0", checksum_sha256="a" * 64)
    feed_frames(adapter, 200)
    window = adapter.get_signal()
    assert runner.input_shapes[-1] == (180, 6, 72, 72)
    assert window.samples.size == 180
    assert window.sampling_rate_hz == pytest.approx(30.0)
    assert HeartRateEstimator().estimate(window).bpm == pytest.approx(90.0, abs=2.0)
    metadata = adapter.get_metadata()
    assert metadata["last_inference_latency_ms"] is not None
    assert metadata["checksum_sha256"] == "a" * 64


def test_deep_adapter_waits_for_full_chunk_and_tracks_missing_frames():
    adapter = DeepRPPGAdapter(TSCAN_SPEC, SineDerivativeRunner(1.5, 30.0))
    feed_frames(adapter, 10)
    assert adapter.get_signal() is None
    adapter.reset()
    feed_frames(adapter, 180, missing_every=10)
    assert adapter.get_signal().missing_ratio == pytest.approx(17 / 180)


def test_torch_runner_executes_module():
    torch = pytest.importorskip("torch")
    from aivitals_engine.models.deep.adapter import TorchInferenceRunner

    class MeanHead(torch.nn.Module):
        def forward(self, frames):
            return frames.mean(dim=(1, 2, 3)).unsqueeze(1)

    runner = TorchInferenceRunner(MeanHead(), device="cpu")
    output = runner.run(np.ones((20, 6, 72, 72), dtype=np.float32))
    assert output.shape == (20, 1)
    assert np.allclose(output, 1.0)
