"""Tests for lidco.github.client — GitHubClient."""
from __future__ import annotations

import unittest

from lidco.github.client import GitHubClient


class TestGitHubClient(unittest.TestCase):
    def setUp(self):
        self.client = GitHubClient(token="test-token")
        self.anon = GitHubClient()

    # -- authentication ---------------------------------------------------

    def test_authenticated_with_token(self):
        self.assertTrue(self.client.authenticated)

    def test_not_authenticated_without_token(self):
        self.assertFalse(self.anon.authenticated)

    # -- get_repo ---------------------------------------------------------

    def test_get_repo_returns_metadata(self):
        repo = self.client.get_repo("octocat", "hello-world")
        self.assertEqual(repo["full_name"], "octocat/hello-world")
        self.assertEqual(repo["owner"], "octocat")
        self.assertEqual(repo["name"], "hello-world")
        self.assertEqual(repo["default_branch"], "main")

    def test_get_repo_missing_owner_raises(self):
        with self.assertRaises(ValueError):
            self.client.get_repo("", "repo")

    def test_get_repo_missing_repo_raises(self):
        with self.assertRaises(ValueError):
            self.client.get_repo("owner", "")

    # -- list_repos -------------------------------------------------------

    def test_list_repos_returns_list(self):
        repos = self.client.list_repos("my-org")
        self.assertEqual(len(repos), 2)
        self.assertTrue(all("full_name" in r for r in repos))

    def test_list_repos_empty_org_raises(self):
        with self.assertRaises(ValueError):
            self.client.list_repos("")

    # -- get_user ---------------------------------------------------------

    def test_get_user_returns_dict(self):
        user = self.client.get_user()
        self.assertIn("login", user)
        self.assertIn("id", user)

    # -- rate_limit -------------------------------------------------------

    def test_rate_limit_returns_dict(self):
        info = self.client.rate_limit()
        self.assertIn("limit", info)
        self.assertIn("remaining", info)
        self.assertGreater(info["remaining"], 0)

    # -- paginate ---------------------------------------------------------

    def test_paginate_returns_pages(self):
        pages = self.client.paginate("https://api.github.com/repos")
        self.assertEqual(len(pages), 2)
        self.assertEqual(pages[0]["page"], 1)

    def test_paginate_empty_url_raises(self):
        with self.assertRaises(ValueError):
            self.client.paginate("")


if __name__ == "__main__":
    unittest.main()
