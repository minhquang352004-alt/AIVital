import os
from dataclasses import dataclass

from aivitals_engine.explanation.llm_client import LLMConfigurationError, OpenAIChatClient
from aivitals_engine.explanation.service import ExplanationService
from aivitals_engine.health.assessment import HealthAssessmentService
from aivitals_engine.integration.vitals_service import VitalsService
from aivitals_engine.models.registry import ModelRegistry

MODEL_REGISTRY_DIR_ENV = "AIVITALS_MODEL_REGISTRY_DIR"
DEFAULT_MODEL_REGISTRY_DIR = "model_store"


class ServiceUnavailableError(RuntimeError):
    pass


@dataclass
class ServiceContainer:
    vitals_service: VitalsService
    health_service: HealthAssessmentService
    model_registry: ModelRegistry
    explanation_service: ExplanationService | None = None

    def require_explanation_service(self) -> ExplanationService:
        if self.explanation_service is None:
            raise ServiceUnavailableError("Chưa cấu hình OPENAI_API_KEY nên dịch vụ giải thích đang tắt")
        return self.explanation_service


def build_explanation_service() -> ExplanationService | None:
    try:
        return ExplanationService(OpenAIChatClient.from_environment())
    except LLMConfigurationError:
        return None


def build_default_container() -> ServiceContainer:
    return ServiceContainer(
        vitals_service=VitalsService(),
        health_service=HealthAssessmentService(),
        model_registry=ModelRegistry(os.environ.get(MODEL_REGISTRY_DIR_ENV, DEFAULT_MODEL_REGISTRY_DIR)),
        explanation_service=build_explanation_service(),
    )
