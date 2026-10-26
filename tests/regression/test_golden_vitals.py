import json
from pathlib import Path

import pytest

from aivitals_engine.benchmark.regression_cases import REGRESSION_CASES, VALUE_TOLERANCES, compute_regression_snapshot
from aivitals_engine.contracts.result import VitalCode
from aivitals_engine.scripts.update_golden import tracked_algorithms

GOLDEN_PATH = Path(__file__).parent / "golden_vitals.json"


@pytest.fixture(scope="module")
def golden():
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


def test_golden_matches_algorithm_versions(golden):
    message = "Đổi version thuật toán thì phải chạy lại python -m aivitals_engine.scripts.update_golden và ghi release notes"
    assert golden["algorithms"] == tracked_algorithms(), message


def test_golden_covers_every_case(golden):
    assert sorted(golden["cases"]) == sorted(REGRESSION_CASES)


@pytest.mark.parametrize("case_name", sorted(REGRESSION_CASES))
def test_vitals_regression(golden, case_name):
    expected = golden["cases"][case_name]
    actual = compute_regression_snapshot(case_name)
    for code, tolerance in VALUE_TOLERANCES.items():
        expected_vital, actual_vital = expected[code.value], actual[code.value]
        assert actual_vital["status"] == expected_vital["status"], f"{case_name}/{code}"
        assert actual_vital["issues"] == expected_vital["issues"], f"{case_name}/{code}"
        if expected_vital["value"] is None:
            assert actual_vital["value"] is None, f"{case_name}/{code}"
        else:
            assert actual_vital["value"] == pytest.approx(expected_vital["value"], abs=tolerance), f"{case_name}/{code}"


def test_golden_covers_rejected_measurements(golden):
    heart_rate = {name: case[VitalCode.HEART_RATE.value] for name, case in golden["cases"].items()}
    assert heart_rate["low_fs_10hz"]["status"] == "INVALID"
    assert heart_rate["low_sqi_035"]["status"] == "INVALID"
    assert "SIGNAL_CONDITION_BLOCKING" in heart_rate["motion_high"]["issues"]
    assert "INVALID" in {case[VitalCode.HRV_RMSSD.value]["status"] for case in golden["cases"].values()}
