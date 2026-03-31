"""Tests for FallbackChain."""
from __future__ import annotations

import asyncio
import unittest

from lidco.resilience.fallback_chain import FallbackChain, FallbackResult


def _run(coro):
    return asyncio.run(coro)


class TestFallbackResult(unittest.TestCase):
    def test_defaults(self):
        r = FallbackResult(value=1, source="a")
        self.assertEqual(r.value, 1)
        self.assertEqual(r.source, "a")
        self.assertEqual(r.attempts, [])
        self.assertFalse(r.fallback_used)


class TestFallbackChain(unittest.TestCase):
    def test_single_success(self):
        chain = FallbackChain()
        chain.add("primary", lambda: 42)
        result = chain.execute()
        self.assertEqual(result.value, 42)
        self.assertEqual(result.source, "primary")
        self.assertFalse(result.fallback_used)

    def test_first_fails_second_succeeds(self):
        chain = FallbackChain()
        chain.add("fail", lambda: (_ for _ in ()).throw(RuntimeError("nope")))
        chain.add("ok", lambda: "fallback")
        result = chain.execute()
        self.assertEqual(result.value, "fallback")
        self.assertEqual(result.source, "ok")
        self.assertTrue(result.fallback_used)
        self.assertEqual(len(result.attempts), 1)

    def test_all_fail_raises(self):
        chain = FallbackChain()
        chain.add("a", lambda: (_ for _ in ()).throw(RuntimeError("a")))
        chain.add("b", lambda: (_ for _ in ()).throw(ValueError("b")))
        with self.assertRaises(ValueError):
            chain.execute()

    def test_empty_chain_raises(self):
        chain = FallbackChain()
        with self.assertRaises(RuntimeError):
            chain.execute()

    def test_attempts_recorded(self):
        chain = FallbackChain()
        chain.add("f1", lambda: (_ for _ in ()).throw(RuntimeError("e1")))
        chain.add("f2", lambda: (_ for _ in ()).throw(ValueError("e2")))
        chain.add("ok", lambda: "yes")
        result = chain.execute()
        self.assertEqual(len(result.attempts), 2)
        self.assertEqual(result.attempts[0]["name"], "f1")
        self.assertEqual(result.attempts[1]["name"], "f2")

    def test_remove(self):
        chain = FallbackChain()
        chain.add("a", lambda: 1)
        chain.add("b", lambda: 2)
        chain.remove("a")
        self.assertEqual(len(chain), 1)
        result = chain.execute()
        self.assertEqual(result.source, "b")

    def test_remove_nonexistent(self):
        chain = FallbackChain()
        chain.add("a", lambda: 1)
        chain.remove("zzz")
        self.assertEqual(len(chain), 1)

    def test_clear(self):
        chain = FallbackChain()
        chain.add("a", lambda: 1)
        chain.add("b", lambda: 2)
        chain.clear()
        self.assertEqual(len(chain), 0)

    def test_len(self):
        chain = FallbackChain()
        self.assertEqual(len(chain), 0)
        chain.add("a", lambda: 1)
        self.assertEqual(len(chain), 1)

    def test_kwargs_forwarded(self):
        chain = FallbackChain()
        chain.add("greet", lambda name="world": f"hi {name}")
        result = chain.execute(name="test")
        self.assertEqual(result.value, "hi test")

    def test_stored_kwargs_merged(self):
        chain = FallbackChain()
        chain.add("fn", lambda x=0: x * 2, x=5)
        result = chain.execute()
        self.assertEqual(result.value, 10)

    def test_args_forwarded(self):
        chain = FallbackChain()
        chain.add("add", lambda a, b: a + b)
        result = chain.execute(3, 4)
        self.assertEqual(result.value, 7)

    def test_attempt_error_type_recorded(self):
        chain = FallbackChain()
        chain.add("fail", lambda: (_ for _ in ()).throw(TypeError("t")))
        chain.add("ok", lambda: 1)
        result = chain.execute()
        self.assertEqual(result.attempts[0]["error_type"], "TypeError")

    # --- Async tests ---

    def test_async_single(self):
        chain = FallbackChain()

        async def ok():
            return 99

        chain.add("primary", ok)
        result = _run(chain.async_execute())
        self.assertEqual(result.value, 99)
        self.assertFalse(result.fallback_used)

    def test_async_fallback(self):
        chain = FallbackChain()

        async def fail():
            raise RuntimeError("no")

        async def ok():
            return "async-ok"

        chain.add("fail", fail)
        chain.add("ok", ok)
        result = _run(chain.async_execute())
        self.assertEqual(result.value, "async-ok")
        self.assertTrue(result.fallback_used)

    def test_async_all_fail(self):
        chain = FallbackChain()

        async def fail():
            raise ValueError("v")

        chain.add("f", fail)
        with self.assertRaises(ValueError):
            _run(chain.async_execute())

    def test_async_empty(self):
        chain = FallbackChain()
        with self.assertRaises(RuntimeError):
            _run(chain.async_execute())

    def test_async_attempts_tracked(self):
        chain = FallbackChain()

        async def fail():
            raise RuntimeError("x")

        async def ok():
            return 1

        chain.add("fail", fail)
        chain.add("ok", ok)
        result = _run(chain.async_execute())
        self.assertEqual(len(result.attempts), 1)

    def test_three_deep_fallback(self):
        chain = FallbackChain()
        chain.add("a", lambda: (_ for _ in ()).throw(RuntimeError("a")))
        chain.add("b", lambda: (_ for _ in ()).throw(RuntimeError("b")))
        chain.add("c", lambda: "third")
        result = chain.execute()
        self.assertEqual(result.source, "c")
        self.assertTrue(result.fallback_used)
        self.assertEqual(len(result.attempts), 2)


if __name__ == "__main__":
    unittest.main()
