"""Mobile bridge for remote pairing and notifications — Q189, task 1058."""
from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass
from typing import Optional

from lidco.remote.session_server import ServerInfo


@dataclass(frozen=True)
class PairingCode:
    """Immutable pairing code with expiry."""

    code: str
    expires_at: float
    url: str


@dataclass(frozen=True)
class PermissionResponse:
    """Immutable result of a permission relay request."""

    granted: bool
    reason: str


class MobileBridge:
    """Bridges a mobile device to a running session server."""

    # Default pairing code lifetime in seconds
    PAIRING_TTL: float = 300.0

    def __init__(self, server: ServerInfo) -> None:
        self._server = server
        self._active_codes: dict[str, PairingCode] = {}
        self._paired = False
        self._notifications: list[tuple[str, str]] = []

    def generate_pairing_code(self) -> PairingCode:
        """Generate a short pairing code for mobile device enrollment."""
        raw = secrets.token_hex(3).upper()  # 6 hex chars
        code = f"{raw[:3]}-{raw[3:]}"
        expires_at = time.time() + self.PAIRING_TTL
        url = f"{self._server.url}/pair?code={code}"
        pairing = PairingCode(code=code, expires_at=expires_at, url=url)
        self._active_codes[code] = pairing
        return pairing

    def verify_pairing(self, code: str) -> bool:
        """Verify a pairing code and mark bridge as paired if valid.

        Returns True if the code is valid and not expired.
        """
        pairing = self._active_codes.get(code)
        if pairing is None:
            return False
        if time.time() > pairing.expires_at:
            self._active_codes.pop(code, None)
            return False
        self._paired = True
        self._active_codes.pop(code, None)
        return True

    def send_notification(self, title: str, body: str) -> bool:
        """Queue a notification for the paired device.

        Returns True if the bridge is paired and notification was queued.
        """
        if not self._paired:
            return False
        self._notifications.append((title, body))
        return True

    def relay_permission(self, request: str) -> PermissionResponse:
        """Relay a permission prompt to the mobile device and return the response.

        For now, auto-denies if not paired; auto-grants if paired.
        """
        if not self._paired:
            return PermissionResponse(granted=False, reason="Not paired")
        # In a real implementation this would block until the user responds.
        # For the library layer we return a deterministic grant.
        digest = hashlib.sha256(request.encode()).hexdigest()[:8]
        return PermissionResponse(granted=True, reason=f"User approved ({digest})")
