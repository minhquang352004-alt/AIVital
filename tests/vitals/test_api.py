import pytest
from fastapi.testclient import TestClient

from aivitals_engine.api import create_app
from aivitals_engine.api.container import ServiceContainer
from aivitals_engine.contracts.result import ResultStatus, VitalCode
from aivitals_engine.explanation.service import ExplanationService
from aivitals_engine.health.assessment import HealthAssessmentService
from aivitals_engine.integration.vitals_service import VitalsService
from aivitals_engine.models.registry import ModelKind, ModelRegistry


@pytest.fixture
def container(tmp_path, fixed_clock, fake_llm):
    llm = fake_llm("Nhịp tim của bạn là 72.0 bpm. Thông tin không thay thế chẩn đoán y khoa.")
    return ServiceContainer(
        vitals_service=VitalsService(clock=fixed_clock),
        health_service=HealthAssessmentService(clock=fixed_clock),
        model_registry=ModelRegistry(tmp_path / "models"),
        explanation_service=ExplanationService(llm, clock=fixed_clock),
    )


@pytest.fixture
def client(container):
    return TestClient(create_app(container))


def window_payload(window, session_id="api-session"):
    return {
        "session_id": session_id,
        "samples": window.samples.tolist(),
        "sampling_rate_hz": window.sampling_rate_hz,
        "start_timestamp": window.start_timestamp,
        "method": window.method,
        "method_version": window.method_version,
        "signal_quality": window.signal_quality,
        "raw_samples": window.raw_samples.tolist(),
        "roi_samples": {name: values.tolist() for name, values in window.roi_samples.items()},
    }


def test_health_endpoint(client):
    body = client.get("/api/v1/health").json()
    assert body["success"] is True
    assert body["data"]["explanation_enabled"] is True


def test_compute_vitals_endpoint(client, clean_window):
    window, _ = clean_window
    response = client.post("/api/v1/vitals/compute", json=window_payload(window))
    body = response.json()
    assert response.status_code == 200
    assert body["data"]["status"] == "OK"
    assert len(body["data"]["vitals"]) == 5
    assert client.delete("/api/v1/vitals/sessions/api-session").status_code == 200


def test_compute_vitals_rejects_invalid_input(client, clean_window):
    missing_fields = client.post("/api/v1/vitals/compute", json={"session_id": "x"})
    assert missing_fields.status_code == 400
    assert missing_fields.json()["error"] == "VALIDATION_ERROR"
    window, _ = clean_window
    mismatched = client.post("/api/v1/vitals/compute", json={**window_payload(window), "roi_samples": {"a": [1.0, 2.0]}})
    assert mismatched.status_code == 400
    assert mismatched.json()["error"] == "INVALID_INPUT"


def test_reset_unknown_session_returns_404(client):
    response = client.delete("/api/v1/vitals/sessions/unknown")
    assert response.status_code == 404
    assert response.json() == {"success": False, "error": "NOT_FOUND", "message": "Không tìm thấy phiên đo unknown"}


def test_validation_check_endpoint(client):
    payload = {"code": "heart_rate", "value": 72.0, "timestamp": 1.0, "confidence": 0.9, "window_duration_seconds": 10.0}
    assert client.post("/api/v1/validation/check", json=payload).json()["data"]["status"] == "OK"
    invalid = client.post("/api/v1/validation/check", json={**payload, "value": 250.0}).json()["data"]
    assert invalid["status"] == "INVALID"


def test_health_assessment_and_explanation_endpoints(client, make_result):
    result = make_result({VitalCode.HEART_RATE: (72.0, ResultStatus.OK)}).model_dump(mode="json")
    assessment = client.post("/api/v1/health-assessments", json=result)
    assert assessment.status_code == 201
    explanation = client.post("/api/v1/explanations", json={"kind": "report", "result": result, "assessment": assessment.json()["data"]})
    assert explanation.status_code == 201
    assert explanation.json()["data"]["guard_passed"] is True


def test_explanation_endpoint_refuses_invalid_result(client, make_result):
    result = make_result({}).model_dump(mode="json")
    response = client.post("/api/v1/explanations", json={"kind": "report", "result": result})
    assert response.status_code == 400
    assert response.json()["error"] == "RESULT_NOT_VALIDATED"


def test_explanation_unavailable_without_llm(container, make_result):
    container.explanation_service = None
    client = TestClient(create_app(container))
    result = make_result({VitalCode.HEART_RATE: (72.0, ResultStatus.OK)}).model_dump(mode="json")
    response = client.post("/api/v1/explanations", json={"kind": "report", "result": result})
    assert response.status_code == 503
    assert response.json()["error"] == "SERVICE_UNAVAILABLE"


def test_models_endpoints(client, container):
    artifact = container.model_registry.root / "artifacts" / "tscan.pt"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"weights")
    container.model_registry.register("tscan", "1.0.0", ModelKind.RPPG_DEEP, artifact)
    assert len(client.get("/api/v1/models", params={"kind": "rppg_deep"}).json()["data"]) == 1
    assert client.get("/api/v1/models/tscan/1.0.0/verify").json()["data"]["checksum_verified"] is True
    missing = client.get("/api/v1/models/tscan/9.9.9/verify")
    assert missing.status_code == 404
    artifact.write_bytes(b"tampered")
    assert client.get("/api/v1/models/tscan/1.0.0/verify").status_code == 409


def test_contract_endpoints_and_unknown_route(client):
    states = client.get("/api/v1/contracts/measurement-states").json()["data"]
    assert "RESULT_READY" in states["states"]
    assert "properties" in client.get("/api/v1/contracts/vital-result-schema").json()["data"]
    assert "properties" in client.get("/api/v1/contracts/blood-pressure-schema").json()["data"]
    plan = client.get("/api/v1/benchmark/deep-model-plan").json()["data"]
    assert [item["name"] for item in plan][0] == "tscan"
    unknown = client.get("/api/v1/unknown")
    assert unknown.status_code == 404
    assert unknown.json()["success"] is False


def test_compute_vitals_forwards_signal_warnings(client, clean_window):
    window, _ = clean_window
    payload = {**window_payload(window, "api-motion"), "signal_warnings": ["MOTION_HIGH"]}
    heart_rate = client.post("/api/v1/vitals/compute", json=payload).json()["data"]["vitals"][0]
    assert heart_rate["status"] == "BAD"
    assert [issue["code"] for issue in heart_rate["issues"]] == ["SIGNAL_CONDITION_BLOCKING"]


def test_compute_vitals_low_sampling_rate_returns_invalid_result(client):
    payload = {
        "session_id": "api-low-fs",
        "samples": [float(value) for value in range(400)],
        "sampling_rate_hz": 5.0,
        "start_timestamp": 0.0,
        "method": "POS",
        "method_version": "1.0",
    }
    response = client.post("/api/v1/vitals/compute", json=payload)
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "INVALID"


def test_compute_vitals_limits_signal_warnings(client, clean_window):
    window, _ = clean_window
    payload = {**window_payload(window), "signal_warnings": ["TOO_DARK"] * 33}
    assert client.post("/api/v1/vitals/compute", json=payload).status_code == 400


def test_validation_check_accepts_signal_warnings(client):
    payload = {"code": "heart_rate", "value": 72.0, "timestamp": 1.0, "confidence": 0.9, "window_duration_seconds": 10.0}
    data = client.post("/api/v1/validation/check", json={**payload, "signal_warnings": ["FACE_NOT_FOUND"]}).json()["data"]
    assert data["status"] == "BAD"
