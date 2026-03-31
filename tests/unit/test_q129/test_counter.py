"""Tests for lidco.telemetry.counter."""
from lidco.telemetry.counter import Counter, CounterRegistry


class TestCounter:
    def setup_method(self):
        self.c = Counter("req_count")

    def test_initial_value_zero(self):
        assert self.c.value == 0.0

    def test_name(self):
        assert self.c.name == "req_count"

    def test_increment_default(self):
        val = self.c.increment()
        assert val == 1.0
        assert self.c.value == 1.0

    def test_increment_by(self):
        self.c.increment(by=5)
        assert self.c.value == 5.0

    def test_multiple_increments(self):
        self.c.increment()
        self.c.increment()
        self.c.increment()
        assert self.c.value == 3.0

    def test_decrement(self):
        self.c.increment(by=10)
        val = self.c.decrement(by=3)
        assert val == 7.0
        assert self.c.value == 7.0

    def test_decrement_default(self):
        self.c.increment(by=5)
        self.c.decrement()
        assert self.c.value == 4.0

    def test_reset(self):
        self.c.increment(by=100)
        self.c.reset()
        assert self.c.value == 0.0

    def test_returns_new_value(self):
        returned = self.c.increment(by=7)
        assert returned == self.c.value

    def test_negative_decrement(self):
        self.c.decrement(by=5)
        assert self.c.value == -5.0


class TestCounterRegistry:
    def setup_method(self):
        self.reg = CounterRegistry()

    def test_get_or_create(self):
        c = self.reg.get_or_create("hits")
        assert c.name == "hits"

    def test_get_or_create_same_instance(self):
        c1 = self.reg.get_or_create("hits")
        c2 = self.reg.get_or_create("hits")
        assert c1 is c2

    def test_get_existing(self):
        self.reg.get_or_create("hits")
        c = self.reg.get("hits")
        assert c is not None

    def test_get_missing_returns_none(self):
        assert self.reg.get("ghost") is None

    def test_all_values_empty(self):
        assert self.reg.all_values() == {}

    def test_all_values(self):
        self.reg.get_or_create("a").increment(by=3)
        self.reg.get_or_create("b").increment(by=7)
        vals = self.reg.all_values()
        assert vals["a"] == 3.0
        assert vals["b"] == 7.0

    def test_reset_all(self):
        self.reg.get_or_create("a").increment(by=10)
        self.reg.get_or_create("b").increment(by=20)
        self.reg.reset_all()
        assert all(v == 0.0 for v in self.reg.all_values().values())

    def test_names(self):
        self.reg.get_or_create("x")
        self.reg.get_or_create("y")
        assert set(self.reg.names()) == {"x", "y"}

    def test_independent_counters(self):
        c1 = self.reg.get_or_create("a")
        c2 = self.reg.get_or_create("b")
        c1.increment(by=5)
        assert c2.value == 0.0

    def test_multiple_registries_independent(self):
        r1 = CounterRegistry()
        r2 = CounterRegistry()
        r1.get_or_create("x").increment()
        assert r2.get("x") is None
