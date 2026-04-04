"""Tests for PRReviewerMatcher (Q300)."""
import unittest

from lidco.pr.reviewer import PRReviewerMatcher, Reviewer


class TestPRReviewerMatcher(unittest.TestCase):

    def test_suggest_no_owners(self):
        m = PRReviewerMatcher()
        result = m.suggest(["src/foo.py"])
        self.assertEqual(result, [])

    def test_add_owner_and_suggest(self):
        m = PRReviewerMatcher()
        m.add_owner("src/*.py", "alice")
        result = m.suggest(["src/foo.py"])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].user, "alice")

    def test_add_codeowner_and_suggest(self):
        m = PRReviewerMatcher()
        m.add_codeowner("docs/*", "docs-team")
        result = m.suggest(["docs/readme.md"])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].user, "docs-team")
        self.assertAlmostEqual(result[0].score, 0.8)

    def test_suggest_deduplicates(self):
        m = PRReviewerMatcher()
        m.add_owner("src/*.py", "alice")
        result = m.suggest(["src/a.py", "src/b.py"])
        users = [r.user for r in result]
        self.assertEqual(users.count("alice"), 1)

    def test_match_expertise(self):
        m = PRReviewerMatcher()
        m.add_owner("*.ts", "bob")
        result = m.match_expertise("app.ts")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].user, "bob")

    def test_match_expertise_no_match(self):
        m = PRReviewerMatcher()
        m.add_owner("*.ts", "bob")
        result = m.match_expertise("app.py")
        self.assertEqual(result, [])

    def test_record_and_recent_activity(self):
        m = PRReviewerMatcher()
        self.assertEqual(m.recent_activity("carol"), 0)
        m.record_activity("carol")
        m.record_activity("carol")
        self.assertEqual(m.recent_activity("carol"), 2)

    def test_recent_activity_unknown_user(self):
        m = PRReviewerMatcher()
        self.assertEqual(m.recent_activity("unknown"), 0)

    def test_owner_and_codeowner_both_match(self):
        m = PRReviewerMatcher()
        m.add_owner("src/*.py", "alice")
        m.add_codeowner("src/*", "backend-team")
        result = m.suggest(["src/foo.py"])
        users = {r.user for r in result}
        self.assertIn("alice", users)
        self.assertIn("backend-team", users)

    def test_reviewer_dataclass(self):
        r = Reviewer(user="x", reason="test", score=0.5)
        self.assertEqual(r.user, "x")
        self.assertEqual(r.score, 0.5)


if __name__ == "__main__":
    unittest.main()
