from collections.abc import Callable, Sequence
from datetime import datetime
from uuid import uuid4

from pydantic import Field

from aivitals_engine.contracts.result import ContractModel, VitalsResult
from aivitals_engine.explanation.guard import GuardViolation, OutputGuard
from aivitals_engine.explanation.llm_client import LLMClient
from aivitals_engine.explanation.payload import (
    ExplanationKind,
    ExplanationPayload,
    build_result_payload,
    build_trend_payload,
)
from aivitals_engine.explanation.prompts import SYSTEM_PROMPT_VI, build_user_prompt
from aivitals_engine.health.assessment import HealthAssessment
from aivitals_engine.integration.result_builder import utc_now

MAX_QUESTION_LENGTH = 500
DEFAULT_DISCLAIMER = (
    "Thông tin chỉ mang tính tham khảo cho mục đích wellness, không phải chẩn đoán y khoa "
    "và không thay thế thiết bị hoặc chuyên gia y tế."
)
FALLBACK_TEXT = (
    "Hệ thống chưa tạo được phần giải thích tự động an toàn cho kết quả này. "
    "Vui lòng xem trực tiếp các chỉ số đã được kiểm tra chất lượng."
)


class ExplanationResponse(ContractModel):
    explanation_id: str = Field(default_factory=lambda: str(uuid4()))
    kind: ExplanationKind
    source_result_ids: list[str]
    text: str
    guard_passed: bool
    violations: list[GuardViolation]
    llm_model: str | None
    created_at: datetime
    disclaimer: str


class ExplanationService:
    def __init__(
        self,
        client: LLMClient,
        guard: OutputGuard | None = None,
        disclaimer: str = DEFAULT_DISCLAIMER,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._client = client
        self._guard = guard or OutputGuard()
        self._disclaimer = disclaimer
        self._clock = clock

    def explain_result(self, result: VitalsResult, assessment: HealthAssessment | None = None) -> ExplanationResponse:
        return self._generate(ExplanationKind.REPORT, build_result_payload(result, assessment))

    def answer_question(
        self, result: VitalsResult, question: str, assessment: HealthAssessment | None = None
    ) -> ExplanationResponse:
        cleaned = question.strip()
        if not cleaned or len(cleaned) > MAX_QUESTION_LENGTH:
            raise ValueError(f"Câu hỏi phải có từ 1 đến {MAX_QUESTION_LENGTH} ký tự")
        return self._generate(ExplanationKind.QUESTION, build_result_payload(result, assessment), cleaned)

    def summarize_trend(self, results: Sequence[VitalsResult]) -> ExplanationResponse:
        return self._generate(ExplanationKind.TREND_SUMMARY, build_trend_payload(results))

    def _generate(
        self, kind: ExplanationKind, payload: ExplanationPayload, question: str | None = None
    ) -> ExplanationResponse:
        completion = self._client.complete(SYSTEM_PROMPT_VI, build_user_prompt(kind, payload.data, question))
        guard_result = self._guard.check(completion.text, payload.allowed_numbers)
        return ExplanationResponse(
            kind=kind,
            source_result_ids=list(payload.source_result_ids),
            text=completion.text.strip() if guard_result.passed else FALLBACK_TEXT,
            guard_passed=guard_result.passed,
            violations=list(guard_result.violations),
            llm_model=completion.model,
            created_at=self._clock(),
            disclaimer=self._disclaimer,
        )
