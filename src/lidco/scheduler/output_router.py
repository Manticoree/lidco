"""AutomationOutputRouter — route agent results to appropriate output channels."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class DeliveryResult:
    success: bool
    output_type: str
    message: str = ""
    error: str = ""


class OutputHandler:
    """Base class for output handlers."""

    def deliver(self, result: str, context: dict) -> DeliveryResult:
        raise NotImplementedError


class LogOutputHandler(OutputHandler):
    """Logs to internal list (for testing)."""

    def __init__(self) -> None:
        self.delivered: list[tuple[str, dict]] = []

    def deliver(self, result: str, context: dict) -> DeliveryResult:
        self.delivered = [*self.delivered, (result, context)]
        return DeliveryResult(success=True, output_type="log", message=result)


class StubOutputHandler(OutputHandler):
    """Generic stub for pr/slack/linear/comment types."""

    def __init__(self, output_type: str) -> None:
        self.output_type = output_type

    def deliver(self, result: str, context: dict) -> DeliveryResult:
        return DeliveryResult(
            success=True,
            output_type=self.output_type,
            message=f"stub:{result[:50]}",
        )


class OutputRouter:
    """Route results to registered output handlers."""

    def __init__(self) -> None:
        self._handlers: dict[str, OutputHandler] = {}
        # Pre-register defaults
        self._handlers["log"] = LogOutputHandler()
        self._handlers["pr"] = StubOutputHandler("pr")
        self._handlers["slack"] = StubOutputHandler("slack")
        self._handlers["linear"] = StubOutputHandler("linear")
        self._handlers["comment"] = StubOutputHandler("comment")

    def register(self, output_type: str, handler: OutputHandler) -> None:
        """Register or override a handler for an output type."""
        self._handlers = {**self._handlers, output_type: handler}

    def route(self, result: str, output_type: str, context: dict | None = None) -> DeliveryResult:
        """Call registered handler. Return error DeliveryResult if no handler."""
        ctx = context if context is not None else {}
        handler = self._handlers.get(output_type)
        if handler is None:
            return DeliveryResult(
                success=False,
                output_type=output_type,
                error=f"No handler registered for output type '{output_type}'",
            )
        try:
            return handler.deliver(result, ctx)
        except Exception as exc:
            return DeliveryResult(
                success=False,
                output_type=output_type,
                error=str(exc),
            )

    def list_types(self) -> list[str]:
        """Return all registered output types."""
        return sorted(self._handlers.keys())
