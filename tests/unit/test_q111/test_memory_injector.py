"""Tests for src/lidco/memory/injector.py."""
from unittest.mock import MagicMock, PropertyMock
from dataclasses import dataclass

from lidco.memory.injector import MemoryInjector, InjectionResult


@dataclass
class FakeMemory:
    content: str


class FakeStore:
    def __init__(self, items=None):
        self._items = items or []

    def list(self, limit=50):
        return self._items[:limit]


class FakeSeeder:
    def __init__(self, memories=None):
        self._memories = memories or []

    def seed(self):
        ctx = MagicMock()
        ctx.memories = self._memories
        return ctx


class TestInjectionResult:
    def test_fields(self):
        r = InjectionResult(prompt_block="hello", facts_included=1, facts_dropped=0, tokens_used=1)
        assert r.prompt_block == "hello"
        assert r.facts_included == 1
        assert r.facts_dropped == 0
        assert r.tokens_used == 1


class TestMemoryInjector:
    def test_no_stores(self):
        inj = MemoryInjector()
        result = inj.compose()
        assert result.facts_included == 0
        assert result.prompt_block == ""
        assert result.tokens_used == 0

    def test_memory_store_only(self):
        store = FakeStore([FakeMemory("fact one"), FakeMemory("fact two")])
        inj = MemoryInjector(memory_store=store)
        result = inj.compose()
        assert result.facts_included == 2
        assert "fact one" in result.prompt_block
        assert "fact two" in result.prompt_block

    def test_session_seeder_only(self):
        seeder = FakeSeeder([FakeMemory("seeded fact")])
        inj = MemoryInjector(session_seeder=seeder)
        result = inj.compose()
        assert result.facts_included == 1
        assert "seeded fact" in result.prompt_block

    def test_both_stores_deduplicated(self):
        store = FakeStore([FakeMemory("shared fact")])
        seeder = FakeSeeder([FakeMemory("shared fact")])
        inj = MemoryInjector(memory_store=store, session_seeder=seeder)
        result = inj.compose()
        assert result.facts_included == 1

    def test_both_stores_combined(self):
        store = FakeStore([FakeMemory("store fact")])
        seeder = FakeSeeder([FakeMemory("seeder fact")])
        inj = MemoryInjector(memory_store=store, session_seeder=seeder)
        result = inj.compose()
        assert result.facts_included == 2

    def test_budget_limits_facts(self):
        facts = [FakeMemory(f"fact number {i} with some extra text to use budget") for i in range(100)]
        store = FakeStore(facts)
        inj = MemoryInjector(memory_store=store)
        result = inj.compose(budget=50)  # very small budget
        assert result.facts_included < 100
        assert result.facts_dropped > 0

    def test_tokens_used_estimate(self):
        store = FakeStore([FakeMemory("hello world")])
        inj = MemoryInjector(memory_store=store)
        result = inj.compose()
        assert result.tokens_used == len(result.prompt_block) // 4

    def test_query_relevance_scoring(self):
        store = FakeStore([
            FakeMemory("python is great"),
            FakeMemory("rust is fast"),
            FakeMemory("python testing tools"),
        ])
        inj = MemoryInjector(memory_store=store)
        result = inj.compose(query="python")
        assert result.facts_included >= 1
        # Python facts should appear before rust
        idx_python = result.prompt_block.find("python")
        idx_rust = result.prompt_block.find("rust")
        if idx_rust >= 0:
            assert idx_python < idx_rust

    def test_empty_query_includes_all(self):
        store = FakeStore([FakeMemory("a"), FakeMemory("b")])
        inj = MemoryInjector(memory_store=store)
        result = inj.compose(query="")
        assert result.facts_included == 2

    def test_inject_into_prompt_prepends(self):
        store = FakeStore([FakeMemory("remembered")])
        inj = MemoryInjector(memory_store=store)
        result = inj.inject_into_prompt("Base prompt here")
        assert result.startswith("## Remembered Context")
        assert "Base prompt here" in result

    def test_inject_into_prompt_no_facts(self):
        inj = MemoryInjector()
        result = inj.inject_into_prompt("Base prompt")
        assert result == "Base prompt"

    def test_memory_store_raises_exception(self):
        store = MagicMock()
        store.list.side_effect = RuntimeError("DB error")
        inj = MemoryInjector(memory_store=store)
        result = inj.compose()
        assert result.facts_included == 0

    def test_session_seeder_raises_exception(self):
        seeder = MagicMock()
        seeder.seed.side_effect = RuntimeError("Seeder error")
        inj = MemoryInjector(session_seeder=seeder)
        result = inj.compose()
        assert result.facts_included == 0

    def test_dict_memory_objects(self):
        store = FakeStore([{"content": "dict fact"}])
        inj = MemoryInjector(memory_store=store)
        result = inj.compose()
        assert result.facts_included == 1
        assert "dict fact" in result.prompt_block

    def test_large_budget(self):
        store = FakeStore([FakeMemory(f"fact {i}") for i in range(5)])
        inj = MemoryInjector(memory_store=store)
        result = inj.compose(budget=100000)
        assert result.facts_included == 5
        assert result.facts_dropped == 0

    def test_compose_header_present(self):
        store = FakeStore([FakeMemory("x")])
        inj = MemoryInjector(memory_store=store)
        result = inj.compose()
        assert "## Remembered Context" in result.prompt_block

    def test_compose_facts_as_bullets(self):
        store = FakeStore([FakeMemory("bullet item")])
        inj = MemoryInjector(memory_store=store)
        result = inj.compose()
        assert "- bullet item" in result.prompt_block

    def test_empty_content_skipped(self):
        store = FakeStore([FakeMemory(""), FakeMemory("real")])
        inj = MemoryInjector(memory_store=store)
        result = inj.compose()
        assert result.facts_included == 1

    def test_score_facts_no_query(self):
        inj = MemoryInjector()
        scored = inj._score_facts(["a", "b"], "")
        assert all(s == 1.0 for s, _ in scored)

    def test_score_facts_with_query(self):
        inj = MemoryInjector()
        scored = inj._score_facts(["python rocks", "java rocks"], "python")
        # python fact should score higher
        python_score = [s for s, f in scored if "python" in f][0]
        java_score = [s for s, f in scored if "java" in f][0]
        assert python_score > java_score

    def test_inject_into_prompt_with_query(self):
        store = FakeStore([FakeMemory("python fact"), FakeMemory("unrelated")])
        inj = MemoryInjector(memory_store=store)
        result = inj.inject_into_prompt("base", query="python")
        assert "python fact" in result

    def test_budget_zero(self):
        store = FakeStore([FakeMemory("a")])
        inj = MemoryInjector(memory_store=store)
        result = inj.compose(budget=0)
        # Everything gets dropped because budget is 0
        assert result.facts_included == 0

    def test_none_content_in_memory(self):
        m = MagicMock()
        m.content = None
        store = FakeStore([m])
        inj = MemoryInjector(memory_store=store)
        result = inj.compose()
        assert result.facts_included == 0

    def test_inject_into_prompt_budget_respected(self):
        facts = [FakeMemory(f"fact {i} with padding text") for i in range(50)]
        store = FakeStore(facts)
        inj = MemoryInjector(memory_store=store)
        result = inj.inject_into_prompt("base", budget=30)
        assert "base" in result
