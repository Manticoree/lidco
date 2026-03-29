"""Tests for SessionTagStore (Task 700)."""
import unittest

from lidco.memory.session_tags import SessionTag, SessionTagStore


class TestSessionTag(unittest.TestCase):
    def test_creation(self):
        t = SessionTag(session_id="s1", tags=["a", "b"], attributes={"origin": "test"}, created_at="2025-01-01T00:00:00")
        self.assertEqual(t.session_id, "s1")
        self.assertEqual(t.tags, ["a", "b"])
        self.assertEqual(t.attributes["origin"], "test")


class TestTag(unittest.TestCase):
    def setUp(self):
        self.store = SessionTagStore()

    def test_tag_new_session(self):
        self.store.tag("s1", ["tag1", "tag2"])
        result = self.store.get("s1")
        self.assertIsNotNone(result)
        self.assertEqual(result.tags, ["tag1", "tag2"])

    def test_tag_with_attributes(self):
        self.store.tag("s1", ["tag1"], {"origin": "playbook", "agent": "bugbot"})
        result = self.store.get("s1")
        self.assertEqual(result.attributes["origin"], "playbook")
        self.assertEqual(result.attributes["agent"], "bugbot")

    def test_tag_idempotent(self):
        self.store.tag("s1", ["tag1"])
        self.store.tag("s1", ["tag1"])
        result = self.store.get("s1")
        self.assertEqual(result.tags, ["tag1"])

    def test_tag_merge_tags(self):
        self.store.tag("s1", ["tag1"])
        self.store.tag("s1", ["tag2"])
        result = self.store.get("s1")
        self.assertIn("tag1", result.tags)
        self.assertIn("tag2", result.tags)

    def test_tag_merge_attributes(self):
        self.store.tag("s1", ["tag1"], {"a": "1"})
        self.store.tag("s1", [], {"b": "2"})
        result = self.store.get("s1")
        self.assertEqual(result.attributes["a"], "1")
        self.assertEqual(result.attributes["b"], "2")

    def test_tag_no_attributes_default(self):
        self.store.tag("s1", ["t"])
        result = self.store.get("s1")
        self.assertEqual(result.attributes, {})

    def test_tag_empty_tags(self):
        self.store.tag("s1", [])
        result = self.store.get("s1")
        self.assertEqual(result.tags, [])

    def test_created_at_set(self):
        self.store.tag("s1", ["t"])
        result = self.store.get("s1")
        self.assertTrue(len(result.created_at) > 0)


class TestUntag(unittest.TestCase):
    def setUp(self):
        self.store = SessionTagStore()

    def test_untag_removes_tag(self):
        self.store.tag("s1", ["a", "b", "c"])
        self.store.untag("s1", "b")
        result = self.store.get("s1")
        self.assertEqual(result.tags, ["a", "c"])

    def test_untag_nonexistent_session(self):
        # Should not raise
        self.store.untag("nonexistent", "tag")

    def test_untag_nonexistent_tag(self):
        self.store.tag("s1", ["a"])
        self.store.untag("s1", "b")
        result = self.store.get("s1")
        self.assertEqual(result.tags, ["a"])


class TestGet(unittest.TestCase):
    def setUp(self):
        self.store = SessionTagStore()

    def test_get_nonexistent(self):
        result = self.store.get("nonexistent")
        self.assertIsNone(result)

    def test_get_existing(self):
        self.store.tag("s1", ["t"])
        result = self.store.get("s1")
        self.assertIsNotNone(result)
        self.assertEqual(result.session_id, "s1")


class TestSearch(unittest.TestCase):
    def setUp(self):
        self.store = SessionTagStore()
        self.store.tag("s1", ["bugbot", "review"])
        self.store.tag("s2", ["deploy", "CI"])
        self.store.tag("s3", ["bugbot-v2", "testing"])

    def test_search_finds_match(self):
        results = self.store.search("bugbot")
        ids = [r.session_id for r in results]
        self.assertIn("s1", ids)
        self.assertIn("s3", ids)
        self.assertNotIn("s2", ids)

    def test_search_case_insensitive(self):
        results = self.store.search("BUGBOT")
        self.assertTrue(len(results) >= 1)

    def test_search_no_match(self):
        results = self.store.search("nonexistent")
        self.assertEqual(results, [])

    def test_search_substring(self):
        results = self.store.search("bug")
        self.assertTrue(len(results) >= 2)

    def test_search_empty_query(self):
        # Empty string matches all tags (substring of everything)
        results = self.store.search("")
        self.assertTrue(len(results) >= 3)


class TestFilter(unittest.TestCase):
    def setUp(self):
        self.store = SessionTagStore()
        self.store.tag("s1", ["t"], {"origin": "playbook", "agent": "bugbot"})
        self.store.tag("s2", ["t"], {"origin": "manual", "agent": "review"})
        self.store.tag("s3", ["t"], {"origin": "playbook", "agent": "review"})

    def test_filter_by_origin(self):
        results = self.store.filter(origin="playbook")
        ids = [r.session_id for r in results]
        self.assertIn("s1", ids)
        self.assertIn("s3", ids)
        self.assertNotIn("s2", ids)

    def test_filter_by_agent(self):
        results = self.store.filter(agent="bugbot")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].session_id, "s1")

    def test_filter_by_both(self):
        results = self.store.filter(origin="playbook", agent="review")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].session_id, "s3")

    def test_filter_no_match(self):
        results = self.store.filter(origin="unknown")
        self.assertEqual(results, [])

    def test_filter_none_returns_all(self):
        results = self.store.filter()
        self.assertEqual(len(results), 3)

    def test_filter_by_after(self):
        # All have same-ish timestamps, filter with very old date
        results = self.store.filter(after="2000-01-01")
        self.assertEqual(len(results), 3)

    def test_filter_by_before(self):
        results = self.store.filter(before="2000-01-01")
        self.assertEqual(results, [])

    def test_filter_after_and_before(self):
        results = self.store.filter(after="2000-01-01", before="2099-12-31")
        self.assertEqual(len(results), 3)


class TestListAll(unittest.TestCase):
    def test_empty_store(self):
        store = SessionTagStore()
        self.assertEqual(store.list_all(), [])

    def test_list_all(self):
        store = SessionTagStore()
        store.tag("s1", ["a"])
        store.tag("s2", ["b"])
        result = store.list_all()
        self.assertEqual(len(result), 2)


class TestDelete(unittest.TestCase):
    def setUp(self):
        self.store = SessionTagStore()

    def test_delete_removes(self):
        self.store.tag("s1", ["t"])
        self.store.delete("s1")
        self.assertIsNone(self.store.get("s1"))

    def test_delete_nonexistent(self):
        # Should not raise
        self.store.delete("nonexistent")

    def test_delete_does_not_affect_others(self):
        self.store.tag("s1", ["t"])
        self.store.tag("s2", ["t"])
        self.store.delete("s1")
        self.assertIsNotNone(self.store.get("s2"))


if __name__ == "__main__":
    unittest.main()
