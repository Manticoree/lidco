"""Certificate manager — custom CA certs, expiry monitoring (Q263)."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class CertInfo:
    """Parsed certificate information."""

    subject: str
    issuer: str
    not_before: str
    not_after: str
    fingerprint: str
    is_expired: bool = False


class CertificateManager:
    """Register, inspect and monitor TLS certificates."""

    def __init__(self) -> None:
        self._certs: dict[str, CertInfo] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register(self, name: str, cert_pem: str) -> CertInfo:
        """Parse basic PEM info and register under *name*."""
        subject = self._extract_field(cert_pem, "Subject")
        issuer = self._extract_field(cert_pem, "Issuer")
        not_before = self._extract_field(cert_pem, "Not Before")
        not_after = self._extract_field(cert_pem, "Not After")
        fp = self.fingerprint(cert_pem)
        is_expired = self._check_expired(not_after)
        info = CertInfo(
            subject=subject,
            issuer=issuer,
            not_before=not_before,
            not_after=not_after,
            fingerprint=fp,
            is_expired=is_expired,
        )
        self._certs[name] = info
        return info

    def remove(self, name: str) -> bool:
        """Remove a registered cert. Returns True if it existed."""
        return self._certs.pop(name, None) is not None

    def get(self, name: str) -> CertInfo | None:
        """Retrieve cert info by name."""
        return self._certs.get(name)

    def check_expiry(self) -> list[tuple[str, CertInfo]]:
        """Return certs that are expired."""
        return [(n, c) for n, c in self._certs.items() if c.is_expired]

    def all_certs(self) -> dict[str, CertInfo]:
        """Return all registered certificates."""
        return dict(self._certs)

    def fingerprint(self, cert_pem: str) -> str:
        """Compute SHA-256 hex digest of PEM content."""
        return hashlib.sha256(cert_pem.encode()).hexdigest()

    def summary(self) -> dict:
        """Return summary statistics."""
        expired = sum(1 for c in self._certs.values() if c.is_expired)
        return {
            "total": len(self._certs),
            "expired": expired,
            "valid": len(self._certs) - expired,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_field(pem: str, field_name: str) -> str:
        """Extract a field value from PEM metadata comments."""
        pattern = rf"{re.escape(field_name)}\s*[:=]\s*(.+)"
        match = re.search(pattern, pem)
        return match.group(1).strip() if match else ""

    @staticmethod
    def _check_expired(not_after: str) -> bool:
        """Simple expiry check — looks for 'expired' marker or past year."""
        if not not_after:
            return False
        lower = not_after.lower()
        if "expired" in lower:
            return True
        # Try to detect a 4-digit year and compare
        year_match = re.search(r"(\d{4})", not_after)
        if year_match:
            year = int(year_match.group(1))
            if year < 2026:
                return True
        return False
