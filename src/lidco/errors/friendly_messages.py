"""Q152: Translate technical errors into friendly, actionable messages."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FriendlyError:
    technical: str
    friendly: str
    suggestions: list[str] = field(default_factory=list)
    docs_hint: Optional[str] = None


class FriendlyMessages:
    """Registry of user-friendly error translations."""

    def __init__(self) -> None:
        self._registry: dict[str, dict] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register(
        self,
        error_type: str,
        friendly: str,
        suggestions: list[str],
        docs_hint: str | None = None,
    ) -> None:
        """Map *error_type* (class name) to a friendly translation."""
        self._registry[error_type] = {
            "friendly": friendly,
            "suggestions": list(suggestions),
            "docs_hint": docs_hint,
        }

    def translate(self, error: Exception) -> FriendlyError:
        """Convert *error* to a FriendlyError using the registry."""
        err_type = type(error).__name__
        technical = f"{err_type}: {error}"

        entry = self._registry.get(err_type)
        if entry is None:
            return FriendlyError(
                technical=technical,
                friendly=f"An unexpected error occurred: {error}",
                suggestions=["Check the traceback for details."],
            )

        return FriendlyError(
            technical=technical,
            friendly=entry["friendly"],
            suggestions=list(entry["suggestions"]),
            docs_hint=entry["docs_hint"],
        )

    def format(self, fe: FriendlyError) -> str:
        """Format a FriendlyError as a multi-line string."""
        lines: list[str] = []
        lines.append(f"Error: {fe.friendly}")
        lines.append(f"Technical: {fe.technical}")
        if fe.suggestions:
            lines.append("Suggestions:")
            for i, s in enumerate(fe.suggestions, 1):
                lines.append(f"  {i}. {s}")
        if fe.docs_hint:
            lines.append(f"Docs: {fe.docs_hint}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def with_defaults(cls) -> "FriendlyMessages":
        """Return a FriendlyMessages instance with common translations."""
        fm = cls()
        fm.register(
            "ModuleNotFoundError",
            "A required Python package is missing.",
            ["Run 'pip install <package>' to install it.", "Check your virtual environment is activated."],
            "https://docs.python.org/3/library/exceptions.html#ModuleNotFoundError",
        )
        fm.register(
            "FileNotFoundError",
            "The specified file or directory does not exist.",
            ["Double-check the file path.", "Ensure the file has not been moved or deleted."],
            "https://docs.python.org/3/library/exceptions.html#FileNotFoundError",
        )
        fm.register(
            "PermissionError",
            "You do not have permission to access this resource.",
            ["Check file permissions.", "Try running with elevated privileges."],
            "https://docs.python.org/3/library/exceptions.html#PermissionError",
        )
        fm.register(
            "SyntaxError",
            "There is a syntax error in the code.",
            ["Check for missing colons, brackets, or parentheses.", "Verify indentation is correct."],
            "https://docs.python.org/3/library/exceptions.html#SyntaxError",
        )
        fm.register(
            "ValueError",
            "An invalid value was provided.",
            ["Check the input data type and range.", "Ensure the value matches the expected format."],
        )
        fm.register(
            "TypeError",
            "An operation received an argument of the wrong type.",
            ["Check the types of arguments passed.", "Review function signatures."],
        )
        fm.register(
            "KeyError",
            "A required key is missing from a dictionary.",
            ["Verify the key exists before accessing it.", "Use .get() with a default value."],
        )
        fm.register(
            "ConnectionError",
            "Could not connect to the remote server.",
            ["Check your network connection.", "Verify the server URL is correct.", "Try again later."],
        )
        fm.register(
            "TimeoutError",
            "The operation took too long to complete.",
            ["Increase the timeout value.", "Check network connectivity.", "Try again later."],
        )
        fm.register(
            "ImportError",
            "A module could not be imported.",
            ["Ensure the module is installed.", "Check for circular imports."],
        )
        return fm
