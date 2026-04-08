from typing import List, Optional, Dict, Any
from pydantic import BaseModel


class ErrorDetail(BaseModel):
    """Field-level error detail."""
    field: str
    message: str


class ErrorResponse(BaseModel):
    """Structured error response envelope."""
    status_code: int
    error_code: str  # Machine-readable code, e.g., "ORDER_NOT_FOUND"
    message: str  # Human-readable message
    details: Optional[List[ErrorDetail]] = None
    request_id: Optional[str] = None  # For tracing
    data: Optional[Dict[str, Any]] = None  # Additional context if needed


# Example responses:
# 404: ErrorResponse(
#     status_code=404,
#     error_code="ORDER_NOT_FOUND",
#     message="Order not found",
#     request_id="req-123"
# )
#
# 422: ErrorResponse(
#     status_code=422,
#     error_code="VALIDATION_ERROR",
#     message="Request validation failed",
#     details=[ErrorDetail(field="email", message="Invalid email format")],
#     request_id="req-124"
# )