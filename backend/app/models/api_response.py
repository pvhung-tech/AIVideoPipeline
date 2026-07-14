from typing import Any

from pydantic import BaseModel


class ApiError(BaseModel):
    code: str
    message: str


class ApiResponse(BaseModel):
    success: bool
    data: Any | None = None
    message: str = ""
    error: ApiError | None = None
