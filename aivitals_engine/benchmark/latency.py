from dataclasses import dataclass
from time import perf_counter

import numpy as np

from aivitals_engine.benchmark.synthetic import synthesize_bvp_window
from aivitals_engine.integration.vitals_service import VitalsService

WARMUP_ITERATIONS = 3


@dataclass(frozen=True)
class LatencyReport:
    iterations: int
    window_seconds: float
    sampling_rate_hz: float
    mean_ms: float
    p50_ms: float
    p95_ms: float
    max_ms: float


def benchmark_vitals_latency(
    iterations: int = 50, window_seconds: float = 30.0, sampling_rate_hz: float = 30.0, seed: int = 21
) -> LatencyReport:
    if iterations < 1:
        raise ValueError("iterations phải lớn hơn 0")
    window, _ = synthesize_bvp_window(duration_seconds=window_seconds, sampling_rate_hz=sampling_rate_hz, seed=seed)
    service = VitalsService()
    for index in range(WARMUP_ITERATIONS):
        service.compute(window, f"warmup-{index}")
    timings = []
    for index in range(iterations):
        started = perf_counter()
        service.compute(window, f"latency-{index}")
        timings.append((perf_counter() - started) * 1000.0)
    values = np.array(timings)
    return LatencyReport(
        iterations=iterations,
        window_seconds=window_seconds,
        sampling_rate_hz=sampling_rate_hz,
        mean_ms=round(float(values.mean()), 3),
        p50_ms=round(float(np.percentile(values, 50)), 3),
        p95_ms=round(float(np.percentile(values, 95)), 3),
        max_ms=round(float(values.max()), 3),
    )
