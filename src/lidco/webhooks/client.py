"""WebhookClient — send webhooks with retry and signing (stdlib only)."""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class DeliveryRecord:
    url: str
    payload: dict
    status: str
    response: Optional[str] = None
    attempt: int = 1
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = time.time()


class WebhookClient:
    """
    Send webhook payloads to external URLs with optional retry and HMAC signing.

    Parameters
    ----------
    timeout:
        HTTP request timeout in seconds.
    default_secret:
        Default secret for HMAC-SHA256 signing.
    """

    def __init__(self, timeout: float = 10.0, default_secret: str = "") -> None:
        self._timeout = timeout
        self._default_secret = default_secret
        self._log: List[DeliveryRecord] = []

    # -------------------------------------------------------- sign

    @staticmethod
    def sign_payload(payload: dict, secret: str) -> str:
        """Compute HMAC-SHA256 hex digest of JSON-serialised *payload* with *secret*."""
        body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()

    # -------------------------------------------------------- send

    def send(self, url: str, payload: dict, secret: str = "") -> dict:
        """Send *payload* as JSON POST to *url*.

        Returns dict with ``status``, ``body``, and ``signature`` (if secret provided).
        """
        secret = secret or self._default_secret
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        headers: Dict[str, str] = {"Content-Type": "application/json"}
        signature = ""
        if secret:
            signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
            headers["X-Signature-256"] = signature

        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                resp_body = resp.read().decode()
                record = DeliveryRecord(
                    url=url, payload=payload, status="ok", response=resp_body
                )
                self._log.append(record)
                return {"status": "ok", "body": resp_body, "signature": signature}
        except Exception as exc:
            record = DeliveryRecord(
                url=url, payload=payload, status="error", response=str(exc)
            )
            self._log.append(record)
            return {"status": "error", "error": str(exc), "signature": signature}

    # -------------------------------------------------------- with_retry

    def with_retry(self, url: str, payload: dict, max_retries: int = 3, secret: str = "") -> dict:
        """Send with exponential backoff retry.

        Returns the first successful result or the last failure.
        """
        last_result: dict = {}
        for attempt in range(1, max_retries + 1):
            result = self.send(url, payload, secret=secret)
            if self._log:
                self._log[-1].attempt = attempt
            if result.get("status") == "ok":
                return result
            last_result = result
            if attempt < max_retries:
                time.sleep(0.1 * (2 ** (attempt - 1)))
        return last_result

    # -------------------------------------------------------- delivery_log

    def delivery_log(self) -> list:
        """Return list of all delivery records."""
        return list(self._log)

    def clear_log(self) -> int:
        """Clear delivery log. Return count cleared."""
        count = len(self._log)
        self._log = []
        return count
