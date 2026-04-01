"""Tests for lidco.sdk.tool_builder — ToolBuilder fluent API."""

from unittest.mock import MagicMock, patch
import sys

# Ensure lidco.tools.base types are available (they exist in the project)
from lidco.tools.base import BaseTool, ToolParameter, ToolPermission, ToolResult
from lidco.sdk.tool_builder import (
    ToolBuilder,
    ToolBuilderError,
    ToolSpec,
    ToolValidationError,
)


async def _dummy_handler(**kwargs) -> ToolResult:
    return ToolResult(output="ok")


def test_fluent_build():
    tool = (
        ToolBuilder("my_tool")
        .description("A test tool")
        .add_param("input", "string", "The input")
        .handler(_dummy_handler)
        .build()
    )
    assert isinstance(tool, BaseTool)
    assert tool.name == "my_tool"
    assert tool.description == "A test tool"
    assert len(tool.parameters) == 1
    assert tool.parameters[0].name == "input"


def test_add_multiple_params():
    builder = (
        ToolBuilder("multi")
        .description("Multi-param tool")
        .add_param("a", "string", "First")
        .add_param("b", "integer", "Second", required=False, default=0)
        .handler(_dummy_handler)
    )
    spec = builder.get_spec()
    assert len(spec.tool_parameters) == 2
    assert spec.tool_parameters[1].required is False
    assert spec.tool_parameters[1].default == 0


def test_validate_no_description():
    builder = ToolBuilder("x").handler(_dummy_handler)
    errors = builder.validate()
    assert any("description" in e.lower() for e in errors)


def test_validate_no_handler():
    builder = ToolBuilder("x").description("desc")
    errors = builder.validate()
    assert any("handler" in e.lower() for e in errors)


def test_build_raises_on_invalid():
    builder = ToolBuilder("x")  # missing desc and handler
    try:
        builder.build()
        assert False, "Expected ToolValidationError"
    except ToolValidationError as exc:
        assert "description" in str(exc).lower()
        assert "handler" in str(exc).lower()


def test_empty_name_raises():
    try:
        ToolBuilder("")
        assert False, "Expected ToolBuilderError"
    except ToolBuilderError:
        pass


def test_duplicate_param_detected():
    builder = (
        ToolBuilder("dup")
        .description("desc")
        .add_param("x", "string", "First x")
        .add_param("x", "string", "Second x")
        .handler(_dummy_handler)
    )
    errors = builder.validate()
    assert any("duplicate" in e.lower() for e in errors)


def test_reset_clears_state():
    builder = (
        ToolBuilder("resettable")
        .description("desc")
        .add_param("a", "string", "param")
        .handler(_dummy_handler)
        .set_metadata("key", "val")
    )
    # Ensure valid before reset
    assert len(builder.validate()) == 0
    builder.reset()
    errors = builder.validate()
    assert any("description" in e.lower() for e in errors)
    assert any("handler" in e.lower() for e in errors)


def test_get_spec():
    builder = (
        ToolBuilder("spec_tool")
        .description("A spec tool")
        .handler(_dummy_handler)
        .set_metadata("author", "test")
    )
    spec = builder.get_spec()
    assert isinstance(spec, ToolSpec)
    assert spec.tool_name == "spec_tool"
    assert spec.metadata == {"author": "test"}


def test_set_permission():
    builder = (
        ToolBuilder("perm_tool")
        .description("desc")
        .set_permission(ToolPermission.AUTO)
        .handler(_dummy_handler)
    )
    spec = builder.get_spec()
    assert spec.tool_permission == ToolPermission.AUTO
