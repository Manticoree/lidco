"""Env Provisioner — provision dev/staging/prod environments.

Template-based provisioning, auto-configure, destroy on demand.
"""

from __future__ import annotations

import copy
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EnvTier(str, Enum):
    DEV = "dev"
    STAGING = "staging"
    PROD = "prod"


class EnvStatus(str, Enum):
    PENDING = "pending"
    PROVISIONING = "provisioning"
    ACTIVE = "active"
    DESTROYING = "destroying"
    DESTROYED = "destroyed"
    FAILED = "failed"


@dataclass(frozen=True)
class EnvTemplate:
    """Blueprint for an environment."""

    name: str
    tier: EnvTier
    config: dict[str, Any] = field(default_factory=dict)
    resources: dict[str, Any] = field(default_factory=dict)
    tags: dict[str, str] = field(default_factory=dict)


@dataclass
class Environment:
    """A provisioned environment instance."""

    env_id: str
    name: str
    tier: EnvTier
    status: EnvStatus
    config: dict[str, Any]
    resources: dict[str, Any]
    tags: dict[str, str]
    created_at: float
    updated_at: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "env_id": self.env_id,
            "name": self.name,
            "tier": self.tier.value,
            "status": self.status.value,
            "config": self.config,
            "resources": self.resources,
            "tags": self.tags,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class ProvisionError(Exception):
    """Raised when provisioning fails."""


class EnvProvisioner:
    """Provision and manage environments from templates."""

    def __init__(self) -> None:
        self._templates: dict[str, EnvTemplate] = {}
        self._environments: dict[str, Environment] = {}

    # -- Template management --------------------------------------------------

    def register_template(self, template: EnvTemplate) -> None:
        self._templates[template.name] = template

    def get_template(self, name: str) -> EnvTemplate | None:
        return self._templates.get(name)

    def list_templates(self) -> list[EnvTemplate]:
        return list(self._templates.values())

    # -- Default configs per tier ---------------------------------------------

    _TIER_DEFAULTS: dict[EnvTier, dict[str, Any]] = {
        EnvTier.DEV: {"replicas": 1, "debug": True, "log_level": "DEBUG"},
        EnvTier.STAGING: {"replicas": 2, "debug": False, "log_level": "INFO"},
        EnvTier.PROD: {"replicas": 3, "debug": False, "log_level": "WARNING"},
    }

    def _auto_configure(self, template: EnvTemplate) -> dict[str, Any]:
        """Merge tier defaults with template config (template wins)."""
        base = dict(self._TIER_DEFAULTS.get(template.tier, {}))
        base.update(template.config)
        return base

    # -- Provisioning ---------------------------------------------------------

    def provision(
        self,
        template_name: str,
        *,
        name_override: str | None = None,
        extra_config: dict[str, Any] | None = None,
        extra_tags: dict[str, str] | None = None,
    ) -> Environment:
        """Provision a new environment from a registered template."""
        template = self._templates.get(template_name)
        if template is None:
            raise ProvisionError(f"Template not found: {template_name}")

        env_name = name_override or f"{template.name}-{uuid.uuid4().hex[:8]}"

        # Check for duplicate active names
        for env in self._environments.values():
            if env.name == env_name and env.status not in (
                EnvStatus.DESTROYED,
                EnvStatus.FAILED,
            ):
                raise ProvisionError(f"Active environment already exists: {env_name}")

        config = self._auto_configure(template)
        if extra_config:
            config.update(extra_config)

        tags = dict(template.tags)
        if extra_tags:
            tags.update(extra_tags)

        now = time.time()
        env = Environment(
            env_id=uuid.uuid4().hex,
            name=env_name,
            tier=template.tier,
            status=EnvStatus.ACTIVE,
            config=config,
            resources=copy.deepcopy(template.resources),
            tags=tags,
            created_at=now,
            updated_at=now,
        )
        self._environments[env.env_id] = env
        return env

    # -- Query ----------------------------------------------------------------

    def get(self, env_id: str) -> Environment | None:
        return self._environments.get(env_id)

    def list_environments(
        self,
        *,
        tier: EnvTier | None = None,
        status: EnvStatus | None = None,
    ) -> list[Environment]:
        result: list[Environment] = []
        for env in self._environments.values():
            if tier is not None and env.tier != tier:
                continue
            if status is not None and env.status != status:
                continue
            result.append(env)
        return result

    # -- Destroy --------------------------------------------------------------

    def destroy(self, env_id: str) -> Environment:
        """Mark environment as destroyed."""
        env = self._environments.get(env_id)
        if env is None:
            raise ProvisionError(f"Environment not found: {env_id}")
        if env.status == EnvStatus.DESTROYED:
            raise ProvisionError(f"Environment already destroyed: {env_id}")

        env.status = EnvStatus.DESTROYED
        env.updated_at = time.time()
        return env
