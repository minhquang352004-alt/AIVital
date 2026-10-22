import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import Field

from aivitals_engine.contracts.result import (
    ContractModel,
    ModelInfo,
    ResultStatus,
    VitalCode,
    VitalsResult,
    VitalValue,
)
from aivitals_engine.health.risk_model import EvidenceLevel
from aivitals_engine.integration.result_builder import utc_now

DEFAULT_KNOWLEDGE_PATH = Path(__file__).parent / "knowledge" / "health_findings_vi.json"
WELLNESS_RULESET = ModelInfo(name="wellness_rules", version="0.1.0")


class FindingSeverity(StrEnum):
    INFO = "info"
    ATTENTION = "attention"


class FindingKnowledge(ContractModel):
    severity: FindingSeverity
    evidence_level: EvidenceLevel
    interpretation: str
    caution: str


class HealthKnowledge(ContractModel):
    knowledge_version: str
    review_status: str
    reviewer_role: str
    disclaimer: str
    findings: dict[str, FindingKnowledge]


class HealthFinding(ContractModel):
    code: str
    metric: VitalCode
    observed_value: float
    unit: str
    severity: FindingSeverity
    evidence_level: EvidenceLevel
    interpretation: str
    caution: str


class HealthAssessment(ContractModel):
    assessment_id: str = Field(default_factory=lambda: str(uuid4()))
    source_result_id: str
    created_at: datetime
    intended_use: Literal["wellness_screening_assist"] = "wellness_screening_assist"
    is_diagnosis: Literal[False] = False
    ruleset: ModelInfo
    knowledge_version: str
    review_status: str
    findings: list[HealthFinding]
    excluded_metrics: list[VitalCode]
    disclaimer: str


@dataclass(frozen=True)
class RangeRule:
    metric: VitalCode
    low: float
    high: float
    below_code: str
    within_code: str
    above_code: str

    def finding_code(self, value: float) -> str:
        if value < self.low:
            return self.below_code
        if value > self.high:
            return self.above_code
        return self.within_code


DEFAULT_RANGE_RULES: tuple[RangeRule, ...] = (
    RangeRule(
        VitalCode.HEART_RATE,
        60.0,
        100.0,
        "resting_heart_rate_below_typical_range",
        "resting_heart_rate_within_typical_range",
        "resting_heart_rate_above_typical_range",
    ),
    RangeRule(
        VitalCode.RESPIRATORY_RATE,
        12.0,
        20.0,
        "respiratory_rate_below_typical_range",
        "respiratory_rate_within_typical_range",
        "respiratory_rate_above_typical_range",
    ),
)

CONTEXT_FINDINGS: dict[VitalCode, str] = {VitalCode.HRV_RMSSD: "hrv_single_measurement_context"}


def load_health_knowledge(path: Path | str = DEFAULT_KNOWLEDGE_PATH) -> HealthKnowledge:
    return HealthKnowledge.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))


class HealthAssessmentService:
    def __init__(
        self,
        knowledge: HealthKnowledge | None = None,
        rules: Sequence[RangeRule] = DEFAULT_RANGE_RULES,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._knowledge = knowledge or load_health_knowledge()
        self._rules = tuple(rules)
        self._clock = clock
        self._check_knowledge_coverage()

    @property
    def knowledge(self) -> HealthKnowledge:
        return self._knowledge

    def assess(self, result: VitalsResult) -> HealthAssessment:
        accepted = {vital.code: vital for vital in result.accepted_vitals()}
        findings = [
            self._finding(rule.finding_code(accepted[rule.metric].value), accepted[rule.metric])
            for rule in self._rules
            if rule.metric in accepted
        ]
        findings += [self._finding(code, accepted[metric]) for metric, code in CONTEXT_FINDINGS.items() if metric in accepted]
        return HealthAssessment(
            source_result_id=result.result_id,
            created_at=self._clock(),
            ruleset=WELLNESS_RULESET,
            knowledge_version=self._knowledge.knowledge_version,
            review_status=self._knowledge.review_status,
            findings=findings,
            excluded_metrics=[vital.code for vital in result.vitals if vital.status is not ResultStatus.OK],
            disclaimer=self._knowledge.disclaimer,
        )

    def _finding(self, code: str, vital: VitalValue) -> HealthFinding:
        knowledge = self._knowledge.findings[code]
        return HealthFinding(
            code=code,
            metric=vital.code,
            observed_value=vital.value,
            unit=vital.unit,
            severity=knowledge.severity,
            evidence_level=knowledge.evidence_level,
            interpretation=knowledge.interpretation,
            caution=knowledge.caution,
        )

    def _check_knowledge_coverage(self) -> None:
        required = {code for rule in self._rules for code in (rule.below_code, rule.within_code, rule.above_code)}
        required |= set(CONTEXT_FINDINGS.values())
        missing = sorted(required - set(self._knowledge.findings))
        if missing:
            raise ValueError(f"Knowledge base thiếu nội dung cho các finding: {', '.join(missing)}")
