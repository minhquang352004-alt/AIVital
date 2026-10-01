import json
import re
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

from aivitals_engine.contracts import BVPWindow, ResultStatus, VitalCode, VitalsResult
from aivitals_engine.integration.vitals_service import VitalsService
from aivitals_engine.models.deep import (
    DEEP_MODEL_SPECS,
    InputLayout,
    IntegrationTier,
    OutputKind,
    build_representation,
    restore_pulse,
    to_model_layout,
)
from aivitals_engine.quality import MeasurementState, database_mapping
from aivitals_engine.scripts.export_vitals_contracts import SCHEMAS_DIR, build_contracts, render

REPO_ROOT = Path(__file__).resolve().parents[2]
DB_SCHEMA = REPO_ROOT / "db" / "001_week2_camera_demo.sql"
FRONTEND_CONTRACT = REPO_ROOT / "frontend" / "lib" / "api-contract.ts"


def make_window(**overrides) -> BVPWindow:
    values = dict(samples=np.zeros(300), sampling_rate_hz=30.0, start_timestamp=100.0, method="POS", method_version="1.0")
    values.update(overrides)
    return BVPWindow(**values)


def database_values(column: str) -> set[str]:
    sql = DB_SCHEMA.read_text(encoding="utf-8")
    sql = sql[sql.index("CREATE TABLE IF NOT EXISTS measurements") :]
    block = re.search(rf"\b{column} TEXT NOT NULL CHECK \({column} IN \((.*?)\)\)", sql, re.S).group(1)
    return set(re.findall(r"'([A-Z_]+)'", block))


def test_bvp_window_rejects_invalid_input():
    with pytest.raises(ValueError):
        make_window(samples=[0.0, np.nan, 1.0])
    with pytest.raises(ValueError):
        make_window(raw_samples=np.zeros(299))
    with pytest.raises(ValueError):
        make_window(missing_ratio=1.5)
    with pytest.raises(ValueError):
        make_window(sampling_rate_hz=0.0)


def test_bvp_window_tail_keeps_alignment():
    samples = np.arange(300, dtype=float)
    window = make_window(samples=samples, roi_samples={"forehead": samples * 2})
    tail = window.tail(2.0)
    assert tail.samples.size == 60
    assert tail.start_timestamp == pytest.approx(100.0 + 240 / 30)
    assert np.array_equal(tail.roi_samples["forehead"], samples[240:] * 2)
    assert window.tail(60.0) is window


def test_invalid_vital_cannot_carry_value(clean_window, fixed_clock):
    window, _ = clean_window
    vital = VitalsService(clock=fixed_clock).compute(window, "contract").find_vital(VitalCode.HEART_RATE)
    assert vital.status is not ResultStatus.INVALID
    with pytest.raises(ValidationError):
        vital.model_validate({**vital.model_dump(), "status": ResultStatus.INVALID})
    with pytest.raises(ValidationError):
        vital.model_validate({**vital.model_dump(), "unit": "ms"})


def test_exported_contract_files_are_up_to_date():
    for file_name, payload in build_contracts().items():
        path = SCHEMAS_DIR / file_name
        assert path.exists(), f"Thiếu {file_name}, chạy aivitals_engine/scripts/export_vitals_contracts.py"
        assert json.loads(path.read_text(encoding="utf-8")) == json.loads(render(payload)), file_name


def test_example_result_matches_schema():
    example = json.loads((SCHEMAS_DIR / "example_vitals_result.json").read_text(encoding="utf-8"))
    assert VitalsResult.model_validate(example).session_id == "example-session"


def test_state_machine_maps_onto_quang_database():
    allowed_states = database_values("state")
    allowed_statuses = database_values("status")
    for state in MeasurementState:
        mapping = database_mapping(state)
        assert mapping["measurements_status"] in allowed_statuses
        assert mapping["measurements_state"] is None or mapping["measurements_state"] in allowed_states
    persisted = {database_mapping(state)["measurements_state"] for state in MeasurementState} - {None}
    assert persisted == allowed_states


def test_frontend_states_are_covered():
    contract = FRONTEND_CONTRACT.read_text(encoding="utf-8")
    block = re.search(r"export type MeasurementState =(.*?);", contract, re.S).group(1)
    frontend_states = set(re.findall(r'"([A-Z_]+)"', block))
    assert frontend_states <= {state.value for state in MeasurementState}


def test_deep_model_plan_tiers():
    tiers = {name: spec.integration_tier for name, spec in DEEP_MODEL_SPECS.items()}
    assert tiers == {
        "tscan": IntegrationTier.REALTIME_CANDIDATE,
        "efficientphys": IntegrationTier.REALTIME_CANDIDATE,
        "deepphys": IntegrationTier.BENCHMARK_ONLY,
        "physnet": IntegrationTier.BENCHMARK_ONLY,
    }
    assert DEEP_MODEL_SPECS["tscan"].window_seconds == pytest.approx(6.0)


def test_deep_preprocessing_layouts():
    frames = np.random.default_rng(1).uniform(50, 200, size=(25, 8, 8, 3))
    tscan = DEEP_MODEL_SPECS["tscan"]
    representation = build_representation(frames, tscan.representations)
    assert representation.shape == (25, 8, 8, tscan.channel_count)
    assert to_model_layout(representation, InputLayout.FRAME_STACK, tscan.frame_depth).shape == (20, 6, 8, 8)
    assert to_model_layout(representation, InputLayout.VIDEO_VOLUME, None).shape == (1, 6, 25, 8, 8)
    with pytest.raises(ValueError):
        build_representation(frames[..., :2], tscan.representations)
    assert restore_pulse(np.ones(5), OutputKind.PULSE_DERIVATIVE).size == 5
