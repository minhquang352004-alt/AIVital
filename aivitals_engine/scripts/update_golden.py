import json
from pathlib import Path

from aivitals_engine.benchmark.regression_cases import compute_all_snapshots
from aivitals_engine.version import ENGINE_VERSION
from aivitals_engine.vitals.hr import HEART_RATE_ALGORITHM
from aivitals_engine.vitals.hrv import HRV_ALGORITHM
from aivitals_engine.vitals.rr import RESPIRATORY_RATE_ALGORITHM

GOLDEN_PATH = Path(__file__).resolve().parents[2] / "tests" / "regression" / "golden_vitals.json"


def tracked_algorithms() -> dict[str, str]:
    return {algorithm.name: algorithm.version for algorithm in (HEART_RATE_ALGORITHM, HRV_ALGORITHM, RESPIRATORY_RATE_ALGORITHM)}


def main() -> int:
    payload = {"engine_version": ENGINE_VERSION, "algorithms": tracked_algorithms(), "cases": compute_all_snapshots()}
    GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Đã ghi golden snapshot: {GOLDEN_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
