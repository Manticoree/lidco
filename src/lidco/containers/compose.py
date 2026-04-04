"""ComposeManager — docker-compose generation and validation (stdlib only)."""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ServiceDef:
    """Definition of a docker-compose service."""

    name: str
    image: str
    ports: list[str] = field(default_factory=list)
    environment: dict[str, str] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)
    volumes: list[str] = field(default_factory=list)
    networks: list[str] = field(default_factory=list)
    command: str | None = None
    restart: str = "unless-stopped"


class ComposeManager:
    """Build, validate, and inspect docker-compose configurations."""

    def __init__(self) -> None:
        self._services: dict[str, ServiceDef] = {}
        self._networks: dict[str, dict[str, Any]] = {}
        self._volumes: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------------ #
    # Service management                                                   #
    # ------------------------------------------------------------------ #

    def add_service(
        self,
        name: str,
        image: str,
        ports: list[str] | None = None,
        *,
        environment: dict[str, str] | None = None,
        depends_on: list[str] | None = None,
        volumes: list[str] | None = None,
        networks: list[str] | None = None,
        command: str | None = None,
        restart: str = "unless-stopped",
    ) -> ServiceDef:
        """Add (or replace) a service and return its definition."""
        svc = ServiceDef(
            name=name,
            image=image,
            ports=list(ports or []),
            environment=dict(environment or {}),
            depends_on=list(depends_on or []),
            volumes=list(volumes or []),
            networks=list(networks or []),
            command=command,
            restart=restart,
        )
        self._services[name] = svc
        # auto-register referenced networks
        for net in svc.networks:
            if net not in self._networks:
                self._networks[net] = {}
        return svc

    def remove_service(self, name: str) -> bool:
        """Remove a service by name. Returns True if it existed."""
        return self._services.pop(name, None) is not None

    def get_service(self, name: str) -> ServiceDef | None:
        return self._services.get(name)

    def list_services(self) -> list[str]:
        return sorted(self._services)

    # ------------------------------------------------------------------ #
    # Network / volume helpers                                             #
    # ------------------------------------------------------------------ #

    def add_network(self, name: str, *, driver: str = "bridge") -> None:
        self._networks[name] = {"driver": driver}

    def networks(self) -> list[str]:
        """Return sorted list of all declared networks."""
        nets: set[str] = set(self._networks)
        for svc in self._services.values():
            nets.update(svc.networks)
        return sorted(nets)

    def add_volume(self, name: str, *, driver: str = "local") -> None:
        self._volumes[name] = {"driver": driver}

    # ------------------------------------------------------------------ #
    # YAML-ish generation (no PyYAML dependency)                           #
    # ------------------------------------------------------------------ #

    def generate(self) -> str:
        """Return a docker-compose.yml string (hand-rolled YAML)."""
        lines: list[str] = ['version: "3.9"', ""]

        if self._services:
            lines.append("services:")
            for name in sorted(self._services):
                svc = self._services[name]
                lines.append(f"  {name}:")
                lines.append(f"    image: {svc.image}")
                if svc.command:
                    lines.append(f"    command: {svc.command}")
                if svc.restart:
                    lines.append(f"    restart: {svc.restart}")
                if svc.ports:
                    lines.append("    ports:")
                    for p in svc.ports:
                        lines.append(f'      - "{p}"')
                if svc.environment:
                    lines.append("    environment:")
                    for k in sorted(svc.environment):
                        lines.append(f"      {k}: {svc.environment[k]}")
                if svc.depends_on:
                    lines.append("    depends_on:")
                    for d in svc.depends_on:
                        lines.append(f"      - {d}")
                if svc.volumes:
                    lines.append("    volumes:")
                    for v in svc.volumes:
                        lines.append(f"      - {v}")
                if svc.networks:
                    lines.append("    networks:")
                    for n in svc.networks:
                        lines.append(f"      - {n}")
                lines.append("")

        all_nets = self.networks()
        if all_nets:
            lines.append("networks:")
            for n in all_nets:
                driver = self._networks.get(n, {}).get("driver", "bridge")
                lines.append(f"  {n}:")
                lines.append(f"    driver: {driver}")
            lines.append("")

        if self._volumes:
            lines.append("volumes:")
            for v in sorted(self._volumes):
                driver = self._volumes[v].get("driver", "local")
                lines.append(f"  {v}:")
                lines.append(f"    driver: {driver}")
            lines.append("")

        return "\n".join(lines) + "\n"

    # ------------------------------------------------------------------ #
    # Validation                                                           #
    # ------------------------------------------------------------------ #

    def validate(self) -> list[str]:
        """Return a list of validation errors/warnings."""
        errors: list[str] = []
        if not self._services:
            errors.append("No services defined")
            return errors

        known = set(self._services)
        for name, svc in self._services.items():
            for dep in svc.depends_on:
                if dep not in known:
                    errors.append(f"Service '{name}' depends on unknown service '{dep}'")
            for port_mapping in svc.ports:
                parts = port_mapping.split(":")
                if len(parts) != 2:
                    errors.append(f"Service '{name}': invalid port mapping '{port_mapping}'")

        # Detect port conflicts
        host_ports: dict[str, str] = {}
        for name, svc in self._services.items():
            for pm in svc.ports:
                parts = pm.split(":")
                if len(parts) == 2:
                    hp = parts[0]
                    if hp in host_ports and host_ports[hp] != name:
                        errors.append(
                            f"Port conflict: host port {hp} used by both "
                            f"'{host_ports[hp]}' and '{name}'"
                        )
                    host_ports[hp] = name

        return errors

    # ------------------------------------------------------------------ #
    # Dependency inspection                                                #
    # ------------------------------------------------------------------ #

    def dependencies(self, service: str) -> list[str]:
        """Return the transitive dependency list for *service*."""
        svc = self._services.get(service)
        if svc is None:
            raise ValueError(f"Unknown service: {service}")

        result: list[str] = []
        visited: set[str] = set()

        def _walk(name: str) -> None:
            s = self._services.get(name)
            if s is None:
                return
            for dep in s.depends_on:
                if dep not in visited:
                    visited.add(dep)
                    _walk(dep)
                    result.append(dep)

        _walk(service)
        return result
