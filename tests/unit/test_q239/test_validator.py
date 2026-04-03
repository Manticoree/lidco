"""Tests for lidco.conversation.validator — MessageValidator."""
from __future__ import annotations

import unittest

from lidco.conversation.validator import (
    DEFAULT_MAX_CONTENT_LENGTH,
    VALID_ROLES,
    MessageValidator,
    ValidationResult,
)


class TestValidationResult(unittest.TestCase):
    def test_frozen_dataclass(self):
        r = ValidationResult(is_valid=True)
        self.assertTrue(r.is_valid)
        self.assertEqual(r.errors, [])

    def test_with_errors(self):
        r = ValidationResult(is_valid=False, errors=["bad"])
        self.assertFalse(r.is_valid)
        self.assertEqual(r.errors, ["bad"])


class TestMessageValidatorBasics(unittest.TestCase):
    def setUp(self):
        self.v = MessageValidator()

    def test_valid_user_message(self):
        r = self.v.validate({"role": "user", "content": "hello"})
        self.assertTrue(r.is_valid)
        self.assertEqual(r.errors, [])

    def test_valid_assistant_message(self):
        r = self.v.validate({"role": "assistant", "content": "hi"})
        self.assertTrue(r.is_valid)

    def test_valid_system_message(self):
        r = self.v.validate({"role": "system", "content": "prompt"})
        self.assertTrue(r.is_valid)

    def test_valid_tool_message(self):
        r = self.v.validate({"role": "tool", "content": "ok", "tool_call_id": "tc1"})
        self.assertTrue(r.is_valid)

    def test_missing_role(self):
        r = self.v.validate({"content": "hello"})
        self.assertFalse(r.is_valid)
        self.assertIn("Missing required field 'role'", r.errors[0])

    def test_invalid_role(self):
        r = self.v.validate({"role": "admin", "content": "x"})
        self.assertFalse(r.is_valid)
        self.assertIn("Invalid role 'admin'", r.errors[0])

    def test_not_a_dict(self):
        r = self.v.validate("not a dict")
        self.assertFalse(r.is_valid)
        self.assertIn("must be a dict", r.errors[0])


class TestContentValidation(unittest.TestCase):
    def setUp(self):
        self.v = MessageValidator(max_content_length=50)

    def test_string_content_ok(self):
        r = self.v.validate({"role": "user", "content": "short"})
        self.assertTrue(r.is_valid)

    def test_string_content_too_long(self):
        r = self.v.validate({"role": "user", "content": "x" * 51})
        self.assertFalse(r.is_valid)
        self.assertIn("exceeds maximum", r.errors[0])

    def test_list_content_ok(self):
        r = self.v.validate({"role": "user", "content": [{"type": "text", "text": "hi"}]})
        self.assertTrue(r.is_valid)

    def test_list_content_missing_type(self):
        r = self.v.validate({"role": "user", "content": [{"text": "hi"}]})
        self.assertFalse(r.is_valid)
        self.assertIn("missing required 'type' key", r.errors[0])

    def test_list_content_not_dict_block(self):
        r = self.v.validate({"role": "user", "content": ["raw string"]})
        self.assertFalse(r.is_valid)
        self.assertIn("must be a dict", r.errors[0])

    def test_list_content_total_too_long(self):
        r = self.v.validate({
            "role": "user",
            "content": [{"type": "text", "text": "x" * 51}],
        })
        self.assertFalse(r.is_valid)
        self.assertIn("exceeds maximum", r.errors[0])

    def test_invalid_content_type(self):
        r = self.v.validate({"role": "user", "content": 12345})
        self.assertFalse(r.is_valid)
        self.assertIn("must be a string or a list", r.errors[0])

    def test_none_content_ok(self):
        r = self.v.validate({"role": "assistant", "content": None})
        self.assertTrue(r.is_valid)


class TestToolRoleValidation(unittest.TestCase):
    def setUp(self):
        self.v = MessageValidator()

    def test_tool_missing_tool_call_id(self):
        r = self.v.validate({"role": "tool", "content": "result"})
        self.assertFalse(r.is_valid)
        self.assertIn("tool_call_id", r.errors[0])

    def test_tool_with_tool_call_id(self):
        r = self.v.validate({"role": "tool", "content": "ok", "tool_call_id": "abc"})
        self.assertTrue(r.is_valid)


class TestValidateBatch(unittest.TestCase):
    def test_batch(self):
        v = MessageValidator()
        msgs = [
            {"role": "user", "content": "hi"},
            {"role": "bad"},
            {"role": "tool", "content": "x", "tool_call_id": "t1"},
        ]
        results = v.validate_batch(msgs)
        self.assertEqual(len(results), 3)
        self.assertTrue(results[0].is_valid)
        self.assertFalse(results[1].is_valid)
        self.assertTrue(results[2].is_valid)


class TestCustomRoles(unittest.TestCase):
    def test_custom_allowed_roles(self):
        v = MessageValidator(allowed_roles=frozenset({"user", "bot"}))
        self.assertTrue(v.validate({"role": "user"}).is_valid)
        self.assertTrue(v.validate({"role": "bot"}).is_valid)
        self.assertFalse(v.validate({"role": "system"}).is_valid)


class TestProperties(unittest.TestCase):
    def test_defaults(self):
        v = MessageValidator()
        self.assertEqual(v.max_content_length, DEFAULT_MAX_CONTENT_LENGTH)
        self.assertEqual(v.allowed_roles, VALID_ROLES)

    def test_custom(self):
        v = MessageValidator(max_content_length=42)
        self.assertEqual(v.max_content_length, 42)


if __name__ == "__main__":
    unittest.main()
