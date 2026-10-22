from typing import Any

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

DEFAULT_SUCCESS_MESSAGE = "Thao tác thành công"


def success_response(data: Any, message: str = DEFAULT_SUCCESS_MESSAGE, status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder({"success": True, "data": data, "message": message}),
    )


def error_response(error_code: str, message: str, status_code: int, details: Any = None) -> JSONResponse:
    content: dict[str, Any] = {"success": False, "error": error_code, "message": message}
    if details is not None:
        content["details"] = details
    return JSONResponse(status_code=status_code, content=jsonable_encoder(content))
