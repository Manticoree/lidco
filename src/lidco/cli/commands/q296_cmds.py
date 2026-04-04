"""
Q296 CLI commands — /dockerfile, /compose, /k8s, /container-debug

Registered via register_q296_commands(registry).
"""
from __future__ import annotations

import shlex


def register_q296_commands(registry) -> None:
    """Register Q296 slash commands onto the given registry."""

    # ------------------------------------------------------------------ #
    # /dockerfile — Generate and scan Dockerfiles                          #
    # ------------------------------------------------------------------ #
    async def dockerfile_handler(args: str) -> str:
        """
        Usage: /dockerfile generate <language> [framework]
               /dockerfile optimize <path>
               /dockerfile scan <path>
        """
        from lidco.containers.dockerfile import DockerfileGenerator

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /dockerfile <subcommand>\n"
                "  generate <language> [framework]  generate a Dockerfile\n"
                "  optimize <path>                  optimize an existing Dockerfile\n"
                "  scan <path>                      security scan a Dockerfile"
            )

        subcmd = parts[0].lower()
        gen = DockerfileGenerator()

        if subcmd == "generate":
            if len(parts) < 2:
                return "Error: language required. Usage: /dockerfile generate <language> [framework]"
            language = parts[1]
            framework = parts[2] if len(parts) > 2 else None
            try:
                result = gen.generate(language, framework)
            except ValueError as exc:
                return f"Error: {exc}"
            return f"Generated Dockerfile:\n\n{result}"

        if subcmd == "optimize":
            if len(parts) < 2:
                return "Error: path required. Usage: /dockerfile optimize <path>"
            from pathlib import Path

            path = Path(parts[1])
            try:
                content = path.read_text(encoding="utf-8")
            except FileNotFoundError:
                return f"Error: file not found: {parts[1]}"
            optimized = gen.optimize(content)
            return f"Optimized Dockerfile:\n\n{optimized}"

        if subcmd == "scan":
            if len(parts) < 2:
                return "Error: path required. Usage: /dockerfile scan <path>"
            from pathlib import Path

            path = Path(parts[1])
            try:
                content = path.read_text(encoding="utf-8")
            except FileNotFoundError:
                return f"Error: file not found: {parts[1]}"
            warnings = gen.security_scan(content)
            if not warnings:
                return "No security issues found."
            return "Security scan results:\n" + "\n".join(f"  - {w}" for w in warnings)

        return f"Unknown subcommand '{subcmd}'. Use generate/optimize/scan."

    registry.register_async("dockerfile", "Generate, optimize, and scan Dockerfiles", dockerfile_handler)

    # ------------------------------------------------------------------ #
    # /compose — Docker Compose management                                 #
    # ------------------------------------------------------------------ #
    _compose_state: dict[str, object] = {}

    async def compose_handler(args: str) -> str:
        """
        Usage: /compose add <name> <image> [--port <host:container>]
               /compose remove <name>
               /compose generate
               /compose validate
               /compose deps <service>
               /compose list
        """
        from lidco.containers.compose import ComposeManager

        if "mgr" not in _compose_state:
            _compose_state["mgr"] = ComposeManager()

        mgr: ComposeManager = _compose_state["mgr"]  # type: ignore[assignment]

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /compose <subcommand>\n"
                "  add <name> <image> [--port host:container]  add a service\n"
                "  remove <name>                               remove a service\n"
                "  generate                                    output docker-compose.yml\n"
                "  validate                                    validate configuration\n"
                "  deps <service>                              show dependencies\n"
                "  list                                        list services"
            )

        subcmd = parts[0].lower()

        if subcmd == "add":
            if len(parts) < 3:
                return "Error: Usage: /compose add <name> <image> [--port host:container]"
            name, image = parts[1], parts[2]
            ports: list[str] = []
            i = 3
            while i < len(parts):
                if parts[i] == "--port" and i + 1 < len(parts):
                    i += 1
                    ports.append(parts[i])
                i += 1
            mgr.add_service(name, image, ports)
            return f"Service '{name}' added (image={image}, ports={ports})."

        if subcmd == "remove":
            if len(parts) < 2:
                return "Error: service name required."
            removed = mgr.remove_service(parts[1])
            return f"Service '{parts[1]}' removed." if removed else f"Service '{parts[1]}' not found."

        if subcmd == "generate":
            output = mgr.generate()
            return f"docker-compose.yml:\n\n{output}"

        if subcmd == "validate":
            errors = mgr.validate()
            if not errors:
                return "Configuration is valid."
            return "Validation errors:\n" + "\n".join(f"  - {e}" for e in errors)

        if subcmd == "deps":
            if len(parts) < 2:
                return "Error: service name required."
            try:
                deps = mgr.dependencies(parts[1])
            except ValueError as exc:
                return f"Error: {exc}"
            if not deps:
                return f"Service '{parts[1]}' has no dependencies."
            return f"Dependencies of '{parts[1]}': {', '.join(deps)}"

        if subcmd == "list":
            services = mgr.list_services()
            if not services:
                return "No services defined."
            return "Services:\n" + "\n".join(f"  - {s}" for s in services)

        return f"Unknown subcommand '{subcmd}'. Use add/remove/generate/validate/deps/list."

    registry.register_async("compose", "Manage docker-compose configuration", compose_handler)

    # ------------------------------------------------------------------ #
    # /k8s — Kubernetes manifest generation                                #
    # ------------------------------------------------------------------ #
    async def k8s_handler(args: str) -> str:
        """
        Usage: /k8s deployment <name> <image> [--replicas N] [--port P]
               /k8s service <name> <port>
               /k8s ingress <name> <host> [--path /]
               /k8s helm <name>
        """
        import json as _json

        from lidco.containers.k8s import K8sManifestGenerator

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /k8s <subcommand>\n"
                "  deployment <name> <image> [--replicas N] [--port P]\n"
                "  service <name> <port>\n"
                "  ingress <name> <host> [--path /]\n"
                "  helm <name>"
            )

        subcmd = parts[0].lower()
        gen = K8sManifestGenerator()

        if subcmd == "deployment":
            if len(parts) < 3:
                return "Error: Usage: /k8s deployment <name> <image> [--replicas N] [--port P]"
            name, image = parts[1], parts[2]
            replicas = 1
            port = None
            i = 3
            while i < len(parts):
                if parts[i] == "--replicas" and i + 1 < len(parts):
                    i += 1
                    try:
                        replicas = int(parts[i])
                    except ValueError:
                        return f"Error: --replicas must be an integer, got {parts[i]!r}"
                elif parts[i] == "--port" and i + 1 < len(parts):
                    i += 1
                    try:
                        port = int(parts[i])
                    except ValueError:
                        return f"Error: --port must be an integer, got {parts[i]!r}"
                i += 1
            manifest = gen.deployment(name, image, replicas, port=port)
            return f"Deployment manifest:\n\n{_json.dumps(manifest, indent=2)}"

        if subcmd == "service":
            if len(parts) < 3:
                return "Error: Usage: /k8s service <name> <port>"
            name = parts[1]
            try:
                port = int(parts[2])
            except ValueError:
                return f"Error: port must be an integer, got {parts[2]!r}"
            manifest = gen.service(name, port)
            return f"Service manifest:\n\n{_json.dumps(manifest, indent=2)}"

        if subcmd == "ingress":
            if len(parts) < 3:
                return "Error: Usage: /k8s ingress <name> <host> [--path /]"
            name, host = parts[1], parts[2]
            path = "/"
            i = 3
            while i < len(parts):
                if parts[i] == "--path" and i + 1 < len(parts):
                    i += 1
                    path = parts[i]
                i += 1
            manifest = gen.ingress(name, host, path)
            return f"Ingress manifest:\n\n{_json.dumps(manifest, indent=2)}"

        if subcmd == "helm":
            if len(parts) < 2:
                return "Error: Usage: /k8s helm <name>"
            chart = gen.helm_chart(parts[1])
            lines = []
            for fname, content in chart.items():
                if isinstance(content, dict):
                    lines.append(f"--- {fname} ---\n{_json.dumps(content, indent=2)}")
                else:
                    lines.append(f"--- {fname} ---\n{content}")
            return "Helm chart:\n\n" + "\n\n".join(lines)

        return f"Unknown subcommand '{subcmd}'. Use deployment/service/ingress/helm."

    registry.register_async("k8s", "Generate Kubernetes manifests", k8s_handler)

    # ------------------------------------------------------------------ #
    # /container-debug — Debug running containers                          #
    # ------------------------------------------------------------------ #
    async def container_debug_handler(args: str) -> str:
        """
        Usage: /container-debug logs <container_id> [--tail N]
               /container-debug exec <container_id> <command>
               /container-debug port-forward <container> <local> <remote>
               /container-debug health <container_id>
        """
        from lidco.containers.debugger import ContainerDebugger

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /container-debug <subcommand>\n"
                "  logs <container_id> [--tail N]           view container logs\n"
                "  exec <container_id> <command>            execute command in container\n"
                "  port-forward <container> <local> <remote> configure port forwarding\n"
                "  health <container_id>                    check container health"
            )

        subcmd = parts[0].lower()
        dbg = ContainerDebugger()

        if subcmd == "logs":
            if len(parts) < 2:
                return "Error: container_id required."
            cid = parts[1]
            tail = 100
            i = 2
            while i < len(parts):
                if parts[i] == "--tail" and i + 1 < len(parts):
                    i += 1
                    try:
                        tail = int(parts[i])
                    except ValueError:
                        pass
                i += 1
            try:
                lines = dbg.logs(cid, tail=tail)
            except Exception as exc:
                return f"Error: {exc}"
            if not lines:
                return "No log output."
            return "\n".join(lines)

        if subcmd == "exec":
            if len(parts) < 3:
                return "Error: Usage: /container-debug exec <container_id> <command>"
            cid = parts[1]
            cmd = " ".join(parts[2:])
            try:
                output = dbg.exec_cmd(cid, cmd)
            except (RuntimeError, ValueError) as exc:
                return f"Error: {exc}"
            return output or "(no output)"

        if subcmd == "port-forward":
            if len(parts) < 4:
                return "Error: Usage: /container-debug port-forward <container> <local> <remote>"
            container = parts[1]
            try:
                local = int(parts[2])
                remote = int(parts[3])
            except ValueError:
                return "Error: local and remote ports must be integers."
            try:
                config = dbg.port_forward(container, local, remote)
            except ValueError as exc:
                return f"Error: {exc}"
            return f"Port forward configured: localhost:{local} -> {container}:{remote}"

        if subcmd == "health":
            if len(parts) < 2:
                return "Error: container_id required."
            try:
                result = dbg.health_check(parts[1])
            except ValueError as exc:
                return f"Error: {exc}"
            status = "running" if result.get("running") else "stopped"
            health = result.get("health", "unknown")
            return f"Container {parts[1]}: {status}, health={health}"

        return f"Unknown subcommand '{subcmd}'. Use logs/exec/port-forward/health."

    registry.register_async("container-debug", "Debug running containers", container_debug_handler)
