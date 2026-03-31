"""Tests for lidco.embeddings.auto_context."""

from __future__ import annotations

import time
import unittest

from lidco.embeddings.auto_context import (
    AutoContextInjector,
    ContextSnippet,
    InjectionConfig,
)
from lidco.embeddings.generator import EmbeddingGenerator
from lidco.embeddings.retriever import HybridRetriever
from lidco.embeddings.vector_store import VectorEntry, VectorStore


class TestInjectionConfig(unittest.TestCase):
    def test_default_config(self) -> None:
        cfg = InjectionConfig()
        self.assertTrue(cfg.enabled)
        self.assertEqual(cfg.max_snippets, 5)
        self.assertEqual(cfg.max_tokens, 2000)
        self.assertAlmostEqual(cfg.min_relevance, 0.1)

    def test_custom_config(self) -> None:
        cfg = InjectionConfig(enabled=False, max_snippets=3, max_tokens=1000, min_relevance=0.5)
        self.assertFalse(cfg.enabled)
        self.assertEqual(cfg.max_snippets, 3)


class TestAutoContextInjector(unittest.TestCase):
    def _build_injector(
        self, config: InjectionConfig | None = None
    ) -> tuple[AutoContextInjector, VectorStore]:
        gen = EmbeddingGenerator()
        store = VectorStore()

        texts = [
            "def calculate_sum(a, b): return a + b",
            "class UserManager: def create_user(self): pass",
            "def parse_config(path): return yaml.load(path)",
        ]
        gen.build_vocabulary(texts)

        entries: list[VectorEntry] = []
        for i, text in enumerate(texts):
            emb = gen.generate_embedding(text)
            e = VectorEntry(
                id=f"e{i}",
                file_path=f"mod{i}.py",
                start_line=1,
                end_line=5,
                content=text,
                chunk_type="function",
                name=f"item{i}",
                embedding=emb,
                updated_at=time.time(),
            )
            entries.append(e)
            store.upsert(e)

        retriever = HybridRetriever(store, gen)
        retriever.build_keyword_index(entries)
        injector = AutoContextInjector(retriever, config)
        return injector, store

    def test_get_context_returns_snippets(self) -> None:
        cfg = InjectionConfig(min_relevance=0.001)
        injector, store = self._build_injector(config=cfg)
        snippets = injector.get_context("calculate sum numbers")
        self.assertIsInstance(snippets, list)
        # Should find at least one relevant snippet
        self.assertGreater(len(snippets), 0)
        self.assertIsInstance(snippets[0], ContextSnippet)
        store.close()

    def test_get_context_skips_when_explicit_files(self) -> None:
        injector, store = self._build_injector()
        snippets = injector.get_context("calculate sum", explicit_files=["foo.py"])
        self.assertEqual(snippets, [])
        store.close()

    def test_get_context_filters_low_relevance(self) -> None:
        cfg = InjectionConfig(min_relevance=999.0)  # impossibly high
        injector, store = self._build_injector(config=cfg)
        snippets = injector.get_context("calculate sum")
        self.assertEqual(snippets, [])
        store.close()

    def test_get_context_respects_max_snippets(self) -> None:
        cfg = InjectionConfig(max_snippets=1, min_relevance=0.0)
        injector, store = self._build_injector(config=cfg)
        snippets = injector.get_context("calculate user config")
        self.assertLessEqual(len(snippets), 1)
        store.close()

    def test_get_context_respects_max_tokens(self) -> None:
        cfg = InjectionConfig(max_tokens=5, min_relevance=0.0)
        injector, store = self._build_injector(config=cfg)
        snippets = injector.get_context("calculate sum")
        # With max_tokens=5 (20 chars), most snippets won't fit
        total_tokens = sum(injector.estimate_tokens(s.content) for s in snippets)
        self.assertLessEqual(total_tokens, 5)
        store.close()

    def test_format_context_markdown(self) -> None:
        injector, store = self._build_injector()
        snippet = ContextSnippet(
            file_path="test.py",
            start_line=1,
            end_line=5,
            content="def foo(): pass",
            relevance_score=0.85,
            reason="test",
        )
        output = injector.format_context([snippet])
        self.assertIn("## Relevant Code Context", output)
        self.assertIn("test.py:1-5", output)
        self.assertIn("0.85", output)
        self.assertIn("def foo(): pass", output)
        store.close()

    def test_format_context_empty(self) -> None:
        injector, store = self._build_injector()
        output = injector.format_context([])
        self.assertEqual(output, "")
        store.close()

    def test_estimate_tokens(self) -> None:
        injector, store = self._build_injector()
        self.assertEqual(injector.estimate_tokens("abcd"), 1)
        self.assertEqual(injector.estimate_tokens("a" * 100), 25)
        self.assertEqual(injector.estimate_tokens(""), 0)
        store.close()

    def test_disabled_returns_empty(self) -> None:
        cfg = InjectionConfig(enabled=False)
        injector, store = self._build_injector(config=cfg)
        snippets = injector.get_context("calculate sum")
        self.assertEqual(snippets, [])
        store.close()


if __name__ == "__main__":
    unittest.main()
