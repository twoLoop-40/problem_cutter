"""공통 타입 정의"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ToolDiagnostics:
    """툴 실행 시 수집되는 보조 진단 정보"""

    info: List[str] = field(default_factory=list)
    successes: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    runtime_ms: Optional[float] = None
    extras: Dict[str, Any] = field(default_factory=dict)

    def add_info(self, message: str) -> None:
        self.info.append(message)

    def add_success(self, message: str) -> None:
        self.successes.append(message)

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)

    def add_error(self, message: str) -> None:
        self.errors.append(message)


@dataclass
class ToolResult:
    """AgentTool 함수가 반환하는 표준 결과"""

    success: bool
    message: str
    data: Dict[str, Any] = field(default_factory=dict)
    diagnostics: ToolDiagnostics = field(default_factory=ToolDiagnostics)

    @classmethod
    def ok(cls, message: str = "", **data: Any) -> "ToolResult":
        return cls(success=True, message=message, data=data)

    @classmethod
    def fail(
        cls,
        message: str,
        *,
        diagnostics: Optional[ToolDiagnostics] = None,
        **data: Any,
    ) -> "ToolResult":
        return cls(
            success=False,
            message=message,
            data=data,
            diagnostics=diagnostics or ToolDiagnostics(),
        )


class AgentToolError(RuntimeError):
    """AgentTools 전용 예외"""

    def __init__(self, message: str, *, cause: Optional[Exception] = None):
        super().__init__(message)
        self.cause = cause

    def __str__(self) -> str:  # pragma: no cover - 단순 포맷터
        if self.cause:
            return f"{super().__str__()} (cause={self.cause})"
        return super().__str__()








