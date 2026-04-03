"""Q239 CLI commands: /validate-messages, /normalize, /schema-info, /message-stats."""
from __future__ import annotations


def register(registry) -> None:
    """Register Q239 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /validate-messages
    # ------------------------------------------------------------------

    async def validate_messages_handler(args: str) -> str:
        import json

        from lidco.conversation.validator import MessageValidator
        from lidco.conversation.validation_reporter import ValidationReporter

        raw = args.strip()
        if not raw:
            return "Usage: /validate-messages <json array of messages>"
        try:
            messages = json.loads(raw)
        except json.JSONDecodeError as exc:
            return f"Invalid JSON: {exc}"
        if not isinstance(messages, list):
            return "Expected a JSON array of message objects."

        validator = MessageValidator()
        results = validator.validate_batch(messages)
        reporter = ValidationReporter()
        return reporter.report(results)

    # ------------------------------------------------------------------
    # /normalize
    # ------------------------------------------------------------------

    async def normalize_handler(args: str) -> str:
        import json

        from lidco.conversation.normalizer import MessageNormalizer

        parts = args.strip().split(maxsplit=1)
        provider = None
        raw = args.strip()

        # Check if first token looks like a provider name (no '[' or '{')
        if parts and parts[0] not in ("", "[", "{") and not parts[0].startswith("[") and not parts[0].startswith("{"):
            provider = parts[0]
            raw = parts[1] if len(parts) > 1 else ""

        if not raw:
            return "Usage: /normalize [provider] <json array of messages>"
        try:
            messages = json.loads(raw)
        except json.JSONDecodeError as exc:
            return f"Invalid JSON: {exc}"
        if not isinstance(messages, list):
            return "Expected a JSON array of message objects."

        normalizer = MessageNormalizer()
        if provider:
            normalizer.set_target_provider(provider)
        normalized = normalizer.normalize_batch(messages)
        return json.dumps(normalized, indent=2)

    # ------------------------------------------------------------------
    # /schema-info
    # ------------------------------------------------------------------

    async def schema_info_handler(args: str) -> str:
        import json

        from lidco.conversation.schema_registry import SchemaRegistry

        reg = SchemaRegistry.with_defaults()
        provider = args.strip()

        if not provider:
            providers = reg.list_providers()
            return "Registered providers: " + ", ".join(providers)

        schema = reg.get(provider)
        if schema is None:
            return f"No schema found for provider '{provider}'."
        return json.dumps(schema, indent=2)

    # ------------------------------------------------------------------
    # /message-stats
    # ------------------------------------------------------------------

    async def message_stats_handler(args: str) -> str:
        import json

        raw = args.strip()
        if not raw:
            return "Usage: /message-stats <json array of messages>"
        try:
            messages = json.loads(raw)
        except json.JSONDecodeError as exc:
            return f"Invalid JSON: {exc}"
        if not isinstance(messages, list):
            return "Expected a JSON array of message objects."

        role_counts: dict[str, int] = {}
        total_length = 0
        for msg in messages:
            role = msg.get("role", "unknown")
            role_counts[role] = role_counts.get(role, 0) + 1
            content = msg.get("content", "")
            if isinstance(content, str):
                total_length += len(content)
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        text = block.get("text", "")
                        if isinstance(text, str):
                            total_length += len(text)

        lines = [f"Message count: {len(messages)}"]
        for role in sorted(role_counts):
            lines.append(f"  {role}: {role_counts[role]}")
        lines.append(f"Total content length: {total_length}")
        return "\n".join(lines)

    registry.register(SlashCommand("validate-messages", "Validate conversation messages", validate_messages_handler))
    registry.register(SlashCommand("normalize", "Normalize messages to provider schema", normalize_handler))
    registry.register(SlashCommand("schema-info", "Show provider schema info", schema_info_handler))
    registry.register(SlashCommand("message-stats", "Message statistics", message_stats_handler))
