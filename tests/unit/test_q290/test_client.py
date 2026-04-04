"""Tests for GitLabClient (Q290)."""

import unittest

from lidco.gitlab.client import GitLabClient


class TestGitLabClientInit(unittest.TestCase):
    def test_default_init(self):
        c = GitLabClient()
        self.assertEqual(c.token, "")
        self.assertEqual(c.base_url, "https://gitlab.com")

    def test_custom_init(self):
        c = GitLabClient(token="tok", base_url="https://gl.local/")
        self.assertEqual(c.token, "tok")
        self.assertEqual(c.base_url, "https://gl.local")


class TestGetProject(unittest.TestCase):
    def test_get_existing_project(self):
        c = GitLabClient(token="t")
        p = c._add_project("repo1", "mygroup")
        result = c.get_project(p["id"])
        self.assertEqual(result["name"], "repo1")
        self.assertEqual(result["path_with_namespace"], "mygroup/repo1")

    def test_get_missing_project_raises(self):
        c = GitLabClient()
        with self.assertRaises(KeyError):
            c.get_project(999)

    def test_get_project_returns_copy(self):
        c = GitLabClient(token="t")
        p = c._add_project("repo2")
        result = c.get_project(p["id"])
        result["name"] = "hacked"
        self.assertEqual(c.get_project(p["id"])["name"], "repo2")


class TestListProjects(unittest.TestCase):
    def test_empty_list(self):
        c = GitLabClient()
        self.assertEqual(c.list_projects(), [])

    def test_list_all(self):
        c = GitLabClient(token="t")
        c._add_project("a", "g1")
        c._add_project("b", "g2")
        self.assertEqual(len(c.list_projects()), 2)

    def test_filter_by_group(self):
        c = GitLabClient(token="t")
        c._add_project("a", "alpha")
        c._add_project("b", "beta")
        result = c.list_projects(group="alpha")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "a")


class TestGetUser(unittest.TestCase):
    def test_authenticated_user(self):
        c = GitLabClient(token="secret")
        user = c.get_user()
        self.assertEqual(user["username"], "lidco-bot")
        self.assertEqual(user["state"], "active")

    def test_no_token_raises(self):
        c = GitLabClient()
        with self.assertRaises(PermissionError):
            c.get_user()


class TestPaginate(unittest.TestCase):
    def test_paginate_returns_projects(self):
        c = GitLabClient(token="t")
        c._add_project("x")
        result = c.paginate("/api/v4/projects")
        self.assertEqual(len(result), 1)

    def test_empty_url_raises(self):
        c = GitLabClient()
        with self.assertRaises(ValueError):
            c.paginate("")


if __name__ == "__main__":
    unittest.main()
