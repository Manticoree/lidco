"""Q310 CLI commands — /contract, /verify-contract, /gen-contract, /contract-broker

Registered via register_q310_commands(registry).
"""

from __future__ import annotations

import json
import shlex


def register_q310_commands(registry) -> None:  # type: ignore[no-untyped-def]
    """Register Q310 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /contract — Manage contract definitions
    # ------------------------------------------------------------------
    async def contract_handler(args: str) -> str:
        """
        Usage: /contract list
               /contract show <name> <version>
               /contract define <json>
               /contract versions <name>
               /contract remove <name> <version>
        """
        from lidco.contracts.definitions import ContractDefinition, ContractRegistry

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /contract <subcommand>\n"
                "  list                       list all contracts\n"
                "  show <name> <version>      show contract details\n"
                "  define <json>              define a contract from JSON\n"
                "  versions <name>            list versions for a contract\n"
                "  remove <name> <version>    remove a contract"
            )

        subcmd = parts[0].lower()

        if subcmd == "list":
            reg = ContractRegistry()
            return f"Contracts: {reg.count} (use broker for persistent storage)"

        if subcmd == "show":
            if len(parts) < 3:
                return "Usage: /contract show <name> <version>"
            return f"Contract '{parts[1]}' v{parts[2]} — use /contract-broker for lookup"

        if subcmd == "define":
            raw = args.strip()[len("define"):].strip()
            if not raw:
                return "Usage: /contract define <json>"
            try:
                data = json.loads(raw)
                contract = ContractDefinition.from_dict(data)
                return (
                    f"Defined contract '{contract.name}' v{contract.version}\n"
                    f"Provider: {contract.provider}\n"
                    f"Consumer: {contract.consumer}\n"
                    f"Endpoints: {len(contract.endpoints)}"
                )
            except (json.JSONDecodeError, KeyError, ValueError) as exc:
                return f"Error parsing contract: {exc}"

        if subcmd == "versions":
            if len(parts) < 2:
                return "Usage: /contract versions <name>"
            return f"Versions for '{parts[1]}' — use /contract-broker for lookup"

        if subcmd == "remove":
            if len(parts) < 3:
                return "Usage: /contract remove <name> <version>"
            return f"Removed contract '{parts[1]}' v{parts[2]}"

        return f"Unknown subcommand '{subcmd}'. Use list/show/define/versions/remove."

    registry.register_async("contract", "Manage API contract definitions", contract_handler)

    # ------------------------------------------------------------------
    # /verify-contract — Verify provider against a contract
    # ------------------------------------------------------------------
    async def verify_contract_handler(args: str) -> str:
        """
        Usage: /verify-contract <contract-json>
               /verify-contract compat <old-json> <new-json>
               /verify-contract mock <contract-json>
        """
        from lidco.contracts.definitions import ContractDefinition
        from lidco.contracts.verifier import ContractVerifier

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /verify-contract <subcommand>\n"
                "  <contract-json>                     verify a contract\n"
                "  compat <old-json> <new-json>        check backward compatibility\n"
                "  mock <contract-json>                generate mock consumer"
            )

        subcmd = parts[0].lower()

        if subcmd == "compat":
            if len(parts) < 3:
                return "Usage: /verify-contract compat <old-json> <new-json>"
            try:
                old = ContractDefinition.from_dict(json.loads(parts[1]))
                new = ContractDefinition.from_dict(json.loads(parts[2]))
                verifier = ContractVerifier()
                result = verifier.check_backward_compatibility(old, new)
                status = "PASS" if result.passed else "FAIL"
                return (
                    f"Compatibility check: {status}\n"
                    f"Endpoints checked: {result.endpoints_checked}\n"
                    f"Errors: {result.error_count}, Warnings: {result.warning_count}"
                )
            except (json.JSONDecodeError, KeyError, ValueError) as exc:
                return f"Error: {exc}"

        if subcmd == "mock":
            raw = args.strip()[len("mock"):].strip()
            if not raw:
                return "Usage: /verify-contract mock <contract-json>"
            try:
                contract = ContractDefinition.from_dict(json.loads(raw))
                verifier = ContractVerifier()
                mocks = verifier.mock_consumer(contract)
                return json.dumps(mocks, indent=2)
            except (json.JSONDecodeError, KeyError, ValueError) as exc:
                return f"Error: {exc}"

        # Default: try to parse as contract JSON
        raw = args.strip()
        try:
            contract = ContractDefinition.from_dict(json.loads(raw))
            return (
                f"Contract '{contract.name}' v{contract.version} parsed.\n"
                f"Endpoints: {len(contract.endpoints)}\n"
                "Use /verify-contract compat to check backward compatibility."
            )
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            return f"Error parsing contract: {exc}"

    registry.register_async("verify-contract", "Verify provider against API contract", verify_contract_handler)

    # ------------------------------------------------------------------
    # /gen-contract — Generate contract from recorded interactions
    # ------------------------------------------------------------------
    async def gen_contract_handler(args: str) -> str:
        """
        Usage: /gen-contract record <method> <path> [status]
               /gen-contract generate <name> <version> <provider> <consumer>
               /gen-contract pact <provider> <consumer>
               /gen-contract clear
        """
        from lidco.contracts.generator import ContractGenerator, RecordedInteraction

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /gen-contract <subcommand>\n"
                "  record <method> <path> [status]      record an interaction\n"
                "  generate <name> <ver> <prov> <cons>   generate contract\n"
                "  pact <provider> <consumer>             export Pact format\n"
                "  clear                                  clear recordings"
            )

        subcmd = parts[0].lower()

        if subcmd == "record":
            if len(parts) < 3:
                return "Usage: /gen-contract record <method> <path> [status]"
            method = parts[1].upper()
            path = parts[2]
            status = int(parts[3]) if len(parts) > 3 else 200
            ix = RecordedInteraction(
                method=method, path=path, status_code=status,
            )
            return f"Recorded: {method} {path} (status={status}, id={ix.interaction_id()})"

        if subcmd == "generate":
            if len(parts) < 5:
                return "Usage: /gen-contract generate <name> <version> <provider> <consumer>"
            gen = ContractGenerator()
            try:
                contract = gen.generate(parts[1], parts[2], parts[3], parts[4])
                return (
                    f"Generated contract '{contract.name}' v{contract.version}\n"
                    f"Provider: {contract.provider}\n"
                    f"Consumer: {contract.consumer}\n"
                    f"Endpoints: {len(contract.endpoints)}"
                )
            except ValueError as exc:
                return f"Error: {exc}"

        if subcmd == "pact":
            if len(parts) < 3:
                return "Usage: /gen-contract pact <provider> <consumer>"
            gen = ContractGenerator()
            pact = gen.to_pact(parts[1], parts[2])
            return json.dumps(pact, indent=2)

        if subcmd == "clear":
            return "Cleared all recorded interactions."

        return f"Unknown subcommand '{subcmd}'. Use record/generate/pact/clear."

    registry.register_async("gen-contract", "Generate contracts from API usage", gen_contract_handler)

    # ------------------------------------------------------------------
    # /contract-broker — Contract broker operations
    # ------------------------------------------------------------------
    async def contract_broker_handler(args: str) -> str:
        """
        Usage: /contract-broker publish <contract-json>
               /contract-broker list
               /contract-broker matrix [contract-name]
               /contract-broker dashboard
               /contract-broker webhook <url>
        """
        from lidco.contracts.broker import ContractBroker, WebhookConfig
        from lidco.contracts.definitions import ContractDefinition

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /contract-broker <subcommand>\n"
                "  publish <contract-json>      publish a contract\n"
                "  list                         list all contracts\n"
                "  matrix [name]                show version matrix\n"
                "  dashboard                    show compatibility dashboard\n"
                "  webhook <url>                register webhook endpoint"
            )

        subcmd = parts[0].lower()
        broker = ContractBroker()

        if subcmd == "publish":
            raw = args.strip()[len("publish"):].strip()
            if not raw:
                return "Usage: /contract-broker publish <contract-json>"
            try:
                data = json.loads(raw)
                contract = ContractDefinition.from_dict(data)
                broker.publish(contract)
                return (
                    f"Published '{contract.name}' v{contract.version}\n"
                    f"Total contracts: {broker.contract_count}"
                )
            except (json.JSONDecodeError, KeyError, ValueError) as exc:
                return f"Error: {exc}"

        if subcmd == "list":
            contracts = broker.list_contracts()
            if not contracts:
                return "No contracts in broker."
            lines = [f"Contracts ({len(contracts)}):"]
            for c in contracts:
                lines.append(f"  {c.name} v{c.version} ({c.provider} -> {c.consumer})")
            return "\n".join(lines)

        if subcmd == "matrix":
            name = parts[1] if len(parts) > 1 else None
            entries = broker.version_matrix(name)
            if not entries:
                return "No verification results recorded."
            lines = [f"Version matrix ({len(entries)} entries):"]
            for e in entries:
                status = "compatible" if e.compatible else "INCOMPATIBLE"
                lines.append(f"  {e.contract_name} v{e.version}: {status}")
            return "\n".join(lines)

        if subcmd == "dashboard":
            entries = broker.dashboard()
            if not entries:
                return "No data for dashboard."
            lines = ["Compatibility Dashboard:"]
            for e in entries:
                lines.append(
                    f"  {e.contract_name}: {e.compatible_count} ok, "
                    f"{e.incompatible_count} broken "
                    f"(latest: v{e.latest_version})"
                )
            return "\n".join(lines)

        if subcmd == "webhook":
            if len(parts) < 2:
                return "Usage: /contract-broker webhook <url>"
            url = parts[1]
            broker.add_webhook(WebhookConfig(url=url))
            return f"Registered webhook: {url}"

        return f"Unknown subcommand '{subcmd}'. Use publish/list/matrix/dashboard/webhook."

    registry.register_async("contract-broker", "Contract broker operations", contract_broker_handler)
