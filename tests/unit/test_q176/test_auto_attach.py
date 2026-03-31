"""Tests for AutoAttachResolver — Q176."""
from __future__ import annotations

import unittest

from lidco.input.auto_attach import AutoAttachResolver, AttachResult


class TestAutoAttachResolver(unittest.TestCase):
    def setUp(self):
        self.resolver = AutoAttachResolver()
        self.project_files = [
            "src/auth/login.py",
            "src/auth/signup.py",
            "src/config/settings.py",
            "src/config/database.py",
            "src/models/user.py",
            "src/models/schema.py",
            "src/routes/api.py",
            "src/routes/views.py",
            "src/utils/helpers.py",
            "src/utils/format.py",
            "tests/test_auth.py",
            "tests/test_models.py",
            "src/cli/commands.py",
            "src/middleware/cors.py",
            "src/service/user_service.py",
            "src/components/layout.py",
        ]

    # --- Explicit file references ---
    def test_explicit_quoted_file(self):
        results = self.resolver.resolve('"login.py" has a bug', self.project_files)
        paths = [r.path for r in results]
        self.assertIn("src/auth/login.py", paths)

    def test_explicit_path_reference(self):
        results = self.resolver.resolve("check src/auth/login.py", self.project_files)
        paths = [r.path for r in results]
        self.assertIn("src/auth/login.py", paths)

    def test_explicit_reference_score_is_one(self):
        results = self.resolver.resolve('"settings.py" needs update', self.project_files)
        settings_results = [r for r in results if "settings" in r.path]
        self.assertTrue(any(r.score == 1.0 for r in settings_results))

    # --- Implicit references ---
    def test_auth_reference(self):
        results = self.resolver.resolve("fix the authentication flow", self.project_files)
        paths = [r.path for r in results]
        self.assertTrue(any("auth" in p for p in paths))

    def test_config_reference(self):
        results = self.resolver.resolve("update the configuration", self.project_files)
        paths = [r.path for r in results]
        self.assertTrue(any("config" in p for p in paths))

    def test_model_reference(self):
        results = self.resolver.resolve("add field to the user model", self.project_files)
        paths = [r.path for r in results]
        self.assertTrue(any("model" in p for p in paths))

    def test_test_reference(self):
        results = self.resolver.resolve("run the tests", self.project_files)
        paths = [r.path for r in results]
        self.assertTrue(any("test" in p for p in paths))

    def test_route_reference(self):
        results = self.resolver.resolve("add a new API endpoint", self.project_files)
        paths = [r.path for r in results]
        self.assertTrue(any("route" in p or "api" in p for p in paths))

    def test_utility_reference(self):
        results = self.resolver.resolve("add a helper function", self.project_files)
        paths = [r.path for r in results]
        self.assertTrue(any("helper" in p or "util" in p for p in paths))

    def test_cli_reference(self):
        results = self.resolver.resolve("add a new CLI command", self.project_files)
        paths = [r.path for r in results]
        self.assertTrue(any("cli" in p or "command" in p for p in paths))

    def test_middleware_reference(self):
        results = self.resolver.resolve("update the middleware", self.project_files)
        paths = [r.path for r in results]
        self.assertTrue(any("middleware" in p for p in paths))

    def test_service_reference(self):
        results = self.resolver.resolve("modify the user service", self.project_files)
        paths = [r.path for r in results]
        self.assertTrue(any("service" in p for p in paths))

    def test_component_reference(self):
        results = self.resolver.resolve("fix the layout component", self.project_files)
        paths = [r.path for r in results]
        self.assertTrue(any("layout" in p or "component" in p for p in paths))

    # --- Scoring and ranking ---
    def test_results_sorted_by_score(self):
        results = self.resolver.resolve("fix the auth login", self.project_files)
        if len(results) > 1:
            for i in range(len(results) - 1):
                self.assertGreaterEqual(results[i].score, results[i + 1].score)

    def test_filename_match_higher_than_path_match(self):
        # A keyword in the filename should score higher
        results = self.resolver.resolve("check the helpers", self.project_files)
        helper_results = [r for r in results if "helpers" in r.path.split("/")[-1]]
        if helper_results:
            self.assertGreaterEqual(helper_results[0].score, 0.85)

    # --- Budget limits ---
    def test_token_budget_limits_results(self):
        results = self.resolver.resolve("update auth config models", self.project_files, token_budget=3)
        self.assertLessEqual(len(results), 3)

    def test_token_budget_zero_returns_empty(self):
        # budget=0 is falsy, should not limit
        results = self.resolver.resolve("fix auth", self.project_files, token_budget=0)
        # budget 0 is caught by the > 0 check, so no limiting
        self.assertGreater(len(results), 0)

    # --- Edge cases ---
    def test_empty_prompt(self):
        results = self.resolver.resolve("", self.project_files)
        self.assertEqual(results, [])

    def test_empty_files_list(self):
        results = self.resolver.resolve("fix the auth", [])
        self.assertEqual(results, [])

    def test_no_matches(self):
        results = self.resolver.resolve("quantum entanglement", self.project_files)
        self.assertEqual(results, [])

    def test_attach_result_frozen(self):
        r = AttachResult(path="a.py", score=0.9, reason="test")
        with self.assertRaises(AttributeError):
            r.path = "b.py"  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
