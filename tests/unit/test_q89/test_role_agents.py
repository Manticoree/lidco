"""Tests for RoleAgentFactory (T578)."""
import asyncio
import pytest
from lidco.agents.role_agents import (
    RoleAgentFactory,
    RoleAgentConfig,
    AgentTask,
    VALID_ROLES,
    ROLE_SYSTEM_PROMPTS,
)


def test_valid_roles_non_empty():
    assert len(VALID_ROLES) >= 5
    assert "coder" in VALID_ROLES
    assert "reviewer" in VALID_ROLES
    assert "tester" in VALID_ROLES
    assert "planner" in VALID_ROLES
    assert "debugger" in VALID_ROLES


def test_get_config_returns_correct_role():
    factory = RoleAgentFactory()
    config = factory.get_config("coder")
    assert config.role == "coder"
    assert "coder" in config.system_prompt.lower() or "coding" in config.system_prompt.lower()
    assert isinstance(config.allowed_tools, list)


def test_get_config_unknown_role_raises():
    factory = RoleAgentFactory()
    with pytest.raises(ValueError, match="Unknown role"):
        factory.get_config("wizard")


def test_full_prompt_includes_extra_context():
    factory = RoleAgentFactory()
    config = factory.get_config("planner", extra_context="project uses FastAPI")
    prompt = config.full_prompt()
    assert "FastAPI" in prompt


def test_dispatch_no_llm_dry_run():
    factory = RoleAgentFactory()
    task = AgentTask(role="coder", instructions="Write hello world")
    result = asyncio.run(factory.dispatch(task))
    assert result.success
    assert "CODER" in result.response.upper() or result.response


def test_dispatch_with_llm_callback():
    async def mock_llm(system: str, user: str) -> str:
        return f"Response to: {user}"

    factory = RoleAgentFactory(llm_callback=mock_llm)
    task = AgentTask(role="reviewer", instructions="Review this code")
    result = asyncio.run(factory.dispatch(task))
    assert result.success
    assert "Response to: Review this code" == result.response


def test_dispatch_llm_exception_captured():
    async def failing_llm(system: str, user: str) -> str:
        raise RuntimeError("LLM unavailable")

    factory = RoleAgentFactory(llm_callback=failing_llm)
    task = AgentTask(role="tester", instructions="Generate tests")
    result = asyncio.run(factory.dispatch(task))
    assert not result.success
    assert "LLM unavailable" in result.error


def test_dispatch_many():
    factory = RoleAgentFactory()
    tasks = [
        AgentTask(role="planner", instructions="Plan task A"),
        AgentTask(role="coder", instructions="Implement task A"),
    ]
    results = asyncio.run(factory.dispatch_many(tasks))
    assert len(results) == 2
    assert all(r.success for r in results)


def test_add_custom_role():
    factory = RoleAgentFactory()
    factory.add_role("architect", "You are a software architect.", tools=["read_file"])
    assert "architect" in factory.available_roles()
    config = factory.get_config("architect")
    assert "architect" in config.system_prompt.lower()
    assert config.allowed_tools == ["read_file"]


def test_custom_roles_at_construction():
    factory = RoleAgentFactory(custom_roles={"qa": "You are a QA engineer."})
    assert "qa" in factory.available_roles()


def test_available_roles_includes_builtins():
    factory = RoleAgentFactory()
    roles = factory.available_roles()
    for role in VALID_ROLES:
        assert role in roles
