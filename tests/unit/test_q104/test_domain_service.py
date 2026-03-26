"""Tests for src/lidco/domain/service.py — DomainService, ServiceRegistry."""
import pytest
from lidco.domain.service import DomainService, ServiceRegistry, DomainServiceNotFoundError


class PricingService(DomainService):
    service_name = "pricing"

    def __init__(self, tax_rate: float = 0.1):
        self.tax_rate = tax_rate

    def calculate_price(self, base: float) -> float:
        return base * (1 + self.tax_rate)

    def validate(self):
        errors = []
        if self.tax_rate < 0:
            errors.append("tax_rate must be non-negative")
        if self.tax_rate > 1:
            errors.append("tax_rate must be <= 1")
        return errors


class TestDomainService:
    def test_basic_method(self):
        svc = PricingService(tax_rate=0.2)
        assert svc.calculate_price(100) == pytest.approx(120.0)

    def test_is_valid_true(self):
        svc = PricingService(tax_rate=0.1)
        assert svc.is_valid() is True

    def test_is_valid_false(self):
        svc = PricingService(tax_rate=-0.1)
        assert svc.is_valid() is False

    def test_validate_returns_errors(self):
        svc = PricingService(tax_rate=1.5)
        errors = svc.validate()
        assert len(errors) > 0

    def test_service_name(self):
        svc = PricingService()
        assert svc.service_name == "pricing"

    def test_base_service_validates_ok(self):
        svc = DomainService()
        assert svc.validate() == []
        assert svc.is_valid() is True


class TestServiceRegistry:
    def setup_method(self):
        self.registry = ServiceRegistry()

    def test_register_and_get(self):
        svc = PricingService()
        self.registry.register("pricing", svc)
        found = self.registry.get("pricing")
        assert found is svc

    def test_get_missing_raises(self):
        with pytest.raises(DomainServiceNotFoundError) as exc:
            self.registry.get("missing")
        assert exc.value.service_name == "missing"

    def test_unregister(self):
        svc = PricingService()
        self.registry.register("pricing", svc)
        assert self.registry.unregister("pricing") is True
        with pytest.raises(DomainServiceNotFoundError):
            self.registry.get("pricing")

    def test_unregister_nonexistent(self):
        assert self.registry.unregister("nope") is False

    def test_list(self):
        self.registry.register("b_svc", PricingService())
        self.registry.register("a_svc", PricingService())
        assert self.registry.list() == ["a_svc", "b_svc"]

    def test_contains(self):
        self.registry.register("pricing", PricingService())
        assert "pricing" in self.registry
        assert "other" not in self.registry

    def test_len(self):
        assert len(self.registry) == 0
        self.registry.register("svc", PricingService())
        assert len(self.registry) == 1

    def test_clear(self):
        self.registry.register("svc", PricingService())
        self.registry.clear()
        assert len(self.registry) == 0
