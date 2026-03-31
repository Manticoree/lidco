"""Custom Tool Builder — fluent API for creating new tools with auto-registration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

from lidco.tools.base import BaseTool, ToolParameter, ToolPermission, ToolResult


class ToolBuilderError(Exception):
    """Raised for tool building errors."""


class ToolValidationError(ToolBuilderError):
    """Raised when built tool fails validation."""


@dataclass(frozen=True)
class ToolSpec:
    """Immutable specification for a built tool."""

    tool_name: str
    tool_description: str
    tool_parameters: tuple[ToolParameter, ...]
    tool_permission: ToolPermission
    handler: Callable[..., Awaitable[ToolResult]]
    metadata: dict[str, str] = field(default_factory=dict)


class _BuiltTool(BaseTool):
    """Concrete tool created from a ToolSpec."""

    def __init__(self, spec: ToolSpec) -> None:
        self._spec = spec

    @property
    def name(self) -> str:
        return self._spec.tool_name

    @property
    def description(self) -> str:
        return self._spec.tool_description

    @property
    def parameters(self) -> list[ToolParameter]:
        return list(self._spec.tool_parameters)

    @property
    def permission(self) -> ToolPermission:
        return self._spec.tool_permission

    async def _run(self, **kwargs: Any) -> ToolResult:
        return await self._spec.handler(**kwargs)


class ToolBuilder:
    """Fluent builder for creating custom tools.

    Usage::

        tool = (
            ToolBuilder("my_tool")
            .description("Does something useful")
            .add_param("input", "string", "The input text")
            .permission(ToolPermission.AUTO)
            .handler(my_handler)
            .build()
        )
    """

    def __init__(self, name: str) -> None:
        if not name or not name.strip():
            raise ToolBuilderError("Tool name cannot be empty")
        self._name: str = name.strip()
        self._description: str = ""
        self._parameters: list[ToolParameter] = []
        self._permission: ToolPermission = ToolPermission.ASK
        self._handler: Callable[..., Awaitable[ToolResult]] | None = None
        self._metadata: dict[str, str] = {}

    def description(self, desc: str) -> ToolBuilder:
        """Set tool description."""
        self._description = desc
        return self

    def add_param(
        self,
        name: str,
        type: str = "string",
        description: str = "",
        *,
        required: bool = True,
        default: Any = None,
        enum: list[str] | None = None,
    ) -> ToolBuilder:
        """Add a parameter to the tool."""
        param = ToolParameter(
            name=name,
            type=type,
            description=description,
            required=required,
            default=default,
            enum=enum,
        )
        self._parameters = [*self._parameters, param]
        return self

    def set_permission(self, perm: ToolPermission) -> ToolBuilder:
        """Set the permission level."""
        self._permission = perm
        return self

    def handler(self, fn: Callable[..., Awaitable[ToolResult]]) -> ToolBuilder:
        """Set the async handler function."""
        self._handler = fn
        return self

    def set_metadata(self, key: str, value: str) -> ToolBuilder:
        """Add metadata entry."""
        self._metadata = {**self._metadata, key: value}
        return self

    def validate(self) -> list[str]:
        """Validate the builder state. Returns a list of error messages (empty if valid)."""
        errors: list[str] = []
        if not self._name:
            errors.append("Tool name is required")
        if not self._description:
            errors.append("Tool description is required")
        if self._handler is None:
            errors.append("Tool handler is required")
        # Check for duplicate param names
        param_names = [p.name for p in self._parameters]
        seen: set[str] = set()
        for pn in param_names:
            if pn in seen:
                errors.append(f"Duplicate parameter name: {pn!r}")
            seen.add(pn)
        return errors

    def build(self) -> BaseTool:
        """Build and return the tool. Raises ToolValidationError if invalid."""
        errors = self.validate()
        if errors:
            raise ToolValidationError("; ".join(errors))

        spec = ToolSpec(
            tool_name=self._name,
            tool_description=self._description,
            tool_parameters=tuple(self._parameters),
            tool_permission=self._permission,
            handler=self._handler,  # type: ignore[arg-type]
            metadata=dict(self._metadata),
        )
        return _BuiltTool(spec)

    def build_and_register(self, registry: Any) -> BaseTool:
        """Build the tool and register it with a ToolRegistry."""
        tool = self.build()
        registry.register(tool)
        return tool

    def get_spec(self) -> ToolSpec:
        """Return the current spec without building. Raises if invalid."""
        errors = self.validate()
        if errors:
            raise ToolValidationError("; ".join(errors))
        return ToolSpec(
            tool_name=self._name,
            tool_description=self._description,
            tool_parameters=tuple(self._parameters),
            tool_permission=self._permission,
            handler=self._handler,  # type: ignore[arg-type]
            metadata=dict(self._metadata),
        )

    def reset(self) -> ToolBuilder:
        """Reset builder state (keep name)."""
        self._description = ""
        self._parameters = []
        self._permission = ToolPermission.ASK
        self._handler = None
        self._metadata = {}
        return self
