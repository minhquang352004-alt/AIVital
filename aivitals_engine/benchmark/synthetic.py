from collections.abc import Iterator
from dataclasses import dataclass, field, replace

import numpy as np

from aivitals_engine.contracts.bvp_window import BVPWindow
from aivitals_engine.contracts.frame import FramePacket

PULSE_CHANNEL_WEIGHTS = np.array([0.33, 0.77, 0.53])
DEFAULT_SKIN_RGB = np.array([172.0, 122.0, 100.0])
DEFAULT_ROI_NAMES = ("forehead", "left_cheek", "right_cheek")
MIN_IBI_SECONDS = 0.34
MAX_IBI_SECONDS = 1.45
DICROTIC_DELAY_FRACTION = 0.38
DICROTIC_RELATIVE_AMPLITUDE = 0.35
SYSTOLIC_WIDTH_FRACTION = 0.09
DICROTIC_WIDTH_FRACTION = 0.12
ILLUMINATION_WOBBLE_HZ = 0.05
MOTION_DECAY_SECONDS = 0.6
MIN_BEATS_FOR_REFERENCE = 3


@dataclass(frozen=True)
class SyntheticScenario:
    name: str = "rest_good_light"
    heart_rate_bpm: float = 72.0
    respiratory_rate_brpm: float = 15.0
    duration_seconds: float = 40.0
    sampling_rate_hz: float = 30.0
    beat_jitter_ms: float = 25.0
    rsa_depth_ms: float = 35.0
    pulse_relative_amplitude: float = 0.006
    amplitude_modulation_depth: float = 0.2
    baseline_modulation_depth: float = 0.003
    noise_std: float = 0.15
    illumination_drift: float = 0.02
    motion_events_per_minute: float = 0.0
    motion_relative_strength: float = 0.03
    missing_frame_ratio: float = 0.0
    start_timestamp: float = 1_767_225_600.0
    roi_names: tuple[str, ...] = DEFAULT_ROI_NAMES
    seed: int = 7


@dataclass(frozen=True)
class SyntheticRecording:
    scenario: SyntheticScenario
    timestamps: np.ndarray
    roi_rgb: dict[str, np.ndarray]
    face_detected: np.ndarray
    beat_times_s: np.ndarray
    pulse_waveform: np.ndarray
    respiration: np.ndarray
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def relative_times(self) -> np.ndarray:
        return self.timestamps - self.timestamps[0]

    def beat_intervals_between(self, start_s: float, end_s: float) -> np.ndarray:
        beats = self.beat_times_s[(self.beat_times_s >= start_s) & (self.beat_times_s <= end_s)]
        return np.diff(beats) * 1000.0

    def reference_heart_rate(self, start_s: float, end_s: float) -> float | None:
        intervals = self.beat_intervals_between(start_s, end_s)
        if intervals.size < MIN_BEATS_FOR_REFERENCE:
            return None
        return float(60000.0 / np.mean(intervals))

    def reference_rmssd(self, start_s: float, end_s: float) -> float | None:
        intervals = self.beat_intervals_between(start_s, end_s)
        if intervals.size < MIN_BEATS_FOR_REFERENCE:
            return None
        return float(np.sqrt(np.mean(np.diff(intervals) ** 2)))

    def reference_sdnn(self, start_s: float, end_s: float) -> float | None:
        intervals = self.beat_intervals_between(start_s, end_s)
        if intervals.size < MIN_BEATS_FOR_REFERENCE:
            return None
        return float(np.std(intervals, ddof=1))

    def frames(self) -> Iterator[FramePacket]:
        for index, timestamp in enumerate(self.timestamps):
            roi_means = {name: values[index] for name, values in self.roi_rgb.items()}
            yield FramePacket(timestamp=float(timestamp), roi_rgb_means=roi_means, face_detected=bool(self.face_detected[index]))


def generate_beat_times(scenario: SyntheticScenario, rng: np.random.Generator) -> np.ndarray:
    mean_ibi = 60.0 / scenario.heart_rate_bpm
    respiration_hz = scenario.respiratory_rate_brpm / 60.0
    beat_times = [float(rng.uniform(0.1, mean_ibi))]
    while beat_times[-1] < scenario.duration_seconds + mean_ibi:
        phase = 2.0 * np.pi * respiration_hz * beat_times[-1]
        interval = mean_ibi + scenario.rsa_depth_ms / 1000.0 * np.sin(phase)
        interval += rng.normal(0.0, scenario.beat_jitter_ms / 1000.0)
        beat_times.append(beat_times[-1] + float(np.clip(interval, MIN_IBI_SECONDS, MAX_IBI_SECONDS)))
    return np.array(beat_times)


def synthesize_pulse_waveform(times: np.ndarray, beat_times: np.ndarray) -> np.ndarray:
    waveform = np.zeros_like(times)
    intervals = np.diff(beat_times, append=beat_times[-1] + np.mean(np.diff(beat_times)))
    for beat_time, interval in zip(beat_times, intervals):
        systolic = np.exp(-0.5 * ((times - beat_time) / (SYSTOLIC_WIDTH_FRACTION * interval)) ** 2)
        dicrotic_center = beat_time + DICROTIC_DELAY_FRACTION * interval
        dicrotic = np.exp(-0.5 * ((times - dicrotic_center) / (DICROTIC_WIDTH_FRACTION * interval)) ** 2)
        waveform += systolic + DICROTIC_RELATIVE_AMPLITUDE * dicrotic
    return (waveform - waveform.mean()) / max(waveform.std(), 1e-12)


def synthesize_motion(times: np.ndarray, scenario: SyntheticScenario, rng: np.random.Generator) -> np.ndarray:
    event_count = rng.poisson(scenario.motion_events_per_minute * scenario.duration_seconds / 60.0)
    motion = np.zeros_like(times)
    for event_time in rng.uniform(0.0, scenario.duration_seconds, size=event_count):
        strength = rng.choice([-1.0, 1.0]) * scenario.motion_relative_strength * rng.uniform(0.5, 1.0)
        after = times >= event_time
        motion[after] += strength * np.exp(-(times[after] - event_time) / MOTION_DECAY_SECONDS)
    return motion


def synthesize_illumination(times: np.ndarray, scenario: SyntheticScenario) -> np.ndarray:
    ramp = scenario.illumination_drift * times / scenario.duration_seconds
    wobble = 0.5 * scenario.illumination_drift * np.sin(2.0 * np.pi * ILLUMINATION_WOBBLE_HZ * times)
    return 1.0 + ramp + wobble


def synthesize_roi_trace(
    scenario: SyntheticScenario,
    pulse: np.ndarray,
    respiration: np.ndarray,
    common_gain: np.ndarray,
    rng: np.random.Generator,
) -> np.ndarray:
    skin = DEFAULT_SKIN_RGB * rng.uniform(0.95, 1.05, size=3)
    modulated_pulse = pulse * (1.0 + scenario.amplitude_modulation_depth * respiration)
    absorption = scenario.pulse_relative_amplitude * np.outer(modulated_pulse, PULSE_CHANNEL_WEIGHTS)
    baseline = 1.0 + scenario.baseline_modulation_depth * respiration
    trace = skin * (1.0 - absorption) * (baseline * common_gain)[:, None]
    return trace + rng.normal(0.0, scenario.noise_std, size=trace.shape)


def generate_recording(scenario: SyntheticScenario) -> SyntheticRecording:
    rng = np.random.default_rng(scenario.seed)
    sample_count = int(round(scenario.duration_seconds * scenario.sampling_rate_hz))
    times = np.arange(sample_count) / scenario.sampling_rate_hz
    beat_times = generate_beat_times(scenario, rng)
    pulse = synthesize_pulse_waveform(times, beat_times)
    respiration = np.sin(2.0 * np.pi * scenario.respiratory_rate_brpm / 60.0 * times)
    common_gain = synthesize_illumination(times, scenario) * (1.0 + synthesize_motion(times, scenario, rng))
    roi_rgb = {name: synthesize_roi_trace(scenario, pulse, respiration, common_gain, rng) for name in scenario.roi_names}
    face_detected = rng.uniform(size=sample_count) >= scenario.missing_frame_ratio
    return SyntheticRecording(
        scenario=scenario,
        timestamps=scenario.start_timestamp + times,
        roi_rgb=roi_rgb,
        face_detected=face_detected,
        beat_times_s=beat_times,
        pulse_waveform=pulse,
        respiration=respiration,
        metadata={"scenario": scenario.name, "source": "synthetic"},
    )


def build_synthetic_suite(seed: int = 7, duration_seconds: float = 60.0) -> list[SyntheticRecording]:
    base = SyntheticScenario(duration_seconds=duration_seconds, seed=seed)
    scenarios = [
        base,
        replace(base, name="low_heart_rate", heart_rate_bpm=54.0, respiratory_rate_brpm=12.0, seed=seed + 1),
        replace(base, name="high_heart_rate", heart_rate_bpm=118.0, respiratory_rate_brpm=20.0, seed=seed + 2),
        replace(base, name="low_light_noise", noise_std=0.55, pulse_relative_amplitude=0.004, seed=seed + 3),
        replace(base, name="motion_artifacts", motion_events_per_minute=12.0, seed=seed + 4),
        replace(base, name="missing_frames", missing_frame_ratio=0.15, seed=seed + 5),
    ]
    return [generate_recording(scenario) for scenario in scenarios]


def synthesize_bvp_window(
    heart_rate_bpm: float = 72.0,
    respiratory_rate_brpm: float = 15.0,
    duration_seconds: float = 40.0,
    sampling_rate_hz: float = 30.0,
    noise_std: float = 0.1,
    seed: int = 11,
    signal_quality: float | None = 0.85,
) -> tuple[BVPWindow, SyntheticRecording]:
    scenario = SyntheticScenario(
        heart_rate_bpm=heart_rate_bpm,
        respiratory_rate_brpm=respiratory_rate_brpm,
        duration_seconds=duration_seconds,
        sampling_rate_hz=sampling_rate_hz,
        seed=seed,
    )
    recording = generate_recording(scenario)
    rng = np.random.default_rng(seed + 1000)
    modulated = recording.pulse_waveform * (1.0 + scenario.amplitude_modulation_depth * recording.respiration)
    samples = modulated + rng.normal(0.0, noise_std, size=modulated.size)
    raw = samples + 0.8 * recording.respiration
    roi_samples = {name: modulated + rng.normal(0.0, noise_std * 1.5, size=modulated.size) for name in scenario.roi_names}
    window = BVPWindow(
        samples=samples,
        sampling_rate_hz=sampling_rate_hz,
        start_timestamp=scenario.start_timestamp,
        method="synthetic",
        method_version="1.0.0",
        signal_quality=signal_quality,
        raw_samples=raw,
        roi_samples=roi_samples,
    )
    return window, recording
