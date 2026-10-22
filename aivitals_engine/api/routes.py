from dataclasses import asdict

from fastapi import APIRouter, Depends, Request

from aivitals_engine.api.container import ServiceContainer
from aivitals_engine.api.errors import ResourceNotFoundError
from aivitals_engine.api.responses import success_response
from aivitals_engine.api.schemas import BVPWindowRequest, ExplanationRequest, ValidationCheckRequest
from aivitals_engine.contracts.result import VitalsResult
from aivitals_engine.explanation.payload import ExplanationKind
from aivitals_engine.health.assessment import HealthAssessment
from aivitals_engine.models.blood_pressure.interface import BloodPressureEstimate
from aivitals_engine.models.registry import ModelKind, ModelStatus
from aivitals_engine.quality.measurement_state import export_state_contract
from aivitals_engine.validation.vital_validator import VitalValidator
from aivitals_engine.version import ENGINE_NAME, ENGINE_VERSION

router = APIRouter()
validator = VitalValidator()


def get_container(request: Request) -> ServiceContainer:
    return request.app.state.container


@router.get("/health")
def read_health(container: ServiceContainer = Depends(get_container)):
    data = {
        "service": ENGINE_NAME,
        "engine_version": ENGINE_VERSION,
        "explanation_enabled": container.explanation_service is not None,
        "active_sessions": len(container.vitals_service.active_sessions()),
    }
    return success_response(data, "Engine đang hoạt động")


@router.get("/contracts/vital-result-schema")
def read_vital_result_schema():
    return success_response(VitalsResult.model_json_schema(), "Lấy JSON schema kết quả vitals thành công")


@router.get("/contracts/health-assessment-schema")
def read_health_assessment_schema():
    return success_response(HealthAssessment.model_json_schema(), "Lấy JSON schema health assessment thành công")


@router.get("/contracts/blood-pressure-schema")
def read_blood_pressure_schema():
    return success_response(BloodPressureEstimate.model_json_schema(), "Lấy JSON schema ước tính huyết áp thành công")


@router.get("/contracts/measurement-states")
def read_measurement_states():
    return success_response(export_state_contract(), "Lấy state contract của quy trình đo thành công")


@router.post("/vitals/compute")
def compute_vitals(body: BVPWindowRequest, container: ServiceContainer = Depends(get_container)):
    result = container.vitals_service.compute(body.to_window(), body.session_id)
    return success_response(result, "Tính chỉ số sinh tồn thành công")


@router.delete("/vitals/sessions/{session_id}")
def reset_vitals_session(session_id: str, container: ServiceContainer = Depends(get_container)):
    if not container.vitals_service.reset_session(session_id):
        raise ResourceNotFoundError(f"Không tìm thấy phiên đo {session_id}")
    return success_response({"session_id": session_id}, "Đã xóa trạng thái phiên đo")


@router.post("/validation/check")
def check_validation(body: ValidationCheckRequest):
    outcome = validator.validate(body.to_candidate(), body.to_context())
    data = {"status": outcome.status, "issues": list(outcome.issues)}
    return success_response(data, "Kiểm tra kết quả thành công")


@router.post("/health-assessments")
def create_health_assessment(body: VitalsResult, container: ServiceContainer = Depends(get_container)):
    assessment = container.health_service.assess(body)
    return success_response(assessment, "Tạo đánh giá wellness thành công", status_code=201)


@router.post("/explanations")
def create_explanation(body: ExplanationRequest, container: ServiceContainer = Depends(get_container)):
    service = container.require_explanation_service()
    if body.kind is ExplanationKind.TREND_SUMMARY:
        response = service.summarize_trend(body.results)
    elif body.result is None:
        raise ValueError("Cần truyền result cho loại giải thích này")
    elif body.kind is ExplanationKind.QUESTION:
        response = service.answer_question(body.result, body.question or "", body.assessment)
    else:
        response = service.explain_result(body.result, body.assessment)
    return success_response(response, "Tạo phần giải thích thành công", status_code=201)


@router.get("/models")
def list_models(
    kind: ModelKind | None = None, status: ModelStatus | None = None, container: ServiceContainer = Depends(get_container)
):
    entries = container.model_registry.list_entries(kind=kind, status=status)
    return success_response(entries, "Lấy danh sách model thành công")


@router.get("/models/{name}/{version}/verify")
def verify_model(name: str, version: str, container: ServiceContainer = Depends(get_container)):
    entry = container.model_registry.get(name, version)
    container.model_registry.verify(entry)
    return success_response({"model": entry, "checksum_verified": True}, "Checksum model hợp lệ")


@router.get("/benchmark/deep-model-plan")
def read_deep_model_plan():
    from aivitals_engine.models.deep.specs import DEEP_MODEL_SPECS

    plan = sorted((asdict(spec) for spec in DEEP_MODEL_SPECS.values()), key=lambda item: item["integration_priority"])
    return success_response(plan, "Lấy kế hoạch tích hợp deep model thành công")
