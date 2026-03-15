"""Slack notification integration via incoming webhooks — Task 405."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


_ENV_WEBHOOK = "LIDCO_SLACK_WEBHOOK"


def _load_webhook_from_config() -> str | None:
    """Attempt to read slack.webhook_url from ~/.lidco/config.yaml."""
    config_path = Path.home() / ".lidco" / "config.yaml"
    if not config_path.exists():
        return None
    try:
        import re
        content = config_path.read_text(encoding="utf-8")
        # Simple extraction — avoid full YAML dependency
        match = re.search(r"webhook_url\s*:\s*(.+)", content)
        if match:
            return match.group(1).strip().strip('"').strip("'")
    except OSError:
        pass
    return None


class SlackNotifier:
    """Send messages to Slack via an incoming webhook URL.

    Args:
        webhook_url: The Slack incoming webhook URL.  If omitted, the value
            is read from the ``LIDCO_SLACK_WEBHOOK`` environment variable or
            ``~/.lidco/config.yaml`` ``slack.webhook_url``.

    Raises:
        ValueError: If no webhook URL can be found.
    """

    def __init__(self, webhook_url: str | None = None) -> None:
        if webhook_url:
            self._webhook_url = webhook_url
        else:
            self._webhook_url = (
                os.environ.get(_ENV_WEBHOOK)
                or _load_webhook_from_config()
                or ""
            )

    @property
    def webhook_url(self) -> str:
        return self._webhook_url

    def send(self, text: str, channel: str | None = None) -> bool:
        """Send a plain-text message to Slack.

        Args:
            text: Message text.
            channel: Optional channel override (e.g. ``#general``).

        Returns:
            True on success.

        Raises:
            ValueError: If no webhook URL is configured.
            RuntimeError: If the HTTP request fails.
        """
        if not self._webhook_url:
            raise ValueError(
                f"No Slack webhook URL configured. Set {_ENV_WEBHOOK} env var "
                "or add slack.webhook_url to ~/.lidco/config.yaml"
            )

        payload: dict[str, Any] = {"text": text}
        if channel:
            payload["channel"] = channel

        return self._post(payload)

    def send_blocks(
        self, blocks: list[dict[str, Any]], channel: str | None = None
    ) -> bool:
        """Send a Block Kit message to Slack.

        Args:
            blocks: List of Block Kit block objects.
            channel: Optional channel override.

        Returns:
            True on success.

        Raises:
            ValueError: If no webhook URL is configured.
            RuntimeError: If the HTTP request fails.
        """
        if not self._webhook_url:
            raise ValueError(
                f"No Slack webhook URL configured. Set {_ENV_WEBHOOK} env var "
                "or add slack.webhook_url to ~/.lidco/config.yaml"
            )

        payload: dict[str, Any] = {"blocks": blocks}
        if channel:
            payload["channel"] = channel

        return self._post(payload)

    def notify_task_done(self, description: str, elapsed: float) -> bool:
        """Send a formatted task completion notification.

        Args:
            description: Short task description.
            elapsed: Time taken in seconds.

        Returns:
            True on success.
        """
        mins, secs = divmod(int(elapsed), 60)
        duration = f"{mins}m {secs}s" if mins else f"{secs}s"
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":white_check_mark: *Task completed* in {duration}\n>{description}",
                },
            }
        ]
        return self.send_blocks(blocks)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _post(self, payload: dict[str, Any]) -> bool:
        """POST a JSON payload to the configured webhook.

        Returns:
            True on success.

        Raises:
            RuntimeError: On HTTP error.
        """
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self._webhook_url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                if resp.status not in (200, 201, 204):
                    raise RuntimeError(
                        f"Slack webhook returned HTTP {resp.status}"
                    )
        except urllib.error.HTTPError as exc:
            raise RuntimeError(
                f"Slack webhook HTTP error: {exc.code} {exc.reason}"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"Slack webhook request failed: {exc.reason}"
            ) from exc
        return True
