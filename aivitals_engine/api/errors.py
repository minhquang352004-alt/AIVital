import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from aivitals_engine.api.container import ServiceUnavailableError
from aivitals_engine.api.responses import error_response
from aivitals_engine.explanation.llm_client import LLMRequestError
from aivitals_engine.explanation.payload import ResultNotValidatedError
from aivitals_engine.models.registry import ChecksumMismatchError, ModelNotFoundError

logger = logging.getLogger("aivitals_engine.api")

HTTP_ERROR_CODES = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}


class ResourceNotFoundError(LookupError):
    pass


async def handle_request_validation(request: Request, exception: RequestValidationError):
    return error_response("VALIDATION_ERROR", "Dữ liệu đầu vào không hợp lệ", 400, exception.errors())


async def handle_result_not_validated(request: Request, exception: ResultNotValidatedError):
    return error_response("RESULT_NOT_VALIDATED", str(exception), 400)


async def handle_value_error(request: Request, exception: ValueError):
    return error_response("INVALID_INPUT", str(exception), 400)


async def handle_not_found(request: Request, exception: Exception):
    return error_response("NOT_FOUND", str(exception), 404)


async def handle_checksum_mismatch(request: Request, exception: ChecksumMismatchError):
    return error_response("MODEL_CHECKSUM_MISMATCH", str(exception), 409)


async def handle_llm_error(request: Request, exception: LLMRequestError):
    return error_response("LLM_UPSTREAM_ERROR", "Dịch vụ giải thích tạm thời không phản hồi", 502)


async def handle_service_unavailable(request: Request, exception: ServiceUnavailableError):
    return error_response("SERVICE_UNAVAILABLE", str(exception), 503)


async def handle_http_exception(request: Request, exception: StarletteHTTPException):
    code = HTTP_ERROR_CODES.get(exception.status_code, "HTTP_ERROR")
    return error_response(code, "Không tìm thấy tài nguyên" if exception.status_code == 404 else str(exception.detail), exception.status_code)


async def handle_unexpected(request: Request, exception: Exception):
    logger.exception("Lỗi không mong đợi khi xử lý %s", request.url.path)
    return error_response("INTERNAL_ERROR", "Lỗi hệ thống, vui lòng thử lại sau", 500)


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, handle_request_validation)
    app.add_exception_handler(ResultNotValidatedError, handle_result_not_validated)
    app.add_exception_handler(ModelNotFoundError, handle_not_found)
    app.add_exception_handler(ResourceNotFoundError, handle_not_found)
    app.add_exception_handler(ChecksumMismatchError, handle_checksum_mismatch)
    app.add_exception_handler(LLMRequestError, handle_llm_error)
    app.add_exception_handler(ServiceUnavailableError, handle_service_unavailable)
    app.add_exception_handler(ValueError, handle_value_error)
    app.add_exception_handler(StarletteHTTPException, handle_http_exception)
    app.add_exception_handler(Exception, handle_unexpected)
