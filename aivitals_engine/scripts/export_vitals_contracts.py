import json
import os
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from aivitals_engine.benchmark.synthetic import synthesize_bvp_window
from aivitals_engine.contracts.result import VitalsResult
from aivitals_engine.health.risk_model import HealthRiskOutput
from aivitals_engine.integration.frontend_mapper import to_measurement_result
from aivitals_engine.integration.vitals_service import VitalsService
from aivitals_engine.models.blood_pressure.interface import BloodPressureEstimate
from aivitals_engine.models.deep.specs import DEEP_MODEL_SPECS
from aivitals_engine.quality.measurement_state import export_state_contract

SCHEMAS_DIR = Path(PROJECT_ROOT) / "aivitals_engine" / "contracts" / "schemas"
EXAMPLE_TIME = datetime(2026, 1, 1, 8, 0, 30, tzinfo=UTC)
EXAMPLE_ID = "example-session"


def build_example_result() -> VitalsResult:
    window, _ = synthesize_bvp_window(noise_std=0.1, seed=11)
    result = VitalsService(clock=lambda: EXAMPLE_TIME).compute(window, EXAMPLE_ID)
    return result.model_copy(update={"result_id": "00000000-0000-0000-0000-000000000001"})


def build_contracts() -> dict[str, object]:
    example = build_example_result()
    return {
        "vital_result.schema.json": VitalsResult.model_json_schema(),
        "blood_pressure_estimate.schema.json": BloodPressureEstimate.model_json_schema(),
        "health_risk_output.schema.json": HealthRiskOutput.model_json_schema(),
        "measurement_states.json": export_state_contract(),
        "deep_model_adapter_plan.json": [asdict(spec) for spec in DEEP_MODEL_SPECS.values()],
        "example_vitals_result.json": example.model_dump(mode="json"),
        "example_measurement_result.json": to_measurement_result(example, EXAMPLE_ID),
    }


def render(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    SCHEMAS_DIR.mkdir(parents=True, exist_ok=True)
    for file_name, payload in build_contracts().items():
        path = SCHEMAS_DIR / file_name
        path.write_text(render(payload), encoding="utf-8")
        print(f"Đã ghi {path.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
