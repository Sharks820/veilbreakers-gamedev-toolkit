from typing import Any, Literal
from pydantic import BaseModel, Field


class BlenderCommand(BaseModel):
    type: str
    params: dict[str, Any] = Field(default_factory=dict)


class BlenderResponse(BaseModel):
    status: Literal["success", "error"]
    result: Any = None
    message: str | None = None
    error_type: str | None = None


class BlenderError(BaseModel):
    error_type: str
    message: str
    suggestion: str
    can_retry: bool

    def to_tool_response(self) -> str:
        return (
            f"ERROR [{self.error_type}]: {self.message}\n"
            f"SUGGESTION: {self.suggestion}\n"
            f"RETRYABLE: {'yes' if self.can_retry else 'no'}"
        )
