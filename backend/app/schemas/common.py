from pydantic import BaseModel
from typing import Any, Dict, List, Optional


class ErrorResponse(BaseModel):
    detail: str


class ValidationErrorDetail(BaseModel):
    loc: List[Any]
    msg: str
    type: str


class HTTPValidationError(BaseModel):
    detail: List[ValidationErrorDetail]
