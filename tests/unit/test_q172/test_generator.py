"""Tests for lidco.embeddings.generator."""

from __future__ import annotations

import math
import unittest

from lidco.embeddings.generator import (
    ChunkingConfig,
    CodeChunk,
    EmbeddingGenerator,
)


class TestChunkingConfig(unittest.TestCase):
    def test_default_config(self) -> None:
        cfg = ChunkingConfig()
        self.assertEqual(cfg.chunk_size, 500)
        self.assertEqual(cfg.chunk_overlap, 50)
        self.assertTrue(cfg.respect_boundaries)

    def test_custom_config(self) -> None:
        cfg = ChunkingConfig(chunk_size=200, chunk_overlap=20, respect_boundaries=False)
        self.assertEqual(cfg.chunk_size, 200)
        self.assertEqual(cfg.chunk_overlap, 20)
        self.assertFalse(cfg.respect_boundaries)


class TestChunkFileByFunctions(unittest.TestCase):
    def test_chunk_file_by_functions(self) -> None:
        content = (
            "def foo():\n"
            "    return 1\n"
            "\n"
            "def bar():\n"
            "    return 2\n"
        )
        gen = EmbeddingGenerator()
        chunks = gen.chunk_file("test.py", content)
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0].chunk_type, "function")
        self.assertEqual(chunks[0].name, "foo")
        self.assertEqual(chunks[1].chunk_type, "function")
        self.assertEqual(chunks[1].name, "bar")

    def test_chunk_file_by_classes(self) -> None:
        content = (
            "class Foo:\n"
            "    pass\n"
            "\n"
            "class Bar:\n"
            "    pass\n"
        )
        gen = EmbeddingGenerator()
        chunks = gen.chunk_file("test.py", content)
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0].chunk_type, "class")
        self.assertEqual(chunks[0].name, "Foo")
        self.assertEqual(chunks[1].chunk_type, "class")
        self.assertEqual(chunks[1].name, "Bar")


class TestChunkFileNoBoundaries(unittest.TestCase):
    def test_chunk_file_no_boundaries(self) -> None:
        content = "x = 1\ny = 2\nz = 3\n" * 50
        gen = EmbeddingGenerator(config=ChunkingConfig(chunk_size=100, chunk_overlap=10))
        chunks = gen.chunk_file("test.py", content)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertEqual(chunk.chunk_type, "block")
            self.assertIsNone(chunk.name)

    def test_chunk_file_empty_content(self) -> None:
        gen = EmbeddingGenerator()
        chunks = gen.chunk_file("test.py", "")
        self.assertEqual(chunks, [])


class TestChunkOverlap(unittest.TestCase):
    def test_chunk_overlap(self) -> None:
        content = "a" * 1000
        gen = EmbeddingGenerator(
            config=ChunkingConfig(chunk_size=200, chunk_overlap=50, respect_boundaries=False)
        )
        chunks = gen.chunk_file("test.py", content)
        # With size=200, overlap=50, step=150, should get ceil(1000/150)=7 chunks
        self.assertGreater(len(chunks), 1)
        # Check overlap: second chunk starts 150 chars in
        if len(chunks) >= 2:
            self.assertIn(content[150:200], chunks[1].content)


class TestTokenize(unittest.TestCase):
    def test_tokenize_basic(self) -> None:
        gen = EmbeddingGenerator()
        tokens = gen._tokenize("hello world foo_bar")
        self.assertIn("hello", tokens)
        self.assertIn("world", tokens)
        self.assertIn("foo_bar", tokens)

    def test_tokenize_stopwords_removed(self) -> None:
        gen = EmbeddingGenerator()
        tokens = gen._tokenize("the quick and lazy fox is not here")
        self.assertNotIn("the", tokens)
        self.assertNotIn("and", tokens)
        self.assertNotIn("is", tokens)
        self.assertNotIn("not", tokens)
        self.assertIn("quick", tokens)
        self.assertIn("lazy", tokens)
        self.assertIn("fox", tokens)


class TestBuildVocabulary(unittest.TestCase):
    def test_build_vocabulary(self) -> None:
        gen = EmbeddingGenerator()
        gen.build_vocabulary(["hello world", "world test", "hello test"])
        self.assertIn("hello", gen._vocab)
        self.assertIn("world", gen._vocab)
        self.assertIn("test", gen._vocab)
        self.assertEqual(gen._doc_count, 3)

    def test_max_vocab_size(self) -> None:
        gen = EmbeddingGenerator()
        texts = [" ".join(f"word{i}" for i in range(12000))]
        gen.build_vocabulary(texts)
        self.assertLessEqual(len(gen._vocab), 10000)


class TestGenerateEmbedding(unittest.TestCase):
    def test_generate_embedding_returns_list_of_floats(self) -> None:
        gen = EmbeddingGenerator()
        gen.build_vocabulary(["hello world function"])
        emb = gen.generate_embedding("hello world")
        self.assertIsInstance(emb, list)
        self.assertTrue(all(isinstance(v, float) for v in emb))

    def test_generate_embedding_dimension_matches_vocab(self) -> None:
        gen = EmbeddingGenerator()
        gen.build_vocabulary(["alpha beta gamma delta"])
        emb = gen.generate_embedding("alpha beta")
        self.assertEqual(len(emb), len(gen._vocab))

    def test_embedding_normalized(self) -> None:
        gen = EmbeddingGenerator()
        gen.build_vocabulary(["function hello world test code"])
        emb = gen.generate_embedding("function hello code")
        norm = math.sqrt(sum(v * v for v in emb))
        self.assertAlmostEqual(norm, 1.0, places=5)


class TestEmbedChunks(unittest.TestCase):
    def test_embed_chunks_returns_pairs(self) -> None:
        gen = EmbeddingGenerator()
        chunks = [
            CodeChunk("a.py", 1, 5, "def foo(): pass", "function", "foo"),
            CodeChunk("a.py", 6, 10, "def bar(): pass", "function", "bar"),
        ]
        gen.build_vocabulary([c.content for c in chunks])
        pairs = gen.embed_chunks(chunks)
        self.assertEqual(len(pairs), 2)
        for chunk, emb in pairs:
            self.assertIsInstance(chunk, CodeChunk)
            self.assertIsInstance(emb, list)


class TestChunkTypesAndNames(unittest.TestCase):
    def test_chunk_types_correct(self) -> None:
        content = "def foo():\n    pass\n\nclass Bar:\n    pass\n"
        gen = EmbeddingGenerator()
        chunks = gen.chunk_file("test.py", content)
        types = {c.chunk_type for c in chunks}
        self.assertIn("function", types)
        self.assertIn("class", types)

    def test_chunk_names_extracted(self) -> None:
        content = "def my_func():\n    pass\n\nclass MyClass:\n    pass\n"
        gen = EmbeddingGenerator()
        chunks = gen.chunk_file("test.py", content)
        names = {c.name for c in chunks}
        self.assertIn("my_func", names)
        self.assertIn("MyClass", names)


if __name__ == "__main__":
    unittest.main()
