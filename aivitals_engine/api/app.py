from fastapi import FastAPI

from aivitals_engine.api.container import ServiceContainer, build_default_container
from aivitals_engine.api.errors import register_exception_handlers
from aivitals_engine.api.routes import router
from aivitals_engine.version import ENGINE_VERSION

API_PREFIX = "/api/v1"


def create_app(container: ServiceContainer | None = None) -> FastAPI:
    app = FastAPI(
        title="AIVitals Engine API",
        version=ENGINE_VERSION,
        description="API của khối Vitals, Validation, Model Registry, Health Assessment và Explanation",
    )
    app.state.container = container or build_default_container()
    register_exception_handlers(app)
    app.include_router(router, prefix=API_PREFIX)
    return app
