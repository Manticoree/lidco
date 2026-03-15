"""Q55/372 — Cross-platform desktop notifications.

Sends a system notification when a long-running task completes.
Supports Windows (PowerShell toast), macOS (osascript) and Linux (notify-send).
Fails silently if the platform or dependencies are unavailable.
"""
from __future__ import annotations

import logging
import platform
import subprocess
import sys

logger = logging.getLogger(__name__)

_SYSTEM = platform.system()


def _notify_windows(title: str, message: str) -> None:
    script = (
        f"[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, "
        f"ContentType = WindowsRuntime] > $null; "
        f"$xml = [Windows.UI.Notifications.ToastNotificationManager]"
        f"::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02); "
        f"$xml.GetElementsByTagName('text')[0].AppendChild($xml.CreateTextNode('{title}')); "
        f"$xml.GetElementsByTagName('text')[1].AppendChild($xml.CreateTextNode('{message}')); "
        f"$toast = [Windows.UI.Notifications.ToastNotification]::new($xml); "
        f"[Windows.UI.Notifications.ToastNotificationManager]"
        f"::CreateToastNotifier('LIDCO').Show($toast);"
    )
    subprocess.run(
        ["powershell.exe", "-NonInteractive", "-Command", script],
        capture_output=True,
        timeout=5,
    )


def _notify_macos(title: str, message: str) -> None:
    subprocess.run(
        [
            "osascript", "-e",
            f'display notification "{message}" with title "{title}"',
        ],
        capture_output=True,
        timeout=5,
    )


def _notify_linux(title: str, message: str) -> None:
    subprocess.run(
        ["notify-send", title, message, "--app-name=LIDCO"],
        capture_output=True,
        timeout=5,
    )


def notify(title: str = "LIDCO", message: str = "Задача выполнена") -> None:
    """Send a desktop notification. Fails silently on any error."""
    try:
        if _SYSTEM == "Windows":
            _notify_windows(title, message)
        elif _SYSTEM == "Darwin":
            _notify_macos(title, message)
        elif _SYSTEM == "Linux":
            _notify_linux(title, message)
        else:
            logger.debug("Desktop notifications not supported on %s", _SYSTEM)
    except Exception as exc:
        logger.debug("Notification failed: %s", exc)


def notify_task_done(description: str, elapsed_seconds: float, min_seconds: float = 30.0) -> None:
    """Send a notification only if the task took longer than min_seconds."""
    if elapsed_seconds < min_seconds:
        return
    minutes = int(elapsed_seconds) // 60
    secs = int(elapsed_seconds) % 60
    time_str = f"{minutes}m {secs}s" if minutes else f"{secs}s"
    message = f"{description[:60]} завершено за {time_str}"
    notify("LIDCO — Готово", message)
