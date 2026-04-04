"""Slack integration — client, notification bridge, command bridge, code share."""
from __future__ import annotations

from lidco.slack.bridge import NotificationBridge
from lidco.slack.client import SlackClient
from lidco.slack.code_share import CodeShare
from lidco.slack.commands import CommandBridge

__all__ = [
    "SlackClient",
    "NotificationBridge",
    "CommandBridge",
    "CodeShare",
]
