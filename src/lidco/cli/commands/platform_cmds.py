"""CLI commands for enterprise platform features (Q85)."""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lidco.cli.commands.registry import CommandRegistry


def register_platform_commands(registry: "CommandRegistry") -> None:
    """Register /ci-heal, /webhook, /knowledge, /mcp-serve commands."""

    async def ci_heal_handler(args: str) -> str:
        command = args.strip()
        if not command:
            return "Usage: /ci-heal <command>  e.g. /ci-heal python -m pytest -q"
        try:
            from lidco.review.ci_healer import CIPipelineHealer
            healer = CIPipelineHealer(max_attempts=1)
            result = await healer.heal(command)
            return result.format_report()
        except Exception as e:
            return f"/ci-heal failed: {e}"

    async def webhook_handler(args: str) -> str:
        parts = args.strip().split(None, 2)
        sub = parts[0] if parts else "help"
        if sub == "parse" and len(parts) >= 3:
            source, body = parts[1], parts[2]
            try:
                from lidco.integrations.webhook_bus import WebhookEventBus
                bus = WebhookEventBus()
                if source == "github":
                    event = bus.parse_github(body)
                elif source == "slack":
                    event = bus.parse_slack(body)
                else:
                    event = bus.parse_linear(body)
                return f"Parsed {source} event: type={event.event_type}"
            except Exception as e:
                return f"/webhook parse failed: {e}"
        elif sub == "history":
            return "Webhook history: no persistent bus in REPL session."
        return "Usage: /webhook parse <github|slack|linear> <json_body>"

    async def knowledge_handler(args: str) -> str:
        parts = args.strip().split(None, 2)
        sub = parts[0] if parts else "list"
        try:
            from lidco.memory.knowledge_trigger import KnowledgeTrigger, KnowledgeItem
            kt = KnowledgeTrigger()
            if sub == "list":
                items = kt.list_items()
                if not items:
                    return "No knowledge items. Use /knowledge add <id> <title> <trigger> <content>"
                return "\n".join(f"  [{i.id}] {i.title} (triggers: {', '.join(i.triggers[:3])})" for i in items)
            elif sub == "add" and len(parts) >= 3:
                # /knowledge add <id> <title>
                item_id = parts[1]
                title = parts[2]
                item = KnowledgeItem(id=item_id, title=title, content="", triggers=[item_id])
                kt.add(item)
                kt.save()
                return f"Added knowledge item: {item_id}"
            elif sub == "match" and len(parts) >= 2:
                ctx = parts[1] if len(parts) > 1 else ""
                injection = kt.build_injection(ctx)
                if injection.is_empty():
                    return "No matching knowledge items for that context."
                return f"Matched {len(injection.matches)} item(s):\n{injection.injected_text[:400]}"
            return "Usage: /knowledge [list|add <id> <title>|match <context>]"
        except Exception as e:
            return f"/knowledge failed: {e}"

    async def mcp_serve_handler(args: str) -> str:
        parts = args.strip().split()
        sub = parts[0] if parts else "info"
        try:
            from lidco.tools.mcp_task_server import MCPTaskServer, MCPTool
            server = MCPTaskServer()

            # Register a demo echo tool
            async def _echo(message: str = "") -> str:
                return f"echo: {message}"

            server.register_tool(MCPTool(
                name="echo",
                description="Echo a message back",
                input_schema={"type": "object", "properties": {"message": {"type": "string"}}},
                handler=_echo,
            ))

            if sub == "info":
                info = server.server_info()
                return f"MCP Server: {info['name']} v{info['version']} — {info['tools']} tool(s)"
            elif sub == "tools":
                tools = server.list_tools()
                return "\n".join(f"  {t['name']}: {t['description']}" for t in tools)
            elif sub == "call" and len(parts) >= 2:
                tool_name = parts[1]
                arg_str = " ".join(parts[2:]) if len(parts) > 2 else ""
                result = await server.call_tool(tool_name, {"message": arg_str})
                return f"Result: {result.result}"
            return "Usage: /mcp-serve [info|tools|call <tool>]"
        except Exception as e:
            return f"/mcp-serve failed: {e}"

    from lidco.cli.commands.registry import SlashCommand
    registry.register(SlashCommand("ci-heal", "Self-healing CI loop: run, detect, fix, retry", ci_heal_handler))
    registry.register(SlashCommand("webhook", "Parse and dispatch webhook events", webhook_handler))
    registry.register(SlashCommand("knowledge", "Manage architectural knowledge items", knowledge_handler))
    registry.register(SlashCommand("mcp-serve", "MCP task server for IDE integration", mcp_serve_handler))
