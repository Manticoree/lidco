"""Tests for RecipeStore (Task 1804)."""
from __future__ import annotations

import unittest

from lidco.community.recipes import Recipe, RecipeStep, RecipeStore


def _recipe(name: str = "auto-lint", **kw) -> Recipe:
    defaults = dict(
        author="alice", description="Auto lint recipe", version="1.0.0",
        steps=[RecipeStep(name="lint", action="run", params={"cmd": "lint"})],
    )
    defaults.update(kw)
    return Recipe(name=name, **defaults)


class TestRecipeStep(unittest.TestCase):
    def test_to_dict(self):
        s = RecipeStep(name="build", action="exec", params={"timeout": 30})
        d = s.to_dict()
        self.assertEqual(d["name"], "build")
        self.assertEqual(d["params"]["timeout"], 30)


class TestRecipe(unittest.TestCase):
    def test_defaults(self):
        r = _recipe()
        self.assertEqual(r.name, "auto-lint")
        self.assertEqual(r.step_count, 1)
        self.assertFalse(r.is_fork)
        self.assertEqual(r.average_rating, 0.0)

    def test_recipe_id_deterministic(self):
        r1 = _recipe()
        r2 = _recipe()
        self.assertEqual(r1.recipe_id, r2.recipe_id)

    def test_recipe_id_differs_by_version(self):
        r1 = _recipe(version="1.0.0")
        r2 = _recipe(version="2.0.0")
        self.assertNotEqual(r1.recipe_id, r2.recipe_id)

    def test_rate(self):
        r = _recipe()
        r2 = r.rate(4)
        self.assertEqual(r.rating_count, 0)
        self.assertEqual(r2.rating_count, 1)
        self.assertAlmostEqual(r2.average_rating, 4.0)

    def test_rate_invalid(self):
        r = _recipe()
        with self.assertRaises(ValueError):
            r.rate(0)

    def test_fork(self):
        r = _recipe()
        f = r.fork("bob")
        self.assertEqual(f.author, "bob")
        self.assertEqual(f.parent_id, r.recipe_id)
        self.assertTrue(f.is_fork)
        self.assertEqual(f.name, "auto-lint-fork")

    def test_fork_custom_name(self):
        r = _recipe()
        f = r.fork("bob", "my-lint")
        self.assertEqual(f.name, "my-lint")

    def test_bump_version(self):
        r = _recipe(version="1.0.0")
        r2 = r.bump_version("2.0.0")
        self.assertEqual(r.version, "1.0.0")
        self.assertEqual(r2.version, "2.0.0")

    def test_increment_downloads(self):
        r = _recipe()
        r2 = r.increment_downloads()
        self.assertEqual(r.downloads, 0)
        self.assertEqual(r2.downloads, 1)

    def test_to_dict(self):
        r = _recipe(tags=["ci"])
        d = r.to_dict()
        self.assertEqual(d["name"], "auto-lint")
        self.assertEqual(d["tags"], ["ci"])
        self.assertIn("recipe_id", d)


class TestRecipeStore(unittest.TestCase):
    def setUp(self):
        self.store = RecipeStore()

    def test_empty(self):
        self.assertEqual(self.store.count, 0)

    def test_publish_and_get(self):
        r = _recipe()
        rid = self.store.publish(r)
        self.assertEqual(self.store.count, 1)
        got = self.store.get(rid)
        self.assertIsNotNone(got)
        self.assertEqual(got.name, "auto-lint")

    def test_publish_requires_name(self):
        with self.assertRaises(ValueError):
            self.store.publish(Recipe(name="", author="a"))

    def test_remove(self):
        rid = self.store.publish(_recipe())
        self.assertTrue(self.store.remove(rid))
        self.assertFalse(self.store.remove(rid))

    def test_search(self):
        self.store.publish(_recipe("linter", description="Lint code"))
        self.store.publish(_recipe("formatter", description="Format code"))
        results = self.store.search("lint")
        self.assertEqual(len(results), 1)

    def test_search_by_tag(self):
        self.store.publish(_recipe("x", tags=["ci"]))
        results = self.store.search("ci")
        self.assertEqual(len(results), 1)

    def test_browse(self):
        self.store.publish(_recipe("a"))
        self.store.publish(_recipe("b", version="2.0.0"))
        self.assertEqual(len(self.store.browse()), 2)

    def test_top_rated(self):
        rid = self.store.publish(_recipe("a"))
        self.store.rate(rid, 5)
        rid2 = self.store.publish(_recipe("b", version="2.0.0"))
        self.store.rate(rid2, 3)
        top = self.store.top_rated()
        self.assertEqual(top[0].name, "a")

    def test_by_author(self):
        self.store.publish(_recipe("a", author="alice"))
        self.store.publish(_recipe("b", author="bob", version="2.0.0"))
        results = self.store.by_author("alice")
        self.assertEqual(len(results), 1)

    def test_rate_not_found(self):
        self.assertFalse(self.store.rate("nope", 3))

    def test_record_download(self):
        rid = self.store.publish(_recipe())
        self.assertTrue(self.store.record_download(rid))
        self.assertEqual(self.store.get(rid).downloads, 1)

    def test_record_download_not_found(self):
        self.assertFalse(self.store.record_download("nope"))

    def test_fork_recipe(self):
        rid = self.store.publish(_recipe())
        fid = self.store.fork_recipe(rid, "bob")
        self.assertIsNotNone(fid)
        forked = self.store.get(fid)
        self.assertEqual(forked.author, "bob")
        self.assertTrue(forked.is_fork)

    def test_fork_recipe_not_found(self):
        self.assertIsNone(self.store.fork_recipe("nope", "bob"))

    def test_forks_of(self):
        rid = self.store.publish(_recipe())
        self.store.fork_recipe(rid, "bob")
        forks = self.store.forks_of(rid)
        # forks_of checks parent_id == recipe_id of original
        # The recipe_id of the original is the MD5 hash
        original = self.store.get(rid)
        forks = self.store.forks_of(original.recipe_id)
        self.assertEqual(len(forks), 1)

    def test_stats(self):
        self.store.publish(_recipe("a", author="alice"))
        self.store.publish(_recipe("b", author="bob", version="2.0.0"))
        st = self.store.stats()
        self.assertEqual(st["total_recipes"], 2)
        self.assertEqual(st["unique_authors"], 2)


if __name__ == "__main__":
    unittest.main()
