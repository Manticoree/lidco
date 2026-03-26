"""Tests for src/lidco/domain/value_object.py — ValueObject, Money, EmailAddress, PhoneNumber."""
import pytest
from lidco.domain.value_object import ValueObject, Money, EmailAddress, PhoneNumber


class Point(ValueObject):
    def __init__(self, x: float, y: float) -> None:
        super().__init__(x=x, y=y)


class TestValueObject:
    def test_fields_set(self):
        p = Point(1.0, 2.0)
        assert p.x == 1.0
        assert p.y == 2.0

    def test_equality_by_value(self):
        p1 = Point(1.0, 2.0)
        p2 = Point(1.0, 2.0)
        assert p1 == p2

    def test_inequality_different_values(self):
        p1 = Point(1.0, 2.0)
        p2 = Point(3.0, 4.0)
        assert p1 != p2

    def test_inequality_different_types(self):
        p = Point(1.0, 2.0)
        assert p != (1.0, 2.0)

    def test_hash_equal_for_equal_objects(self):
        p1 = Point(1.0, 2.0)
        p2 = Point(1.0, 2.0)
        assert hash(p1) == hash(p2)

    def test_hash_usable_in_set(self):
        s = {Point(1, 2), Point(1, 2), Point(3, 4)}
        assert len(s) == 2

    def test_immutable(self):
        p = Point(1.0, 2.0)
        with pytest.raises(AttributeError):
            p.x = 99.0

    def test_repr(self):
        p = Point(1.0, 2.0)
        assert "Point" in repr(p)

    def test_to_dict(self):
        p = Point(1.0, 2.0)
        d = p.to_dict()
        assert d == {"x": 1.0, "y": 2.0}

    def test_copy_with(self):
        p = Point(1.0, 2.0)
        p2 = p.copy_with(x=99.0)
        assert p2.x == 99.0
        assert p2.y == 2.0
        assert p.x == 1.0  # original unchanged


class TestMoney:
    def test_create(self):
        m = Money(10.0, "USD")
        assert m.amount == 10.0
        assert m.currency == "USD"

    def test_currency_uppercased(self):
        m = Money(5.0, "usd")
        assert m.currency == "USD"

    def test_add_same_currency(self):
        result = Money(10.0, "USD").add(Money(5.0, "USD"))
        assert result.amount == 15.0

    def test_add_different_currency_raises(self):
        with pytest.raises(ValueError):
            Money(10.0, "USD").add(Money(5.0, "EUR"))

    def test_subtract(self):
        result = Money(10.0, "USD").subtract(Money(3.0, "USD"))
        assert result.amount == pytest.approx(7.0)

    def test_multiply(self):
        result = Money(10.0, "USD").multiply(1.5)
        assert result.amount == pytest.approx(15.0)

    def test_is_positive(self):
        assert Money(1.0, "USD").is_positive() is True
        assert Money(0.0, "USD").is_positive() is False
        assert Money(-1.0, "USD").is_positive() is False

    def test_is_zero(self):
        assert Money(0.0, "USD").is_zero() is True
        assert Money(1.0, "USD").is_zero() is False

    def test_equality(self):
        assert Money(10.0, "USD") == Money(10.0, "USD")
        assert Money(10.0, "USD") != Money(10.0, "EUR")

    def test_immutable(self):
        m = Money(10.0, "USD")
        with pytest.raises(AttributeError):
            m.amount = 99.0


class TestEmailAddress:
    def test_valid_email(self):
        e = EmailAddress("User@Example.COM")
        assert e.value == "user@example.com"

    def test_domain(self):
        e = EmailAddress("user@example.com")
        assert e.domain == "example.com"

    def test_local_part(self):
        e = EmailAddress("user@example.com")
        assert e.local_part == "user"

    def test_invalid_no_at(self):
        with pytest.raises(ValueError):
            EmailAddress("notanemail")

    def test_invalid_no_dot_in_domain(self):
        with pytest.raises(ValueError):
            EmailAddress("user@nodot")

    def test_equality(self):
        assert EmailAddress("a@b.com") == EmailAddress("a@b.com")


class TestPhoneNumber:
    def test_valid_phone(self):
        p = PhoneNumber("+1 (555) 123-4567")
        assert p.value == "15551234567"

    def test_too_short_raises(self):
        with pytest.raises(ValueError):
            PhoneNumber("123")

    def test_equality(self):
        assert PhoneNumber("1234567890") == PhoneNumber("123-456-7890")
