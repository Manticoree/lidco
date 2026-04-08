"""Tests for lidco.configmgmt.template — Config Template Engine."""

from __future__ import annotations

import os
import unittest
from unittest import mock

from lidco.configmgmt.template import (
    ConfigTemplateEngine,
    RenderResult,
    TemplateValidationError,
    TemplateVariable,
)


class TestConfigTemplateEngine(unittest.TestCase):
    """Tests for ConfigTemplateEngine."""

    def setUp(self) -> None:
        self.engine = ConfigTemplateEngine()

    # -- Template registration ---------------------------------------------

    def test_register_and_list(self) -> None:
        self.engine.register_template("app", "host={{HOST}}")
        self.assertEqual(self.engine.list_templates(), ["app"])

    def test_register_empty_name_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.engine.register_template("", "content")

    def test_get_template(self) -> None:
        self.engine.register_template("db", "port={{PORT}}")
        self.assertEqual(self.engine.get_template("db"), "port={{PORT}}")

    def test_get_template_not_found(self) -> None:
        with self.assertRaises(KeyError):
            self.engine.get_template("missing")

    def test_remove_template(self) -> None:
        self.engine.register_template("tmp", "x")
        self.engine.remove_template("tmp")
        self.assertEqual(self.engine.list_templates(), [])

    def test_remove_nonexistent_no_error(self) -> None:
        self.engine.remove_template("nope")  # should not raise

    # -- Environment management --------------------------------------------

    def test_register_and_list_environments(self) -> None:
        self.engine.register_environment("prod", {"HOST": "prod.example.com"})
        self.assertEqual(self.engine.list_environments(), ["prod"])

    def test_get_environment(self) -> None:
        self.engine.register_environment("dev", {"HOST": "localhost"})
        self.assertEqual(self.engine.get_environment("dev"), {"HOST": "localhost"})

    def test_get_environment_not_found(self) -> None:
        with self.assertRaises(KeyError):
            self.engine.get_environment("missing")

    def test_get_environment_returns_copy(self) -> None:
        self.engine.register_environment("dev", {"HOST": "localhost"})
        env = self.engine.get_environment("dev")
        env["HOST"] = "changed"
        self.assertEqual(self.engine.get_environment("dev")["HOST"], "localhost")

    # -- Variable extraction -----------------------------------------------

    def test_extract_variables_basic(self) -> None:
        self.engine.register_template("t", "{{HOST}}:{{PORT}}")
        variables = self.engine.extract_variables("t")
        names = [v.name for v in variables]
        self.assertIn("HOST", names)
        self.assertIn("PORT", names)

    def test_extract_variables_with_default(self) -> None:
        self.engine.register_template("t", "{{HOST|localhost}}")
        variables = self.engine.extract_variables("t")
        self.assertEqual(len(variables), 1)
        self.assertEqual(variables[0].name, "HOST")
        self.assertEqual(variables[0].default, "localhost")
        self.assertFalse(variables[0].required)

    def test_extract_variables_deduplication(self) -> None:
        self.engine.register_template("t", "{{A}} and {{A}}")
        self.assertEqual(len(self.engine.extract_variables("t")), 1)

    # -- Rendering ---------------------------------------------------------

    def test_render_basic(self) -> None:
        self.engine.register_template("t", "host={{HOST}}")
        self.engine.register_environment("dev", {"HOST": "localhost"})
        result = self.engine.render("t", environment="dev")
        self.assertEqual(result.content, "host=localhost")
        self.assertIn("HOST", result.variables_used)

    def test_render_with_default(self) -> None:
        self.engine.register_template("t", "port={{ PORT | 5432 }}")
        result = self.engine.render("t")
        self.assertEqual(result.content, "port=5432")

    def test_render_with_overrides(self) -> None:
        self.engine.register_template("t", "{{HOST}}")
        self.engine.register_environment("dev", {"HOST": "dev.local"})
        result = self.engine.render("t", environment="dev", overrides={"HOST": "override.local"})
        self.assertEqual(result.content, "override.local")

    def test_render_missing_strict_raises(self) -> None:
        self.engine.register_template("t", "{{REQUIRED_VAR}}")
        with self.assertRaises(TemplateValidationError):
            self.engine.render("t", strict=True)

    def test_render_missing_not_strict_warns(self) -> None:
        self.engine.register_template("t", "{{MISSING}}")
        result = self.engine.render("t", strict=False)
        self.assertIn("{{MISSING}}", result.content)
        self.assertTrue(len(result.warnings) > 0)

    def test_render_secrets_provider(self) -> None:
        self.engine.register_template("t", "key={{API_KEY}}")
        self.engine.set_secrets_provider(lambda k: "secret123" if k == "API_KEY" else None)
        result = self.engine.render("t")
        self.assertEqual(result.content, "key=secret123")
        self.assertIn("API_KEY", result.secrets_injected)

    def test_render_env_var_fallback(self) -> None:
        self.engine.register_template("t", "val={{MY_ENV_VAR}}")
        with mock.patch.dict(os.environ, {"MY_ENV_VAR": "from_env"}):
            result = self.engine.render("t")
        self.assertEqual(result.content, "val=from_env")

    def test_render_priority_override_over_secret(self) -> None:
        self.engine.register_template("t", "{{VAR}}")
        self.engine.set_secrets_provider(lambda k: "secret")
        result = self.engine.render("t", overrides={"VAR": "override"})
        self.assertEqual(result.content, "override")
        self.assertNotIn("VAR", result.secrets_injected)

    # -- Validation --------------------------------------------------------

    def test_validate_template_ok(self) -> None:
        self.engine.register_template("t", "{{HOST}}")
        self.engine.register_environment("dev", {"HOST": "localhost"})
        issues = self.engine.validate_template("t", environment="dev")
        self.assertEqual(issues, [])

    def test_validate_template_missing_var(self) -> None:
        self.engine.register_template("t", "{{HOST}}")
        issues = self.engine.validate_template("t", environment="dev")
        self.assertTrue(len(issues) > 0)

    # -- JSON rendering ----------------------------------------------------

    def test_render_json(self) -> None:
        self.engine.register_template("j", '{"host": "{{HOST}}"}')
        self.engine.register_environment("dev", {"HOST": "localhost"})
        data = self.engine.render_json("j", environment="dev")
        self.assertEqual(data, {"host": "localhost"})

    def test_render_json_invalid(self) -> None:
        self.engine.register_template("j", "not json {{X}}")
        self.engine.register_environment("dev", {"X": "1"})
        with self.assertRaises(TemplateValidationError):
            self.engine.render_json("j", environment="dev")


if __name__ == "__main__":
    unittest.main()
