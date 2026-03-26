"""Template Method pattern — algorithm skeleton with overridable steps (stdlib only)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class DataProcessor(ABC):
    """
    Template method pattern for data processing pipelines.

    The ``process()`` method defines the algorithm skeleton:
    1. validate
    2. transform
    3. format
    4. post_process (hook — default no-op)

    Subclasses override ``validate``, ``transform``, and ``format``.
    """

    def process(self, data: Any) -> Any:
        """Execute the full processing pipeline."""
        self.validate(data)
        transformed = self.transform(data)
        result = self.format(transformed)
        return self.post_process(result)

    @abstractmethod
    def validate(self, data: Any) -> None:
        """Validate input.  Raise ValueError if invalid."""

    @abstractmethod
    def transform(self, data: Any) -> Any:
        """Transform data to intermediate form."""

    @abstractmethod
    def format(self, data: Any) -> Any:
        """Format intermediate result for output."""

    def post_process(self, result: Any) -> Any:
        """Hook — called after format.  Default returns result unchanged."""
        return result


class TextNormalizer(DataProcessor):
    """Normalize text: validate non-empty, strip, lowercase, capitalize."""

    def __init__(self, uppercase: bool = False) -> None:
        self._uppercase = uppercase

    def validate(self, data: Any) -> None:
        if not isinstance(data, str) or not data.strip():
            raise ValueError(f"Expected non-empty string, got {data!r}")

    def transform(self, data: str) -> str:
        return data.strip()

    def format(self, data: str) -> str:
        return data.upper() if self._uppercase else data.lower()


class NumberPipeline(DataProcessor):
    """Process a list of numbers: validate, filter negatives, format as CSV."""

    def validate(self, data: Any) -> None:
        if not isinstance(data, list):
            raise ValueError(f"Expected list, got {type(data).__name__}")

    def transform(self, data: list) -> list:
        return [x for x in data if isinstance(x, (int, float)) and x >= 0]

    def format(self, data: list) -> str:
        return ",".join(str(x) for x in data)


class ReportGenerator(DataProcessor):
    """Generic report generator."""

    def __init__(self, title: str = "Report") -> None:
        self._title = title
        self._steps: list[str] = []

    def validate(self, data: Any) -> None:
        if data is None:
            raise ValueError("Data cannot be None")
        self._steps.append("validated")

    def transform(self, data: Any) -> dict:
        self._steps.append("transformed")
        return {"title": self._title, "data": data}

    def format(self, data: dict) -> str:
        self._steps.append("formatted")
        return f"=== {data['title']} ===\n{data['data']}"

    def post_process(self, result: str) -> str:
        self._steps.append("post_processed")
        return result.strip()

    @property
    def steps_executed(self) -> list[str]:
        return list(self._steps)
