from dataclasses import dataclass
from enum import StrEnum


class InputRepresentation(StrEnum):
    DIFF_NORMALIZED = "diff_normalized"
    STANDARDIZED = "standardized"


class InputLayout(StrEnum):
    FRAME_STACK = "frame_stack"
    VIDEO_VOLUME = "video_volume"


class OutputKind(StrEnum):
    PULSE_DERIVATIVE = "pulse_derivative"
    PULSE = "pulse"


class IntegrationTier(StrEnum):
    REALTIME_CANDIDATE = "realtime_candidate"
    BENCHMARK_ONLY = "benchmark_only"
    RESEARCH_ONLY = "research_only"


@dataclass(frozen=True)
class DeepModelSpec:
    name: str
    architecture: str
    representations: tuple[InputRepresentation, ...]
    layout: InputLayout
    output: OutputKind
    frame_size: int
    chunk_frames: int
    frame_depth: int | None
    target_fps: float
    compute_profile: str
    integration_tier: IntegrationTier
    integration_priority: int
    rationale: str
    reference: str

    @property
    def channel_count(self) -> int:
        return 3 * len(self.representations)

    @property
    def window_seconds(self) -> float:
        return self.chunk_frames / self.target_fps


TSCAN_SPEC = DeepModelSpec(
    name="tscan",
    architecture="TS-CAN (Temporal Shift Convolutional Attention Network)",
    representations=(InputRepresentation.DIFF_NORMALIZED, InputRepresentation.STANDARDIZED),
    layout=InputLayout.FRAME_STACK,
    output=OutputKind.PULSE_DERIVATIVE,
    frame_size=72,
    chunk_frames=180,
    frame_depth=10,
    target_fps=30.0,
    compute_profile="CNN 2D + temporal shift, chạy được CPU, GPU giúp giảm latency",
    integration_tier=IntegrationTier.REALTIME_CANDIDATE,
    integration_priority=1,
    rationale="Kiến trúc thiết kế cho on-device, xử lý theo frame nên hợp với sliding window realtime",
    reference="Liu et al., Multi-Task Temporal Shift Attention Networks for On-Device Contactless Vitals Measurement, NeurIPS 2020",
)

EFFICIENTPHYS_SPEC = DeepModelSpec(
    name="efficientphys",
    architecture="EfficientPhys (convolutional)",
    representations=(InputRepresentation.STANDARDIZED,),
    layout=InputLayout.FRAME_STACK,
    output=OutputKind.PULSE_DERIVATIVE,
    frame_size=72,
    chunk_frames=180,
    frame_depth=10,
    target_fps=30.0,
    compute_profile="CNN 2D nhẹ, không cần tiền xử lý diff riêng",
    integration_tier=IntegrationTier.REALTIME_CANDIDATE,
    integration_priority=2,
    rationale="Tiền xử lý đơn giản nhất nên dễ ghép với ROI của Khang, cần benchmark latency để xác nhận",
    reference="Liu et al., EfficientPhys: Enabling Simple, Fast and Accurate Camera-Based Cardiac Measurement, WACV 2023",
)

DEEPPHYS_SPEC = DeepModelSpec(
    name="deepphys",
    architecture="DeepPhys (motion + appearance attention)",
    representations=(InputRepresentation.DIFF_NORMALIZED, InputRepresentation.STANDARDIZED),
    layout=InputLayout.FRAME_STACK,
    output=OutputKind.PULSE_DERIVATIVE,
    frame_size=72,
    chunk_frames=180,
    frame_depth=None,
    target_fps=30.0,
    compute_profile="CNN 2D hai nhánh, chạy được CPU",
    integration_tier=IntegrationTier.BENCHMARK_ONLY,
    integration_priority=3,
    rationale="Baseline deep kinh điển, dùng làm mốc so sánh; TS-CAN là bản cải tiến trực tiếp",
    reference="Chen & McDuff, DeepPhys: Video-Based Physiological Measurement Using Convolutional Attention Networks, ECCV 2018",
)

PHYSNET_SPEC = DeepModelSpec(
    name="physnet",
    architecture="PhysNet (3D CNN spatio-temporal)",
    representations=(InputRepresentation.DIFF_NORMALIZED,),
    layout=InputLayout.VIDEO_VOLUME,
    output=OutputKind.PULSE,
    frame_size=72,
    chunk_frames=128,
    frame_depth=None,
    target_fps=30.0,
    compute_profile="3D CNN, tốn tài nguyên hơn, ưu tiên GPU",
    integration_tier=IntegrationTier.BENCHMARK_ONLY,
    integration_priority=4,
    rationale="Xử lý cả khối video nên độ trễ theo chunk lớn, phù hợp benchmark offline hơn realtime",
    reference="Yu et al., Remote Photoplethysmograph Signal Measurement from Facial Videos Using Spatio-Temporal Networks, BMVC 2019",
)

DEEP_MODEL_SPECS: dict[str, DeepModelSpec] = {
    spec.name: spec for spec in (TSCAN_SPEC, EFFICIENTPHYS_SPEC, DEEPPHYS_SPEC, PHYSNET_SPEC)
}
