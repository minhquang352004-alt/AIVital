import json
from datetime import timedelta

import httpx
import pytest

from aivitals_engine.contracts.result import ResultStatus, VitalCode
from aivitals_engine.explanation import (
    ExplanationService,
    GuardViolation,
    LLMConfigurationError,
    LLMRequestError,
    OpenAIChatClient,
    ResultNotValidatedError,
    build_result_payload,
)
from aivitals_engine.explanation.service import FALLBACK_TEXT
from aivitals_engine.health import HealthAssessmentService, load_health_knowledge

OK = ResultStatus.OK


def test_health_assessment_flags_high_heart_rate(make_result, fixed_clock):
    result = make_result({VitalCode.HEART_RATE: (112.0, OK), VitalCode.RESPIRATORY_RATE: (16.0, OK), VitalCode.HRV_RMSSD: (35.0, OK)})
    assessment = HealthAssessmentService(clock=fixed_clock).assess(result)
    assert {finding.code for finding in assessment.findings} == {
        "resting_heart_rate_above_typical_range",
        "respiratory_rate_within_typical_range",
        "hrv_single_measurement_context",
    }
    assert assessment.is_diagnosis is False
    assert assessment.source_result_id == result.result_id


def test_health_assessment_excludes_unvalidated_metrics(make_result):
    result = make_result({VitalCode.HEART_RATE: (130.0, ResultStatus.BAD), VitalCode.RESPIRATORY_RATE: (25.0, OK)})
    assessment = HealthAssessmentService().assess(result)
    assert [finding.metric for finding in assessment.findings] == [VitalCode.RESPIRATORY_RATE]
    assert VitalCode.HEART_RATE in assessment.excluded_metrics


def test_knowledge_coverage_is_enforced():
    knowledge = load_health_knowledge()
    with pytest.raises(ValueError):
        HealthAssessmentService(knowledge=knowledge.model_copy(update={"findings": {}}))


def test_payload_contains_only_validated_values(make_result):
    result = make_result({VitalCode.HEART_RATE: (72.0, OK), VitalCode.RESPIRATORY_RATE: (30.0, ResultStatus.BAD)})
    payload = build_result_payload(result)
    assert [item["metric"] for item in payload.data["vitals"]] == ["heart_rate"]
    assert "respiratory_rate" in payload.data["unavailable_metrics"]
    assert payload.allowed_numbers == (72.0,)


def test_invalid_result_is_refused(make_result):
    with pytest.raises(ResultNotValidatedError):
        build_result_payload(make_result({}))


def test_explanation_passes_guard(make_result, fake_llm, fixed_clock):
    result = make_result({VitalCode.HEART_RATE: (72.0, OK)})
    assessment = HealthAssessmentService().assess(result)
    llm = fake_llm("Nhịp tim của bạn là 72.0 bpm, trong khoảng thường gặp 60–100 nhịp/phút. Kết quả không thay thế chẩn đoán y khoa.")
    response = ExplanationService(llm, clock=fixed_clock).explain_result(result, assessment)
    assert response.guard_passed
    assert response.text.startswith("Nhịp tim của bạn là 72.0 bpm")
    assert '"value": 72.0' in llm.calls[0][1]


def test_explanation_blocks_invented_numbers(make_result, fake_llm):
    result = make_result({VitalCode.HEART_RATE: (72.0, OK)})
    response = ExplanationService(fake_llm("Nhịp tim của bạn là 95 bpm.")).explain_result(result)
    assert not response.guard_passed
    assert response.text == FALLBACK_TEXT
    assert response.violations == [GuardViolation.UNVERIFIED_NUMBER]


def test_explanation_blocks_diagnosis(make_result, fake_llm):
    result = make_result({VitalCode.HEART_RATE: (72.0, OK)})
    response = ExplanationService(fake_llm("Bạn bị rối loạn nhịp tim.")).explain_result(result)
    assert GuardViolation.DIAGNOSTIC_CLAIM in response.violations


def test_question_length_is_limited(make_result, fake_llm):
    result = make_result({VitalCode.HEART_RATE: (72.0, OK)})
    service = ExplanationService(fake_llm("Không đủ dữ liệu."))
    with pytest.raises(ValueError):
        service.answer_question(result, "   ")
    assert service.answer_question(result, "Nhịp tim có ổn không?").kind == "question"


def test_trend_summary_uses_deterministic_statistics(make_result, fake_llm, fixed_time):
    results = [
        make_result({VitalCode.HEART_RATE: (value, OK)}, created_at=fixed_time + timedelta(days=index))
        for index, value in enumerate([70.0, 74.0, 78.0])
    ]
    llm = fake_llm("Nhịp tim trung bình 74.0 bpm, dao động từ 70.0 đến 78.0 bpm.")
    response = ExplanationService(llm).summarize_trend(results)
    assert response.guard_passed
    assert len(response.source_result_ids) == 3
    with pytest.raises(ResultNotValidatedError):
        ExplanationService(llm).summarize_trend(results[:1])


def test_openai_client_sends_request():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers["Authorization"]
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"model": "gpt-5.4-nano", "choices": [{"message": {"content": "Xin chào"}}]})

    client = OpenAIChatClient(api_key="test-key", transport=httpx.MockTransport(handler))
    completion = client.complete("system", "user")
    assert completion.text == "Xin chào"
    assert captured["authorization"] == "Bearer test-key"
    assert [message["role"] for message in captured["body"]["messages"]] == ["system", "user"]
    assert captured["body"]["model"] == "gpt-5.4-nano"
    assert captured["body"]["reasoning_effort"] == "low"
    assert "temperature" not in captured["body"]


def test_openai_client_reads_compatible_provider_settings(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "llama-3.3-70b")
    monkeypatch.setenv("OPENAI_REASONING_EFFORT", "")
    monkeypatch.setenv("OPENAI_TEMPERATURE", "0.2")
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": "Xin chào"}}]})

    client = OpenAIChatClient.from_environment(transport=httpx.MockTransport(handler))
    assert client.complete("system", "user").model == "llama-3.3-70b"
    assert captured["body"]["temperature"] == 0.2
    assert "reasoning_effort" not in captured["body"]


def test_openai_client_errors(monkeypatch):
    failing = OpenAIChatClient(api_key="k", transport=httpx.MockTransport(lambda request: httpx.Response(500)))
    with pytest.raises(LLMRequestError):
        failing.complete("system", "user")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(LLMConfigurationError):
        OpenAIChatClient.from_environment()
