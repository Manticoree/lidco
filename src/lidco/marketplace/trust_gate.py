"""Trust & security gate for MCP Marketplace (Task 950)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from lidco.marketplace.manifest import Capability, PluginManifest, TrustLevel


_DANGEROUS_CAPABILITIES = frozenset({Capability.EXECUTE, Capability.FILE_WRITE})


@dataclass
class TrustDecision:
    """Outcome of evaluating a plugin through the trust gate."""

    allowed: bool
    reason: str
    required_capabilities: list[Capability] = field(default_factory=list)
    trust_level: TrustLevel = TrustLevel.UNVERIFIED


class TrustGate:
    """Evaluate whether a plugin should be installed based on trust policy."""

    def __init__(
        self,
        org_allowlist: Optional[list[str]] = None,
        auto_trust_verified: bool = True,
    ) -> None:
        self._allowlist: set[str] = set(org_allowlist) if org_allowlist else set()
        self._auto_trust_verified = auto_trust_verified

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def evaluate(self, manifest: PluginManifest) -> TrustDecision:
        """Return a *TrustDecision* for the given plugin manifest."""
        # Explicitly allowed plugins always pass.
        if manifest.name in self._allowlist:
            return TrustDecision(
                allowed=True,
                reason="Plugin is on the organisation allowlist",
                required_capabilities=list(manifest.capabilities),
                trust_level=manifest.trust_level,
            )

        if manifest.trust_level == TrustLevel.VERIFIED:
            if self._auto_trust_verified:
                return TrustDecision(
                    allowed=True,
                    reason="Verified plugin auto-trusted",
                    required_capabilities=list(manifest.capabilities),
                    trust_level=TrustLevel.VERIFIED,
                )
            return TrustDecision(
                allowed=False,
                reason="Verified plugin but auto-trust is disabled",
                required_capabilities=list(manifest.capabilities),
                trust_level=TrustLevel.VERIFIED,
            )

        if manifest.trust_level == TrustLevel.COMMUNITY:
            dangerous = [c for c in manifest.capabilities if c in _DANGEROUS_CAPABILITIES]
            if dangerous:
                names = ", ".join(c.value for c in dangerous)
                return TrustDecision(
                    allowed=False,
                    reason=f"Community plugin requires dangerous capabilities: {names}",
                    required_capabilities=list(manifest.capabilities),
                    trust_level=TrustLevel.COMMUNITY,
                )
            return TrustDecision(
                allowed=True,
                reason="Community plugin with safe capabilities",
                required_capabilities=list(manifest.capabilities),
                trust_level=TrustLevel.COMMUNITY,
            )

        # UNVERIFIED — always needs confirmation
        return TrustDecision(
            allowed=False,
            reason="Unverified plugin requires manual confirmation",
            required_capabilities=list(manifest.capabilities),
            trust_level=TrustLevel.UNVERIFIED,
        )

    # ------------------------------------------------------------------
    # Allowlist management
    # ------------------------------------------------------------------

    def add_to_allowlist(self, name: str) -> None:
        """Add a plugin name to the organisation allowlist."""
        self._allowlist.add(name)

    def remove_from_allowlist(self, name: str) -> None:
        """Remove a plugin name from the allowlist."""
        self._allowlist.discard(name)

    def is_allowed(self, name: str) -> bool:
        """Check whether *name* is on the allowlist."""
        return name in self._allowlist
