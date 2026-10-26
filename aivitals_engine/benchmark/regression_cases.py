from dataclasses import replace
from typing import Any

from aivitals_engine.benchmark.synthetic import synthesize_bvp_window
from aivitals_engine.contracts.result import VitalCode
from aivitals_engine.integration.vitals_service import VitalsService

REGRESSION_CASES: dict[str, dict[str, Any]] = {
    "rest_72bpm": {"heart_rate_bpm": 72.0, "respiratory_rate_brpm": 15.0, "noise_std": 0.1, "seed": 11},
    "low_54bpm": {"heart_rate_bpm": 54.0, "respiratory_rate_brpm": 12.0, "noise_std": 0.3, "seed": 21},
    "high_118bpm": {"heart_rate_bpm": 118.0, "respiratory_rate_brpm": 20.0, "noise_std": 0.3, "seed": 31},
    "noisy_85bpm": {"heart_rate_bpm": 85.0, "respiratory_rate_brpm": 18.0, "noise_std": 1.2, "seed": 41},
    "short_12s": {"heart_rate_bpm": 66.0, "respiratory_rate_brpm": 14.0, "noise_std": 0.2, "seed": 51, "duration_seconds": 12.0},
    "low_fs_10hz": {"heart_rate_bpm": 70.0, "respiratory_rate_brpm": 15.0, "noise_std": 0.1, "seed": 61, "sampling_rate_hz": 10.0},
    "low_sqi_035": {"heart_rate_bpm": 75.0, "respiratory_rate_brpm": 16.0, "noise_std": 0.2, "seed": 71, "signal_quality": 0.35},
    "motion_high": {
        "heart_rate_bpm": 80.0,
        "respiratory_rate_brpm": 16.0,
        "noise_std": 0.2,
        "seed": 81,
        "signal_warnings": ("MOTION_HIGH", "TOO_DARK"),
    },
}

VALUE_TOLERANCES: dict[VitalCode, float] = {
    VitalCode.HEART_RATE: 0.5,
    VitalCode.HRV_RMSSD: 2.0,
    VitalCode.HRV_SDNN: 2.0,
    VitalCode.HRV_MEAN_IBI: 2.0,
    VitalCode.RESPIRATORY_RATE: 0.5,
}


def compute_regression_snapshot(case_name: str) -> dict[str, dict[str, Any]]:
    parameters = dict(REGRESSION_CASES[case_name])
    warnings = parameters.pop("signal_warnings", ())
    window, _ = synthesize_bvp_window(**parameters)
    result = VitalsService().compute(replace(window, signal_warnings=warnings), f"regression-{case_name}")
    return {
        vital.code.value: {
            "value": vital.value,
            "status": vital.status.value,
            "issues": sorted(issue.code for issue in vital.issues),
        }
        for vital in result.vitals
    }


def compute_all_snapshots() -> dict[str, dict[str, dict[str, Any]]]:
    return {name: compute_regression_snapshot(name) for name in REGRESSION_CASES}
