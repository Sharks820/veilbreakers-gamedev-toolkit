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


class UnityCommand(BaseModel):
    """Command sent to the Unity Editor TCP bridge.

    Mirrors BlenderCommand exactly -- same JSON wire format with a
    ``type`` string selecting the handler and ``params`` carrying
    handler-specific arguments.
    """

    type: str
    params: dict[str, Any] = Field(default_factory=dict)


class UnityResponse(BaseModel):
    """Response received from the Unity Editor TCP bridge.

    Mirrors BlenderResponse -- ``status`` is ``"success"`` or
    ``"error"``, ``result`` carries the handler payload on success,
    ``message`` and ``error_type`` carry diagnostics on failure.
    """

    status: Literal["success", "error"]
    result: Any = None
    message: str | None = None
    error_type: str | None = None


class UnityError(BaseModel):
    """Structured error from a Unity bridge handler.

    Mirrors BlenderError -- carries error classification, a
    human-readable suggestion, and a retry hint.
    """

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
