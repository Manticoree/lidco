"""Base tool interface and types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


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


class BaseTool(ABC):
    """Abstract base class for all tools."""

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
            return ToolResult(output="", success=False, error=str(e))

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
