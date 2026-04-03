"""Message schema validation for conversation messages."""
from __future__ import annotations

from dataclasses import dataclass, field


VALID_ROLES = frozenset({"system", "user", "assistant", "tool"})

DEFAULT_MAX_CONTENT_LENGTH = 100_000


@dataclass(frozen=True)
class ValidationResult:
    """Result of validating a single message."""

    is_valid: bool
    errors: list[str] = field(default_factory=list)


class MessageValidator:
    """Validates conversation messages against configurable rules.

    Parameters
    ----------
    max_content_length:
        Maximum allowed content length in characters.  Defaults to 100 000.
    allowed_roles:
        Set of valid role strings.  Defaults to system/user/assistant/tool.
    """

    def __init__(
        self,
        *,
        max_content_length: int = DEFAULT_MAX_CONTENT_LENGTH,
        allowed_roles: frozenset[str] | None = None,
    ) -> None:
        self._max_content_length = max_content_length
        self._allowed_roles = allowed_roles or VALID_ROLES

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate(self, message: dict) -> ValidationResult:
        """Validate a single message dict and return a ``ValidationResult``."""
        errors: list[str] = []

        if not isinstance(message, dict):
            return ValidationResult(is_valid=False, errors=["Message must be a dict."])

        # Role validation
        role = message.get("role")
        if role is None:
            errors.append("Missing required field 'role'.")
        elif role not in self._allowed_roles:
            errors.append(
                f"Invalid role '{role}'. Must be one of: {', '.join(sorted(self._allowed_roles))}."
            )

        # Content type validation
        content = message.get("content")
        if content is not None:
            if isinstance(content, str):
                if len(content) > self._max_content_length:
                    errors.append(
                        f"Content length {len(content)} exceeds maximum {self._max_content_length}."
                    )
            elif isinstance(content, list):
                for idx, block in enumerate(content):
                    if not isinstance(block, dict):
                        errors.append(
                            f"Content block at index {idx} must be a dict."
                        )
                    elif "type" not in block:
                        errors.append(
                            f"Content block at index {idx} missing required 'type' key."
                        )
                # Check total text length across blocks
                total = self._total_block_length(content)
                if total > self._max_content_length:
                    errors.append(
                        f"Total content block length {total} exceeds maximum {self._max_content_length}."
                    )
            else:
                errors.append(
                    "Content must be a string or a list of content blocks."
                )

        # tool role requires tool_call_id
        if role == "tool" and "tool_call_id" not in message:
            errors.append("Messages with role 'tool' require 'tool_call_id'.")

        return ValidationResult(is_valid=len(errors) == 0, errors=errors)

    def validate_batch(self, messages: list[dict]) -> list[ValidationResult]:
        """Validate a list of messages, returning one result per message."""
        return [self.validate(msg) for msg in messages]

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def max_content_length(self) -> int:
        return self._max_content_length

    @property
    def allowed_roles(self) -> frozenset[str]:
        return self._allowed_roles

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _total_block_length(blocks: list[dict]) -> int:
        total = 0
        for block in blocks:
            if isinstance(block, dict):
                text = block.get("text", "")
                if isinstance(text, str):
                    total += len(text)
        return total
