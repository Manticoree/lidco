"""Tests for src/lidco/doctor/api_validator.py."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from lidco.doctor.api_validator import ApiKeyResult, ApiValidator, KeyStatus


class TestCheckEnvKey(unittest.TestCase):
    def test_missing_key(self):
        with patch.dict("os.environ", {}, clear=True):
            result = ApiValidator().check_env_key("ANTHROPIC_API_KEY", "anthropic")
        self.assertEqual(result.status, KeyStatus.MISSING)
        self.assertIn("not set", result.message)

    def test_valid_anthropic(self):
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-ant-abc123456789"}, clear=True):
            result = ApiValidator().check_env_key("ANTHROPIC_API_KEY", "anthropic")
        self.assertEqual(result.status, KeyStatus.VALID)
        self.assertEqual(result.key_prefix, "sk-ant-a...")

    def test_invalid_anthropic_format(self):
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "bad-key"}, clear=True):
            result = ApiValidator().check_env_key("ANTHROPIC_API_KEY", "anthropic")
        self.assertEqual(result.status, KeyStatus.INVALID)

    def test_valid_openai(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-proj-abcdefghij"}, clear=True):
            result = ApiValidator().check_env_key("OPENAI_API_KEY", "openai")
        self.assertEqual(result.status, KeyStatus.VALID)

    def test_unknown_provider_no_pattern(self):
        with patch.dict("os.environ", {"MY_KEY": "anything"}, clear=True):
            result = ApiValidator().check_env_key("MY_KEY", "custom")
        self.assertEqual(result.status, KeyStatus.VALID)


class TestValidateProviders(unittest.TestCase):
    def test_validate_anthropic(self):
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-ant-xyz12345"}, clear=True):
            result = ApiValidator().validate_anthropic()
        self.assertEqual(result.provider, "anthropic")
        self.assertEqual(result.status, KeyStatus.VALID)

    def test_validate_openai(self):
        with patch.dict("os.environ", {}, clear=True):
            result = ApiValidator().validate_openai()
        self.assertEqual(result.status, KeyStatus.MISSING)


class TestValidateAll(unittest.TestCase):
    def test_all_missing(self):
        with patch.dict("os.environ", {}, clear=True):
            results = ApiValidator().validate_all()
        self.assertEqual(len(results), 3)
        self.assertTrue(all(r.status == KeyStatus.MISSING for r in results))

    def test_has_any_key_false(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertFalse(ApiValidator().has_any_key())

    def test_has_any_key_true(self):
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-ant-test1234"}, clear=True):
            self.assertTrue(ApiValidator().has_any_key())


class TestSummary(unittest.TestCase):
    def test_summary_format(self):
        results = [
            ApiKeyResult("anthropic", KeyStatus.VALID, message="ok"),
            ApiKeyResult("openai", KeyStatus.MISSING, message="not set"),
        ]
        s = ApiValidator().summary(results)
        self.assertIn("[VALID]", s)
        self.assertIn("[MISSING]", s)
        self.assertIn("anthropic", s)
