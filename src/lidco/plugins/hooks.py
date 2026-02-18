"""Hook execution engine wrapping pluggy with error handling."""

from __future__ import annotations

import logging
from typing import Any

import pluggy

logger = logging.getLogger(__name__)


class HookRunner:
    """Wraps pluggy's PluginManager to run hooks with error handling.

    All hook methods are async-safe: they call the synchronous pluggy hooks
    and handle exceptions so a single broken plugin cannot crash the system.
    """

    def __init__(self, plugin_manager: pluggy.PluginManager) -> None:
        self._pm = plugin_manager

    async def run_startup(self, session: object) -> None:
        """Run on_startup hooks for all registered plugins."""
        try:
            self._pm.hook.on_startup(session=session)
        except Exception:
            logger.exception("Error running on_startup hooks")

    async def run_pre_tool(self, tool_name: str, params: dict) -> dict:
        """Run pre_tool_execute hooks. Returns potentially modified params.

        Each hook receives the current params and may return modified params
        or None to signal the tool should be blocked. If any hook returns
        None, an empty dict is returned to indicate blocking.

        Args:
            tool_name: Name of the tool about to execute.
            params: The original parameters dict.

        Returns:
            The (potentially modified) params dict. An empty dict with a
            special '_blocked' key set to True signals the tool was blocked.
        """
        current_params = {**params}

        try:
            results: list[Any] = self._pm.hook.pre_tool_execute(
                tool_name=tool_name, params=current_params
            )
        except Exception:
            logger.exception("Error running pre_tool_execute hooks for %s", tool_name)
            return current_params

        for result in results:
            if result is None:
                logger.info(
                    "Plugin blocked tool execution: %s", tool_name
                )
                return {"_blocked": True}
            if isinstance(result, dict):
                current_params = {**current_params, **result}

        return current_params

    async def run_post_tool(self, tool_name: str, params: dict, result: object) -> None:
        """Run post_tool_execute hooks.

        Args:
            tool_name: Name of the tool that executed.
            params: Parameters that were passed to the tool.
            result: The ToolResult returned by the tool.
        """
        try:
            self._pm.hook.post_tool_execute(
                tool_name=tool_name, params=params, result=result
            )
        except Exception:
            logger.exception("Error running post_tool_execute hooks for %s", tool_name)

    async def run_pre_agent(self, agent_name: str, message: str) -> str:
        """Run pre_agent_run hooks. Returns potentially modified message.

        Each hook receives the current message and may return a modified
        version. The hooks are applied in registration order.

        Args:
            agent_name: Name of the agent about to run.
            message: The original user message.

        Returns:
            The (potentially modified) message string.
        """
        current_message = message

        try:
            results: list[Any] = self._pm.hook.pre_agent_run(
                agent_name=agent_name, message=current_message
            )
        except Exception:
            logger.exception("Error running pre_agent_run hooks for %s", agent_name)
            return current_message

        for result in results:
            if isinstance(result, str) and result:
                current_message = result

        return current_message

    async def run_post_agent(self, agent_name: str, response: object) -> None:
        """Run post_agent_run hooks.

        Args:
            agent_name: Name of the agent that completed.
            response: The AgentResponse returned by the agent.
        """
        try:
            self._pm.hook.post_agent_run(
                agent_name=agent_name, response=response
            )
        except Exception:
            logger.exception("Error running post_agent_run hooks for %s", agent_name)

    async def run_file_change(self, file_path: str, change_type: str) -> None:
        """Run on_file_change hooks.

        Args:
            file_path: Absolute path to the changed file.
            change_type: One of 'created', 'modified', 'deleted'.
        """
        try:
            self._pm.hook.on_file_change(
                file_path=file_path, change_type=change_type
            )
        except Exception:
            logger.exception("Error running on_file_change hooks for %s", file_path)

    async def collect_tools(self) -> list:
        """Collect tools from all plugins via register_tools hook.

        Returns:
            Flat list of BaseTool instances from all plugins.
        """
        tools: list[Any] = []
        try:
            results: list[Any] = self._pm.hook.register_tools()
            for result in results:
                if isinstance(result, list):
                    tools.extend(result)
        except Exception:
            logger.exception("Error collecting tools from plugins")
        return tools

    async def collect_agents(self) -> list:
        """Collect agent configs from all plugins via register_agents hook.

        Returns:
            Flat list of agent config dicts from all plugins.
        """
        agents: list[Any] = []
        try:
            results: list[Any] = self._pm.hook.register_agents()
            for result in results:
                if isinstance(result, list):
                    agents.extend(result)
        except Exception:
            logger.exception("Error collecting agent configs from plugins")
        return agents
