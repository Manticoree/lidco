"""Base tool interface and types."""

from __future__ import annotations

import traceback as _traceback
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class ToolPermission(str, Enum):
    AUTO = "auto"
    ASK = "ask"
    DENY = "deny"


@dataclass(frozen=True)
class ToolParameter:
    """Describes a single tool parameter."""

    name: str
    type: str  # "string", "integer", "boolean", "array", "object"
    description: str
    required: bool = True
    default: Any = None
    enum: list[str] | None = None


@dataclass(frozen=True)
class ToolResult:
    """Result of a tool execution."""

    output: str
    success: bool = True
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    traceback_str: str | None = None


class BaseTool(ABC):
    """Abstract base class for all tools."""

    # Class-level default — overridden per instance via set_progress_callback().
    # Using a class attribute avoids breaking subclasses that define their own
    # __init__ without calling super().__init__().
    _progress_callback: Callable[[str], None] | None = None

    def set_progress_callback(
        self, callback: Callable[[str], None] | None
    ) -> None:
        """Inject a progress callback for long-running tools that stream output.

        When set, streaming-capable tools (e.g. ``RunTestsTool``) call this
        with each output line as it arrives so the agent's stream display
        can show live progress.
        """
        self._progress_callback = callback

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool name (e.g. 'file_read')."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description for the LLM."""

    @property
    @abstractmethod
    def parameters(self) -> list[ToolParameter]:
        """List of parameters this tool accepts."""

    @property
    def permission(self) -> ToolPermission:
        """Default permission level for this tool."""
        return ToolPermission.ASK

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the tool with given parameters."""
        try:
            return await self._run(**kwargs)
        except Exception as e:
            tb = _traceback.format_exc()
            return ToolResult(output="", success=False, error=str(e), traceback_str=tb)

    @abstractmethod
    async def _run(self, **kwargs: Any) -> ToolResult:
        """Internal implementation - override this in subclasses."""

    def to_openai_schema(self) -> dict[str, Any]:
        """Convert to OpenAI function-calling schema."""
        properties: dict[str, Any] = {}
        required: list[str] = []

        for param in self.parameters:
            prop: dict[str, Any] = {
                "type": param.type,
                "description": param.description,
            }
            if param.enum:
                prop["enum"] = param.enum
            properties[param.name] = prop
            if param.required:
                required.append(param.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }
