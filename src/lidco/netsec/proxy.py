"""Proxy manager — HTTP/SOCKS proxy configuration (Q263)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from urllib.parse import urlparse


@dataclass
class ProxyConfig:
    """A single proxy configuration entry."""

    name: str
    url: str
    proxy_type: str = "http"
    enabled: bool = True
    providers: list[str] = field(default_factory=list)


class ProxyManager:
    """Manage HTTP/SOCKS proxy configs; per-provider matching; env auto-detect."""

    def __init__(self) -> None:
        self._configs: dict[str, ProxyConfig] = {}

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def add(self, config: ProxyConfig) -> ProxyConfig:
        """Register a proxy config. Overwrites if name already exists."""
        self._configs[config.name] = config
        return config

    def remove(self, name: str) -> bool:
        """Remove a proxy config by name. Returns True if it existed."""
        return self._configs.pop(name, None) is not None

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get_for_provider(self, provider: str) -> ProxyConfig | None:
        """Return the first enabled proxy whose providers list contains *provider*."""
        for cfg in self._configs.values():
            if cfg.enabled and provider in cfg.providers:
                return cfg
        return None

    def get_for_url(self, url: str) -> ProxyConfig | None:
        """Return the first enabled proxy matching the URL's hostname."""
        parsed = urlparse(url)
        host = parsed.hostname or ""
        for cfg in self._configs.values():
            if not cfg.enabled:
                continue
            proxy_host = urlparse(cfg.url).hostname or ""
            if proxy_host and proxy_host in host:
                return cfg
        # Fallback: return first enabled proxy
        for cfg in self._configs.values():
            if cfg.enabled:
                return cfg
        return None

    # ------------------------------------------------------------------
    # Environment detection
    # ------------------------------------------------------------------

    def detect_env(self) -> list[ProxyConfig]:
        """Read HTTP_PROXY, HTTPS_PROXY, ALL_PROXY from environment."""
        detected: list[ProxyConfig] = []
        env_vars = [
            ("HTTP_PROXY", "http"),
            ("HTTPS_PROXY", "https"),
            ("ALL_PROXY", "http"),
        ]
        for var, ptype in env_vars:
            value = os.environ.get(var) or os.environ.get(var.lower())
            if value:
                cfg = ProxyConfig(
                    name=var.lower(),
                    url=value,
                    proxy_type=ptype,
                )
                detected.append(cfg)
                self._configs[cfg.name] = cfg
        return detected

    # ------------------------------------------------------------------
    # Enable / disable
    # ------------------------------------------------------------------

    def enable(self, name: str) -> bool:
        """Enable a proxy config. Returns False if name not found."""
        cfg = self._configs.get(name)
        if cfg is None:
            return False
        cfg.enabled = True
        return True

    def disable(self, name: str) -> bool:
        """Disable a proxy config. Returns False if name not found."""
        cfg = self._configs.get(name)
        if cfg is None:
            return False
        cfg.enabled = False
        return True

    # ------------------------------------------------------------------
    # Listing / summary
    # ------------------------------------------------------------------

    def all_configs(self) -> list[ProxyConfig]:
        """Return all registered proxy configs."""
        return list(self._configs.values())

    def summary(self) -> dict:
        """Return summary statistics."""
        total = len(self._configs)
        enabled = sum(1 for c in self._configs.values() if c.enabled)
        return {
            "total": total,
            "enabled": enabled,
            "disabled": total - enabled,
        }
