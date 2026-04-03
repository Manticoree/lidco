"""Q263 CLI commands: /net-inspect, /proxy-config, /certs, /net-policy."""
from __future__ import annotations

import json

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q263 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /net-inspect
    # ------------------------------------------------------------------
    async def net_inspect_handler(args: str) -> str:
        from lidco.netsec.inspector import RequestInspector

        if "inspector" not in _state:
            _state["inspector"] = RequestInspector()

        inspector: RequestInspector = _state["inspector"]  # type: ignore[assignment]
        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""

        if sub == "history":
            items = inspector.history()
            if not items:
                return "No inspection history."
            lines = [f"Inspection history ({len(items)} entries):"]
            for r in items[-20:]:
                status = "BLOCKED" if r.blocked else "OK"
                lines.append(f"  [{status}] {r.method} {r.url}")
            return "\n".join(lines)

        if sub == "blocked":
            items = inspector.blocked_requests()
            if not items:
                return "No blocked requests."
            lines = [f"Blocked requests ({len(items)}):"]
            for r in items:
                lines.append(f"  {r.method} {r.url} — {r.reason}")
            return "\n".join(lines)

        if sub == "clear":
            count = inspector.clear_history()
            return f"Cleared {count} inspection entries."

        if sub:
            result = inspector.inspect(sub)
            status = "BLOCKED" if result.blocked else "OK"
            return f"[{status}] {result.method} {result.host} — {result.url}"

        summary = inspector.summary()
        return json.dumps(summary, indent=2)

    registry.register(SlashCommand("net-inspect", "Inspect outbound HTTP requests", net_inspect_handler))

    # ------------------------------------------------------------------
    # /proxy-config
    # ------------------------------------------------------------------
    async def proxy_config_handler(args: str) -> str:
        from lidco.netsec.proxy import ProxyConfig, ProxyManager

        if "proxy" not in _state:
            _state["proxy"] = ProxyManager()

        mgr: ProxyManager = _state["proxy"]  # type: ignore[assignment]
        parts = args.strip().split()
        sub = parts[0].lower() if parts else ""

        if sub == "list":
            configs = mgr.all_configs()
            if not configs:
                return "No proxy configs."
            lines = [f"Proxy configs ({len(configs)}):"]
            for c in configs:
                status = "enabled" if c.enabled else "disabled"
                lines.append(f"  {c.name}: {c.url} [{c.proxy_type}] ({status})")
            return "\n".join(lines)

        if sub == "add":
            if len(parts) < 3:
                return "Usage: /proxy-config add <name> <url>"
            name, url = parts[1], parts[2]
            cfg = ProxyConfig(name=name, url=url)
            mgr.add(cfg)
            return f"Added proxy '{name}': {url}"

        if sub == "remove":
            if len(parts) < 2:
                return "Usage: /proxy-config remove <name>"
            removed = mgr.remove(parts[1])
            return f"Removed '{parts[1]}'." if removed else f"Proxy '{parts[1]}' not found."

        if sub == "detect":
            detected = mgr.detect_env()
            if not detected:
                return "No proxy environment variables found."
            lines = [f"Detected {len(detected)} proxy config(s):"]
            for c in detected:
                lines.append(f"  {c.name}: {c.url} [{c.proxy_type}]")
            return "\n".join(lines)

        summary = mgr.summary()
        return json.dumps(summary, indent=2)

    registry.register(SlashCommand("proxy-config", "Manage proxy configurations", proxy_config_handler))

    # ------------------------------------------------------------------
    # /certs
    # ------------------------------------------------------------------
    async def certs_handler(args: str) -> str:
        from lidco.netsec.certificates import CertificateManager

        if "certs" not in _state:
            _state["certs"] = CertificateManager()

        mgr: CertificateManager = _state["certs"]  # type: ignore[assignment]
        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "list":
            certs = mgr.all_certs()
            if not certs:
                return "No certificates registered."
            lines = [f"Certificates ({len(certs)}):"]
            for name, info in certs.items():
                status = "EXPIRED" if info.is_expired else "valid"
                lines.append(f"  {name}: {info.subject} [{status}] fp={info.fingerprint[:16]}...")
            return "\n".join(lines)

        if sub == "add":
            if not rest:
                return "Usage: /certs add <name>"
            # In real usage, cert PEM would come from file; here just register name
            mgr.register(rest, f"Subject: {rest}\nIssuer: LIDCO CA\nNot Before: 2025-01-01\nNot After: 2027-12-31")
            return f"Registered certificate '{rest}'."

        if sub == "remove":
            if not rest:
                return "Usage: /certs remove <name>"
            removed = mgr.remove(rest)
            return f"Removed '{rest}'." if removed else f"Certificate '{rest}' not found."

        if sub == "check-expiry":
            expired = mgr.check_expiry()
            if not expired:
                return "No expired certificates."
            lines = [f"Expired certificates ({len(expired)}):"]
            for name, info in expired:
                lines.append(f"  {name}: {info.subject} (expired: {info.not_after})")
            return "\n".join(lines)

        summary = mgr.summary()
        return json.dumps(summary, indent=2)

    registry.register(SlashCommand("certs", "Manage TLS certificates", certs_handler))

    # ------------------------------------------------------------------
    # /net-policy
    # ------------------------------------------------------------------
    async def net_policy_handler(args: str) -> str:
        from lidco.netsec.policy import NetworkPolicy, PolicyRule

        if "policy" not in _state:
            _state["policy"] = NetworkPolicy()

        policy: NetworkPolicy = _state["policy"]  # type: ignore[assignment]
        parts = args.strip().split()
        sub = parts[0].lower() if parts else ""

        if sub == "list":
            rules = policy.rules()
            if not rules:
                return "No policy rules."
            lines = [f"Policy rules ({len(rules)}):"]
            for r in rules:
                port_s = f":{r.port}" if r.port else ""
                lines.append(f"  {r.pattern}{port_s} -> {r.effect}  {r.description}")
            return "\n".join(lines)

        if sub == "add":
            if len(parts) < 3:
                return "Usage: /net-policy add <pattern> <allow|deny>"
            pattern, effect = parts[1], parts[2].lower()
            if effect not in ("allow", "deny"):
                return "Effect must be 'allow' or 'deny'."
            rule = PolicyRule(pattern=pattern, effect=effect)
            policy.add_rule(rule)
            return f"Added rule: {pattern} -> {effect}"

        if sub == "remove":
            if len(parts) < 2:
                return "Usage: /net-policy remove <pattern>"
            removed = policy.remove_rule(parts[1])
            return f"Removed rule '{parts[1]}'." if removed else f"Rule '{parts[1]}' not found."

        if sub == "eval":
            if len(parts) < 2:
                return "Usage: /net-policy eval <host> [port]"
            host = parts[1]
            port = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else None
            ev = policy.evaluate(host, port)
            status = "ALLOWED" if ev.allowed else "DENIED"
            return f"[{status}] {ev.host}:{ev.port or '*'} — {ev.reason}"

        summary = policy.summary()
        return json.dumps(summary, indent=2)

    registry.register(SlashCommand("net-policy", "Manage network policies", net_policy_handler))
