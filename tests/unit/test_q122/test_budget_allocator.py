"""Tests for src/lidco/context/budget_allocator.py."""
from lidco.context.budget_allocator import BudgetAllocator, BudgetSlot, AllocationPlan


class TestBudgetSlot:
    def test_fields(self):
        slot = BudgetSlot(name="system", weight=1.0, min_tokens=256, max_tokens=1024)
        assert slot.name == "system"
        assert slot.weight == 1.0
        assert slot.min_tokens == 256
        assert slot.max_tokens == 1024

    def test_defaults(self):
        slot = BudgetSlot(name="x", weight=2.0)
        assert slot.min_tokens == 0
        assert slot.max_tokens == 0


class TestAllocationPlan:
    def test_fields(self):
        plan = AllocationPlan(total=1000, slots={"a": 500, "b": 500}, overflow=False)
        assert plan.total == 1000
        assert plan.slots["a"] == 500
        assert plan.overflow is False


class TestBudgetAllocator:
    def test_init(self):
        ba = BudgetAllocator(total_budget=4096)
        assert ba._total == 4096

    def test_add_slot(self):
        ba = BudgetAllocator(1000)
        ba.add_slot(BudgetSlot("system", 1.0))
        assert "system" in ba._slots

    def test_remove_slot(self):
        ba = BudgetAllocator(1000)
        ba.add_slot(BudgetSlot("system", 1.0))
        ba.remove_slot("system")
        assert "system" not in ba._slots

    def test_remove_slot_not_present(self):
        ba = BudgetAllocator(1000)
        ba.remove_slot("nonexistent")  # should not raise

    def test_set_total(self):
        ba = BudgetAllocator(1000)
        ba.set_total(2000)
        assert ba._total == 2000

    def test_allocate_empty(self):
        ba = BudgetAllocator(1000)
        plan = ba.allocate()
        assert isinstance(plan, AllocationPlan)
        assert plan.slots == {}

    def test_allocate_single_slot(self):
        ba = BudgetAllocator(1000)
        ba.add_slot(BudgetSlot("all", 1.0))
        plan = ba.allocate()
        assert "all" in plan.slots
        assert plan.slots["all"] > 0

    def test_allocate_proportional(self):
        ba = BudgetAllocator(1000)
        ba.add_slot(BudgetSlot("a", 1.0))
        ba.add_slot(BudgetSlot("b", 3.0))
        plan = ba.allocate()
        # b should get ~3x more than a
        assert plan.slots["b"] > plan.slots["a"]

    def test_allocate_respects_min(self):
        ba = BudgetAllocator(1000)
        ba.add_slot(BudgetSlot("small", 0.1, min_tokens=200))
        ba.add_slot(BudgetSlot("large", 10.0))
        plan = ba.allocate()
        assert plan.slots["small"] >= 200

    def test_allocate_respects_max(self):
        ba = BudgetAllocator(1000)
        ba.add_slot(BudgetSlot("capped", 10.0, max_tokens=100))
        ba.add_slot(BudgetSlot("other", 1.0))
        plan = ba.allocate()
        assert plan.slots["capped"] <= 100

    def test_allocate_overflow_flag(self):
        ba = BudgetAllocator(100)
        ba.add_slot(BudgetSlot("a", 1.0, min_tokens=60))
        ba.add_slot(BudgetSlot("b", 1.0, min_tokens=60))
        plan = ba.allocate()
        assert plan.overflow is True

    def test_allocate_no_overflow(self):
        ba = BudgetAllocator(1000)
        ba.add_slot(BudgetSlot("a", 1.0))
        ba.add_slot(BudgetSlot("b", 1.0))
        plan = ba.allocate()
        assert plan.overflow is False

    def test_allocate_returns_plan(self):
        ba = BudgetAllocator(500)
        ba.add_slot(BudgetSlot("x", 1.0))
        plan = ba.allocate()
        assert isinstance(plan, AllocationPlan)
        assert plan.total == 500

    def test_allocate_zero_weight(self):
        ba = BudgetAllocator(1000)
        ba.add_slot(BudgetSlot("a", 0.0))
        ba.add_slot(BudgetSlot("b", 0.0))
        plan = ba.allocate()
        assert isinstance(plan, AllocationPlan)

    def test_allocate_all_slots_present(self):
        ba = BudgetAllocator(1000)
        for name in ["a", "b", "c", "d"]:
            ba.add_slot(BudgetSlot(name, 1.0))
        plan = ba.allocate()
        assert all(name in plan.slots for name in ["a", "b", "c", "d"])
