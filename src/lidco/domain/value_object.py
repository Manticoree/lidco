"""ValueObject — immutable, equality-by-value domain primitives (stdlib only)."""
from __future__ import annotations

from typing import Any


class ValueObject:
    """
    Base class for value objects.

    Value objects are immutable and compare by structural equality.
    Subclasses should define fields as class-level annotations and
    pass them to ``__init__``.

    Example::

        class Money(ValueObject):
            def __init__(self, amount: float, currency: str) -> None:
                super().__init__(amount=amount, currency=currency)
    """

    def __init__(self, **fields: Any) -> None:
        object.__setattr__(self, "_fields", dict(fields))
        for key, val in fields.items():
            object.__setattr__(self, key, val)

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError(f"ValueObject is immutable — cannot set {name!r}")

    def __eq__(self, other: object) -> bool:
        if type(other) is not type(self):
            return False
        return self._fields == other._fields  # type: ignore[attr-defined]

    def __hash__(self) -> int:
        return hash((type(self).__name__, tuple(sorted(self._fields.items()))))

    def __repr__(self) -> str:
        parts = ", ".join(f"{k}={v!r}" for k, v in self._fields.items())
        return f"{type(self).__name__}({parts})"

    def to_dict(self) -> dict[str, Any]:
        """Return a shallow copy of the fields dict."""
        return dict(self._fields)

    def copy_with(self, **overrides: Any) -> "ValueObject":
        """Return a new instance with some fields overridden."""
        new_fields = {**self._fields, **overrides}
        return type(self)(**new_fields)


class Money(ValueObject):
    """A monetary value object."""

    def __init__(self, amount: float, currency: str = "USD") -> None:
        super().__init__(amount=float(amount), currency=str(currency).upper())

    def add(self, other: "Money") -> "Money":
        if self.currency != other.currency:
            raise ValueError(
                f"Cannot add {self.currency} and {other.currency}"
            )
        return Money(self.amount + other.amount, self.currency)

    def subtract(self, other: "Money") -> "Money":
        if self.currency != other.currency:
            raise ValueError(
                f"Cannot subtract {other.currency} from {self.currency}"
            )
        return Money(self.amount - other.amount, self.currency)

    def multiply(self, factor: float) -> "Money":
        return Money(self.amount * factor, self.currency)

    def is_positive(self) -> bool:
        return self.amount > 0

    def is_zero(self) -> bool:
        return self.amount == 0


class EmailAddress(ValueObject):
    """A validated email address value object."""

    def __init__(self, value: str) -> None:
        value = str(value).strip().lower()
        if "@" not in value or "." not in value.split("@", 1)[-1]:
            raise ValueError(f"Invalid email address: {value!r}")
        super().__init__(value=value)

    @property
    def domain(self) -> str:
        return self.value.split("@", 1)[1]

    @property
    def local_part(self) -> str:
        return self.value.split("@", 1)[0]


class PhoneNumber(ValueObject):
    """A normalized phone number value object (digits only)."""

    def __init__(self, value: str) -> None:
        digits = "".join(c for c in str(value) if c.isdigit())
        if len(digits) < 7:
            raise ValueError(f"Phone number too short: {value!r}")
        super().__init__(value=digits)
