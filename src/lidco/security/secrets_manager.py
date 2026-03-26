"""SecretsManager — XOR+base64 obfuscated local secrets vault (stdlib only).

NOTE: This module provides *obfuscation*, not cryptographic security. The intent
is to prevent accidental plaintext exposure in config files, not to resist a
determined attacker with filesystem access.
"""
from __future__ import annotations

import base64
import hashlib
import json
import socket
import time
from dataclasses import asdict, dataclass
from pathlib import Path


_DEFAULT_STORE = Path(".lidco") / "secrets.json"


@dataclass
class SecretEntry:
    key: str
    encrypted_value: str  # base64(XOR(value, derived_key))
    created_at: float
    updated_at: float


class SecretsManager:
    """
    Store/retrieve secrets in ``.lidco/secrets.json`` with XOR+base64 obfuscation.

    Parameters
    ----------
    store_path:
        Path to the JSON file.  Defaults to ``.lidco/secrets.json``.
    machine_key:
        Override the key derivation (useful for testing).  When *None* the key
        is derived from ``socket.gethostname()``.
    """

    def __init__(
        self,
        store_path: Path | None = None,
        machine_key: str | None = None,
    ) -> None:
        self._store_path = Path(store_path) if store_path is not None else _DEFAULT_STORE
        self._machine_key = machine_key

    # ------------------------------------------------------------------ private

    def _derive_key(self) -> bytes:
        seed = self._machine_key if self._machine_key is not None else socket.gethostname()
        return hashlib.sha256(seed.encode("utf-8")).digest()  # 32 bytes

    def _xor_bytes(self, data: bytes, key: bytes) -> bytes:
        return bytes(d ^ key[i % len(key)] for i, d in enumerate(data))

    def _encrypt(self, value: str) -> str:
        raw = value.encode("utf-8")
        obfuscated = self._xor_bytes(raw, self._derive_key())
        return base64.b64encode(obfuscated).decode("ascii")

    def _decrypt(self, token: str) -> str:
        obfuscated = base64.b64decode(token.encode("ascii"))
        raw = self._xor_bytes(obfuscated, self._derive_key())
        return raw.decode("utf-8")

    def _load(self) -> dict[str, dict]:
        if not self._store_path.exists():
            return {}
        try:
            return json.loads(self._store_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _save(self, data: dict[str, dict]) -> None:
        self._store_path.parent.mkdir(parents=True, exist_ok=True)
        self._store_path.write_text(
            json.dumps(data, indent=2, sort_keys=True), encoding="utf-8"
        )

    # ------------------------------------------------------------------ public

    def set(self, key: str, value: str) -> None:
        """Store or update *key* with *value*.

        Raises
        ------
        ValueError
            If *key* is empty or contains whitespace.
        """
        if not key or key != key.strip() or " " in key or "\t" in key:
            raise ValueError(f"Secret key must be non-empty and contain no whitespace, got {key!r}")

        data = self._load()
        now = time.time()
        existing = data.get(key)
        entry = SecretEntry(
            key=key,
            encrypted_value=self._encrypt(value),
            created_at=existing["created_at"] if existing else now,
            updated_at=now,
        )
        data = {**data, key: asdict(entry)}
        self._save(data)

    def get(self, key: str) -> str | None:
        """Return the decrypted value for *key*, or *None* if not found."""
        data = self._load()
        entry = data.get(key)
        if entry is None:
            return None
        return self._decrypt(entry["encrypted_value"])

    def delete(self, key: str) -> bool:
        """Delete *key* from the vault.  Returns *True* if it existed."""
        data = self._load()
        if key not in data:
            return False
        new_data = {k: v for k, v in data.items() if k != key}
        self._save(new_data)
        return True

    def list(self) -> list[str]:
        """Return sorted list of all stored key names."""
        return sorted(self._load().keys())

    def export_env(self) -> dict[str, str]:
        """Return ``{key: decrypted_value}`` for all stored secrets."""
        data = self._load()
        return {k: self._decrypt(v["encrypted_value"]) for k, v in data.items()}
