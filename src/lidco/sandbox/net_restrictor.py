"""Network Restrictor — restricts network access based on sandbox policy."""
from __future__ import annotations

import time
from typing import List
from urllib.parse import urlparse

from lidco.sandbox.policy import PolicyViolation, SandboxPolicy

_ALWAYS_ALLOWED = frozenset({"localhost", "127.0.0.1", "::1"})


class NetworkRestrictor:
    """Restricts network access to allowed domains."""

    def __init__(self, policy: SandboxPolicy) -> None:
        self._policy = policy
        self._violations: list[PolicyViolation] = []

    @property
    def violations(self) -> List[PolicyViolation]:
        """Return list of recorded violations."""
        return list(self._violations)

    def _record_violation(self, detail: str) -> None:
        self._violations.append(
            PolicyViolation(
                violation_type="net",
                detail=detail,
                timestamp=time.time(),
                blocked=True,
            )
        )

    def check_domain(self, domain: str) -> bool:
        """Check if *domain* is allowed by policy."""
        domain = domain.strip().lower()

        # Always allow loopback
        if domain in _ALWAYS_ALLOWED:
            return True

        # If deny_all_network and no allowed domains, block everything
        if self._policy.deny_all_network and not self._policy.allowed_domains:
            self._record_violation(f"Network denied (deny_all): {domain}")
            return False

        # Check against allowed domains
        if self._policy.allowed_domains:
            for allowed in self._policy.allowed_domains:
                allowed_lower = allowed.strip().lower()
                if domain == allowed_lower or domain.endswith("." + allowed_lower):
                    return True
            self._record_violation(f"Domain not in allowed list: {domain}")
            return False

        # If not deny_all and no allowed_domains list, allow all
        if not self._policy.deny_all_network:
            return True

        self._record_violation(f"Network denied: {domain}")
        return False

    def check_url(self, url: str) -> bool:
        """Parse URL and check if its domain is allowed."""
        try:
            parsed = urlparse(url)
            hostname = parsed.hostname or ""
        except Exception:
            self._record_violation(f"Invalid URL: {url}")
            return False

        if not hostname:
            self._record_violation(f"No hostname in URL: {url}")
            return False

        return self.check_domain(hostname)
