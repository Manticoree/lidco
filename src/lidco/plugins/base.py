"""Plugin interface and hook specifications using pluggy."""

from __future__ import annotations

import pluggy

hookspec = pluggy.HookspecMarker("lidco")
hookimpl = pluggy.HookimplMarker("lidco")


class LidcoHookSpec:
    """Hook specifications for LIDCO plugins.

    Each method defines a hook that plugins can implement. Plugins only need
    to implement the hooks they care about.
    """

    @hookspec
    def on_startup(self, session: object) -> None:
        """Called when a LIDCO session starts.

        Args:
            session: The active Session instance.
        """

    @hookspec
    def pre_tool_execute(self, tool_name: str, params: dict) -> dict | None:
        """Called before a tool executes.

        Args:
            tool_name: Name of the tool about to run.
            params: Parameters that will be passed to the tool.

        Returns:
            Modified params dict, or None to signal the tool should be blocked.
        """

    @hookspec
    def post_tool_execute(self, tool_name: str, params: dict, result: object) -> None:
        """Called after a tool finishes executing.

        Args:
            tool_name: Name of the tool that ran.
            params: Parameters that were passed to the tool.
            result: The ToolResult returned by the tool.
        """

    @hookspec
    def pre_agent_run(self, agent_name: str, message: str) -> str:
        """Called before an agent processes a message.

        Args:
            agent_name: Name of the agent about to run.
            message: The user message the agent will receive.

        Returns:
            The (potentially modified) message string.
        """

    @hookspec
    def post_agent_run(self, agent_name: str, response: object) -> None:
        """Called after an agent completes its run.

        Args:
            agent_name: Name of the agent that ran.
            response: The AgentResponse returned by the agent.
        """

    @hookspec
    def on_file_change(self, file_path: str, change_type: str) -> None:
        """Called when a watched file is modified.

        Args:
            file_path: Absolute path to the changed file.
            change_type: One of 'created', 'modified', 'deleted'.
        """

    @hookspec
    def register_tools(self) -> list:
        """Register additional tools with LIDCO.

        Returns:
            List of BaseTool instances to register.
        """

    @hookspec
    def register_agents(self) -> list:
        """Register additional agents with LIDCO.

        Returns:
            List of agent config dicts with keys: name, description,
            system_prompt, and optionally model, temperature, tools, etc.
        """


class BasePlugin:
    """Base class for LIDCO plugins.

    Plugins should subclass this and implement any subset of the hooks
    defined in LidcoHookSpec. Use the @hookimpl decorator on methods.

    Example::

        from lidco.plugins.base import BasePlugin, hookimpl

        class MyPlugin(BasePlugin):
            name = "my-plugin"
            version = "1.0.0"
            description = "Does useful things."

            @hookimpl
            def on_startup(self, session):
                print("Session started!")

            @hookimpl
            def pre_tool_execute(self, tool_name, params):
                return params  # pass through unchanged
    """

    name: str = "unnamed"
    version: str = "0.0.0"
    description: str = ""
