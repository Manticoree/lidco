"""Q262 CLI commands: /scan-secrets, /rotate-secret, /vault, /secret-inventory."""
from __future__ import annotations

import json

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q262 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /scan-secrets
    # ------------------------------------------------------------------
    async def scan_secrets_handler(args: str) -> str:
        from lidco.secrets.scanner import SecretScanner

        if "scanner" not in _state:
            _state["scanner"] = SecretScanner()

        scanner: SecretScanner = _state["scanner"]  # type: ignore[assignment]
        text = args.strip()
        if not text:
            return "Usage: /scan-secrets <text>"

        result = scanner.scan_text(text)
        if not result.findings:
            return f"No secrets found ({result.scanned_lines} lines scanned)."
        lines = [f"Found {len(result.findings)} potential secret(s):"]
        for f in result.findings:
            lines.append(
                f"  [{f.severity}] {f.type} at line {f.line}:{f.column} — {f.value_preview}"
            )
        return "\n".join(lines)

    registry.register(SlashCommand("scan-secrets", "Scan text for leaked secrets", scan_secrets_handler))

    # ------------------------------------------------------------------
    # /rotate-secret
    # ------------------------------------------------------------------
    async def rotate_secret_handler(args: str) -> str:
        from lidco.secrets.rotator import SecretRotator

        if "rotator" not in _state:
            _state["rotator"] = SecretRotator()

        rotator: SecretRotator = _state["rotator"]  # type: ignore[assignment]
        parts = args.strip().split(maxsplit=2)
        if len(parts) < 3:
            return "Usage: /rotate-secret <name> <provider> <current_value>"

        name, provider, current_value = parts
        result = rotator.rotate(name, provider, current_value)
        if result.success:
            return f"Rotated '{name}' via {provider}: {result.old_prefix}... -> {result.new_prefix}..."
        return f"Rotation failed for '{name}': {result.error}"

    registry.register(SlashCommand("rotate-secret", "Rotate a secret", rotate_secret_handler))

    # ------------------------------------------------------------------
    # /vault
    # ------------------------------------------------------------------
    async def vault_handler(args: str) -> str:
        from lidco.secrets.vault import VaultClient

        if "vault" not in _state:
            _state["vault"] = VaultClient()

        vault: VaultClient = _state["vault"]  # type: ignore[assignment]
        parts = args.strip().split(maxsplit=2)
        sub = parts[0].lower() if parts else ""
        rest = parts[1:] if len(parts) > 1 else []

        if sub == "put":
            if len(rest) < 2:
                return "Usage: /vault put <key> <value>"
            key, value = rest[0], rest[1]
            secret = vault.put(key, value)
            return f"Stored '{key}' (v{secret.version})."

        if sub == "get":
            if not rest:
                return "Usage: /vault get <key>"
            secret = vault.get(rest[0])
            if secret is None:
                return f"Key '{rest[0]}' not found or expired."
            return f"{secret.key} (v{secret.version}): {secret.value}"

        if sub == "list":
            prefix = rest[0] if rest else ""
            keys = vault.list_keys(prefix)
            if not keys:
                return "No keys in vault."
            return "Vault keys:\n" + "\n".join(f"  {k}" for k in keys)

        if sub == "delete":
            if not rest:
                return "Usage: /vault delete <key>"
            deleted = vault.delete(rest[0])
            return f"Deleted '{rest[0]}'." if deleted else f"Key '{rest[0]}' not found."

        summary = vault.summary()
        return f"Vault ({summary['backend']}): {summary['keys']} keys, {summary['total_versions']} versions."

    registry.register(SlashCommand("vault", "Manage vault secrets", vault_handler))

    # ------------------------------------------------------------------
    # /secret-inventory
    # ------------------------------------------------------------------
    async def secret_inventory_handler(args: str) -> str:
        from lidco.secrets.inventory import SecretInventory, SecretEntry

        if "inventory" not in _state:
            _state["inventory"] = SecretInventory()

        inv: SecretInventory = _state["inventory"]  # type: ignore[assignment]
        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "add":
            if not rest:
                return "Usage: /secret-inventory add <name>"
            entry = SecretEntry(name=rest)
            inv.add(entry)
            return f"Added '{rest}' to inventory."

        if sub == "list":
            entries = inv.all_entries()
            if not entries:
                return "Inventory is empty."
            lines = [f"Secret inventory ({len(entries)} entries):"]
            for e in entries:
                lines.append(f"  {e.name} [{e.exposure_risk}] provider={e.provider}")
            return "\n".join(lines)

        if sub == "stale":
            threshold = int(rest) if rest.isdigit() else 90
            stale = inv.stale(threshold)
            if not stale:
                return "No stale secrets."
            lines = [f"Stale secrets ({len(stale)}):"]
            for e in stale:
                lines.append(f"  {e.name} [{e.exposure_risk}]")
            return "\n".join(lines)

        if sub == "risk":
            if not rest:
                return "Usage: /secret-inventory risk <level>"
            entries = inv.by_risk(rest)
            if not entries:
                return f"No secrets with risk '{rest}'."
            lines = [f"Secrets with risk '{rest}' ({len(entries)}):"]
            for e in entries:
                lines.append(f"  {e.name} provider={e.provider}")
            return "\n".join(lines)

        summary = inv.summary()
        return json.dumps(summary, indent=2)

    registry.register(SlashCommand("secret-inventory", "Manage secret inventory", secret_inventory_handler))
