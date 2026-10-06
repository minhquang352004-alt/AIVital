import csv
import json
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aivitals_engine.benchmark.metrics import ErrorMetrics, compute_error_metrics, percentile
from aivitals_engine.version import ENGINE_VERSION

STATUS_INVALID = "INVALID"
STATUS_OK = "OK"


@dataclass(frozen=True)
class WindowRecord:
    method: str
    method_version: str
    recording_id: str
    subject_id: str
    scenario: str
    window_end_s: float
    reference_hr_bpm: float | None
    estimated_hr_bpm: float | None
    hr_status: str
    hr_confidence: float
    hr_issue_codes: tuple[str, ...]
    reference_rmssd_ms: float | None
    estimated_rmssd_ms: float | None
    hrv_status: str
    reference_rr_brpm: float | None
    estimated_rr_brpm: float | None
    rr_status: str
    signal_latency_ms: float
    vitals_latency_ms: float


@dataclass(frozen=True)
class MethodSummary:
    method: str
    method_version: str
    window_count: int
    hr_coverage: float
    hr_ok_ratio: float
    mean_hr_confidence: float
    hr_accepted: ErrorMetrics
    hr_ok_only: ErrorMetrics
    rmssd: ErrorMetrics
    respiratory_rate: ErrorMetrics
    latency_ms: dict[str, float | None]
    scenarios: dict[str, dict[str, float | None]]
    issue_counts: dict[str, int]


def ratio(count: int, total: int) -> float:
    return count / total if total else 0.0


def scenario_breakdown(records: Sequence[WindowRecord], tolerance: float) -> dict[str, dict[str, float | None]]:
    breakdown = {}
    for scenario in sorted({record.scenario for record in records}):
        members = [record for record in records if record.scenario == scenario]
        accepted = [record for record in members if record.hr_status != STATUS_INVALID]
        metrics = compute_error_metrics(
            [record.reference_hr_bpm for record in accepted], [record.estimated_hr_bpm for record in accepted], tolerance
        )
        breakdown[scenario] = {
            "windows": float(len(members)),
            "hr_coverage": ratio(len(accepted), len(members)),
            "hr_mae": metrics.mae,
        }
    return breakdown


def summarize_method(records: Sequence[WindowRecord], config: Any) -> MethodSummary:
    accepted = [record for record in records if record.hr_status != STATUS_INVALID]
    ok_only = [record for record in records if record.hr_status == STATUS_OK]
    hrv_accepted = [record for record in records if record.hrv_status != STATUS_INVALID]
    rr_accepted = [record for record in records if record.rr_status != STATUS_INVALID]
    return MethodSummary(
        method=records[0].method,
        method_version=records[0].method_version,
        window_count=len(records),
        hr_coverage=ratio(len(accepted), len(records)),
        hr_ok_ratio=ratio(len(ok_only), len(records)),
        mean_hr_confidence=sum(record.hr_confidence for record in records) / len(records),
        hr_accepted=compute_error_metrics(
            [r.reference_hr_bpm for r in accepted], [r.estimated_hr_bpm for r in accepted], config.hr_tolerance_bpm
        ),
        hr_ok_only=compute_error_metrics(
            [r.reference_hr_bpm for r in ok_only], [r.estimated_hr_bpm for r in ok_only], config.hr_tolerance_bpm
        ),
        rmssd=compute_error_metrics(
            [r.reference_rmssd_ms for r in hrv_accepted], [r.estimated_rmssd_ms for r in hrv_accepted], config.rmssd_tolerance_ms
        ),
        respiratory_rate=compute_error_metrics(
            [r.reference_rr_brpm for r in rr_accepted], [r.estimated_rr_brpm for r in rr_accepted], config.rr_tolerance_brpm
        ),
        latency_ms={
            "signal_p50": percentile([r.signal_latency_ms for r in records], 50),
            "signal_p95": percentile([r.signal_latency_ms for r in records], 95),
            "vitals_p50": percentile([r.vitals_latency_ms for r in records], 50),
            "vitals_p95": percentile([r.vitals_latency_ms for r in records], 95),
        },
        scenarios=scenario_breakdown(records, config.hr_tolerance_bpm),
        issue_counts=dict(Counter(code for record in records for code in record.hr_issue_codes)),
    )


def format_number(value: float | None, digits: int = 2) -> str:
    return "—" if value is None else f"{value:.{digits}f}"


@dataclass
class BenchmarkReport:
    generated_at: str
    engine_version: str
    config: dict[str, Any]
    elapsed_seconds: float
    summaries: list[MethodSummary]
    records: list[WindowRecord] = field(default_factory=list)

    @classmethod
    def from_records(cls, records: Sequence[WindowRecord], config: Any, elapsed_seconds: float) -> "BenchmarkReport":
        methods = sorted({record.method for record in records})
        summaries = [summarize_method([r for r in records if r.method == method], config) for method in methods]
        return cls(
            generated_at=datetime.now(tz=UTC).isoformat(),
            engine_version=ENGINE_VERSION,
            config=asdict(config),
            elapsed_seconds=round(elapsed_seconds, 3),
            summaries=summaries,
            records=list(records),
        )

    def summary(self, method: str) -> MethodSummary:
        return next(summary for summary in self.summaries if summary.method == method)

    def to_dict(self, include_records: bool = True) -> dict[str, Any]:
        payload = asdict(self)
        if not include_records:
            payload.pop("records")
        return payload

    def to_markdown(self) -> str:
        lines = [
            "# Báo cáo benchmark AIVitals",
            "",
            f"- Thời điểm: {self.generated_at}",
            f"- Engine version: {self.engine_version}",
            f"- Cấu hình: {json.dumps(self.config, ensure_ascii=False)}",
            f"- Thời gian chạy: {self.elapsed_seconds} giây",
            "",
            "## Tổng hợp theo method",
            "",
            "| Method | Windows | HR coverage | HR OK | HR MAE | HR RMSE | HR ±5 bpm | Pearson r | RMSSD MAE | RR MAE | Vitals p95 (ms) |",
            "|---|---|---|---|---|---|---|---|---|---|---|",
        ]
        lines += [self._summary_row(summary) for summary in self.summaries]
        for summary in self.summaries:
            lines += ["", f"### {summary.method} theo kịch bản", "", "| Kịch bản | Windows | HR coverage | HR MAE |", "|---|---|---|---|"]
            lines += [
                f"| {name} | {int(values['windows'])} | {format_number(values['hr_coverage'])} | {format_number(values['hr_mae'])} |"
                for name, values in summary.scenarios.items()
            ]
            lines += ["", f"Mã lỗi HR: {json.dumps(summary.issue_counts, ensure_ascii=False)}"]
        return "\n".join(lines) + "\n"

    @staticmethod
    def _summary_row(summary: MethodSummary) -> str:
        return (
            f"| {summary.method} | {summary.window_count} | {format_number(summary.hr_coverage)} | "
            f"{format_number(summary.hr_ok_ratio)} | {format_number(summary.hr_accepted.mae)} | "
            f"{format_number(summary.hr_accepted.rmse)} | {format_number(summary.hr_accepted.within_tolerance_ratio)} | "
            f"{format_number(summary.hr_accepted.pearson_r)} | {format_number(summary.rmssd.mae)} | "
            f"{format_number(summary.respiratory_rate.mae)} | {format_number(summary.latency_ms['vitals_p95'])} |"
        )

    def write(self, output_dir: Path | str) -> dict[str, Path]:
        directory = Path(output_dir)
        directory.mkdir(parents=True, exist_ok=True)
        paths = {
            "json": directory / "benchmark_report.json",
            "csv": directory / "benchmark_windows.csv",
            "markdown": directory / "benchmark_report.md",
        }
        paths["json"].write_text(json.dumps(self.to_dict(include_records=False), ensure_ascii=False, indent=2), encoding="utf-8")
        paths["markdown"].write_text(self.to_markdown(), encoding="utf-8")
        self._write_csv(paths["csv"])
        return paths

    def _write_csv(self, path: Path) -> None:
        field_names = list(WindowRecord.__dataclass_fields__)
        with open(path, "w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=field_names)
            writer.writeheader()
            for record in self.records:
                row = asdict(record)
                row["hr_issue_codes"] = "|".join(record.hr_issue_codes)
                writer.writerow(row)
