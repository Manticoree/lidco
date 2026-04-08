"""
Session State Validator.

Validates session state consistency, finds orphaned sessions, identifies
stale sessions, and performs deep integrity checks.
"""
from __future__ import annotations

import hashlib
import json
import time


# Required fields and their expected Python types for a valid session
_REQUIRED_FIELDS: dict[str, type] = {
    "session_id": str,
    "created_at": (int, float),  # type: ignore[assignment]
    "status": str,
}

_VALID_STATUSES = {"active", "idle", "closed", "error", "pending"}


class SessionStateValidator:
    """Validates session state objects for consistency and integrity."""

    def __init__(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate_consistency(self, state: dict) -> dict:
        """Validate a session state dict has required fields and consistent types.

        Returns:
            dict with keys:
                "valid" (bool): True if no errors
                "errors" (list[str]): validation error messages
                "warnings" (list[str]): non-fatal issues
        """
        errors: list[str] = []
        warnings: list[str] = []

        # Check required fields presence and types
        for field, expected_type in _REQUIRED_FIELDS.items():
            if field not in state:
                errors.append(f"Missing required field: '{field}'")
                continue
            val = state[field]
            if not isinstance(val, expected_type):
                errors.append(
                    f"Field '{field}' has wrong type: expected {expected_type}, got {type(val).__name__}"
                )

        # Validate status value
        if "status" in state and isinstance(state["status"], str):
            if state["status"] not in _VALID_STATUSES:
                warnings.append(
                    f"Unknown status value '{state['status']}'; expected one of {sorted(_VALID_STATUSES)}"
                )

        # Validate created_at is a positive timestamp
        if "created_at" in state and isinstance(state["created_at"], (int, float)):
            if state["created_at"] <= 0:
                errors.append("Field 'created_at' must be a positive timestamp")
            elif state["created_at"] > time.time() + 60:
                warnings.append("Field 'created_at' is in the future")

        # Check session_id is non-empty
        if "session_id" in state and isinstance(state["session_id"], str):
            if not state["session_id"].strip():
                errors.append("Field 'session_id' must not be empty")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
        }

    def find_orphans(self, sessions: list[dict], active_ids: set) -> list[dict]:
        """Find sessions that are not in the active_ids set.

        Args:
            sessions: List of session state dicts.
            active_ids: Set of session_id strings considered active.

        Returns:
            List of dicts with "session_id", "created_at", "status".
        """
        orphans: list[dict] = []
        for session in sessions:
            sid = session.get("session_id", "")
            if sid not in active_ids:
                orphans.append({
                    "session_id": sid,
                    "created_at": session.get("created_at", 0),
                    "status": session.get("status", "unknown"),
                })
        return orphans

    def cleanup_stale(
        self, sessions: list[dict], max_age_hours: float = 24.0
    ) -> dict:
        """Identify sessions that should be cleaned up due to age.

        Args:
            sessions: List of session state dicts.
            max_age_hours: Maximum allowed age in hours before a session is stale.

        Returns:
            dict with keys:
                "stale_count" (int): number of stale sessions
                "total_count" (int): total sessions examined
                "stale_sessions" (list[dict]): the stale session dicts
        """
        now = time.time()
        max_age_seconds = max_age_hours * 3600.0
        stale: list[dict] = []

        for session in sessions:
            created_at = session.get("created_at", 0)
            if isinstance(created_at, (int, float)):
                age = now - created_at
                if age > max_age_seconds:
                    stale.append(session)

        return {
            "stale_count": len(stale),
            "total_count": len(sessions),
            "stale_sessions": stale,
        }

    def check_integrity(self, state: dict) -> dict:
        """Perform a deep integrity check on a session state.

        Checks field consistency, detects anomalies, and computes a checksum.

        Returns:
            dict with keys:
                "integrity_ok" (bool): True if no integrity issues found
                "issues" (list[str]): detected integrity problems
                "checksum" (str): SHA-256 hex digest of the canonical state
        """
        issues: list[str] = []

        # Run basic consistency checks first
        consistency = self.validate_consistency(state)
        issues.extend(consistency["errors"])

        # Cross-field integrity checks
        if "created_at" in state and "last_active_at" in state:
            created = state["created_at"]
            last_active = state["last_active_at"]
            if isinstance(created, (int, float)) and isinstance(last_active, (int, float)):
                if last_active < created:
                    issues.append(
                        "'last_active_at' is before 'created_at' — temporal inconsistency"
                    )

        if "status" in state and state.get("status") == "active":
            if "last_active_at" not in state:
                issues.append("Active session missing 'last_active_at' field")

        # Check for any None values in top-level keys that shouldn't be None
        for key in ("session_id", "status"):
            if key in state and state[key] is None:
                issues.append(f"Field '{key}' is None — expected a non-null value")

        # Compute checksum from a canonical serialisation
        try:
            canonical = json.dumps(state, sort_keys=True, default=str)
            checksum = hashlib.sha256(canonical.encode()).hexdigest()
        except Exception:
            checksum = ""
            issues.append("Failed to compute checksum — state is not serialisable")

        return {
            "integrity_ok": len(issues) == 0,
            "issues": issues,
            "checksum": checksum,
        }
