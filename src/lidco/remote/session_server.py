"""Remote session server — Q189, task 1057."""
from __future__ import annotations

import secrets
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass(frozen=True)
class ServerInfo:
    """Immutable descriptor for a running session server."""

    host: str
    port: int
    token: str
    url: str


class RemoteSessionServer:
    """Lightweight server that accepts remote session connections."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 0,
        auth_token: Optional[str] = None,
    ) -> None:
        self._host = host
        self._port = port
        self._auth_token = auth_token or secrets.token_hex(16)
        self._lock = threading.Lock()
        self._running = False
        self._info: Optional[ServerInfo] = None
        self._callbacks: list[Callable[[str], Any]] = []
        self._messages: list[str] = []
        self._connected: int = 0

    @property
    def is_running(self) -> bool:
        """Return True if the server is currently running."""
        with self._lock:
            return self._running

    @property
    def connected_clients(self) -> int:
        """Return the number of currently connected clients."""
        with self._lock:
            return self._connected

    def start(self) -> ServerInfo:
        """Start the server and return connection information.

        Raises RuntimeError if the server is already running.
        """
        with self._lock:
            if self._running:
                raise RuntimeError("Server is already running")
            # Assign an ephemeral port when 0 is requested
            effective_port = self._port if self._port != 0 else _allocate_port()
            self._info = ServerInfo(
                host=self._host,
                port=effective_port,
                token=self._auth_token,
                url=f"ws://{self._host}:{effective_port}",
            )
            self._running = True
            return self._info

    def stop(self) -> None:
        """Stop the server and disconnect all clients."""
        with self._lock:
            self._running = False
            self._connected = 0
            self._info = None

    def send_message(self, message: str) -> None:
        """Broadcast a message to all connected clients.

        Raises RuntimeError if the server is not running.
        """
        with self._lock:
            if not self._running:
                raise RuntimeError("Server is not running")
            self._messages.append(message)

    def on_message(self, callback: Callable[[str], Any]) -> None:
        """Register a callback to be invoked when a message is received."""
        with self._lock:
            self._callbacks.append(callback)

    # -- internal helpers used by tests / bridge ---------------------

    def _simulate_connect(self) -> None:
        """Simulate a client connection (for testing)."""
        with self._lock:
            if not self._running:
                raise RuntimeError("Server is not running")
            self._connected += 1

    def _simulate_disconnect(self) -> None:
        """Simulate a client disconnection (for testing)."""
        with self._lock:
            self._connected = max(0, self._connected - 1)

    def _simulate_receive(self, message: str) -> None:
        """Simulate receiving a message and invoke callbacks."""
        with self._lock:
            callbacks = list(self._callbacks)
        for cb in callbacks:
            cb(message)


def _allocate_port() -> int:
    """Return a pseudo-random ephemeral port number."""
    import random
    return random.randint(49152, 65535)
