"""Tests for Q140 ArgParser."""
from __future__ import annotations

import unittest

from lidco.input.arg_parser import ArgParser, ParsedArgs, ArgSpec


class TestParsedArgs(unittest.TestCase):
    def test_defaults(self):
        p = ParsedArgs()
        self.assertEqual(p.positional, [])
        self.assertEqual(p.flags, {})
        self.assertEqual(p.options, {})
        self.assertEqual(p.raw, "")
        self.assertEqual(p.errors, [])


class TestArgSpec(unittest.TestCase):
    def test_defaults(self):
        s = ArgSpec(name="x")
        self.assertEqual(s.type, "str")
        self.assertFalse(s.required)
        self.assertIsNone(s.default)
        self.assertEqual(s.help, "")


class TestArgParser(unittest.TestCase):
    def test_empty_parse(self):
        parser = ArgParser("test")
        result = parser.parse("")
        self.assertEqual(result.positional, [])
        self.assertEqual(result.raw, "")

    def test_positional_required(self):
        parser = ArgParser("cmd")
        parser.add_positional("file", required=True)
        result = parser.parse("hello.txt")
        self.assertEqual(result.positional, ["hello.txt"])
        self.assertEqual(result.errors, [])

    def test_positional_missing_required(self):
        parser = ArgParser("cmd")
        parser.add_positional("file", required=True)
        result = parser.parse("")
        self.assertIn("Missing required argument: file", result.errors)

    def test_positional_optional_with_default(self):
        parser = ArgParser("cmd")
        parser.add_positional("mode", required=False, default="auto")
        result = parser.parse("")
        self.assertEqual(result.positional, ["auto"])

    def test_flag_parsing(self):
        parser = ArgParser("cmd")
        parser.add_flag("verbose", short="v")
        result = parser.parse("--verbose")
        self.assertTrue(result.flags["verbose"])

    def test_flag_short(self):
        parser = ArgParser("cmd")
        parser.add_flag("verbose", short="v")
        result = parser.parse("-v")
        self.assertTrue(result.flags["verbose"])

    def test_flag_default_false(self):
        parser = ArgParser("cmd")
        parser.add_flag("verbose", short="v")
        result = parser.parse("")
        self.assertFalse(result.flags["verbose"])

    def test_option_parsing(self):
        parser = ArgParser("cmd")
        parser.add_option("output", short="o")
        result = parser.parse("--output result.txt")
        self.assertEqual(result.options["output"], "result.txt")

    def test_option_short(self):
        parser = ArgParser("cmd")
        parser.add_option("output", short="o")
        result = parser.parse("-o result.txt")
        self.assertEqual(result.options["output"], "result.txt")

    def test_option_missing_value(self):
        parser = ArgParser("cmd")
        parser.add_option("output")
        result = parser.parse("--output")
        self.assertTrue(any("requires a value" in e for e in result.errors))

    def test_option_default(self):
        parser = ArgParser("cmd")
        parser.add_option("format", default="json")
        result = parser.parse("")
        self.assertEqual(result.options["format"], "json")

    def test_option_required_missing(self):
        parser = ArgParser("cmd")
        parser.add_option("name", required=True)
        result = parser.parse("")
        self.assertTrue(any("Missing required option" in e for e in result.errors))

    def test_type_coercion_int(self):
        parser = ArgParser("cmd")
        parser.add_positional("count", type="int")
        result = parser.parse("42")
        self.assertEqual(result.positional, ["42"])
        self.assertEqual(result.errors, [])

    def test_type_coercion_int_invalid(self):
        parser = ArgParser("cmd")
        parser.add_positional("count", type="int")
        result = parser.parse("abc")
        self.assertTrue(any("Cannot convert" in e for e in result.errors))

    def test_type_coercion_float(self):
        parser = ArgParser("cmd")
        parser.add_positional("ratio", type="float")
        result = parser.parse("3.14")
        self.assertEqual(result.positional, ["3.14"])

    def test_combined_args(self):
        parser = ArgParser("deploy")
        parser.add_positional("target")
        parser.add_flag("force", short="f")
        parser.add_option("env", default="staging")
        result = parser.parse("production -f --env live")
        self.assertEqual(result.positional, ["production"])
        self.assertTrue(result.flags["force"])
        self.assertEqual(result.options["env"], "live")

    def test_extra_positionals_kept(self):
        parser = ArgParser("cmd")
        parser.add_positional("first")
        result = parser.parse("one two three")
        self.assertIn("one", result.positional)
        self.assertIn("two", result.positional)
        self.assertIn("three", result.positional)

    def test_raw_preserved(self):
        parser = ArgParser("cmd")
        result = parser.parse("foo bar")
        self.assertEqual(result.raw, "foo bar")

    def test_usage_string(self):
        parser = ArgParser("test")
        parser.add_positional("file")
        parser.add_flag("verbose", short="v")
        usage = parser.usage()
        self.assertIn("/test", usage)
        self.assertIn("<file>", usage)

    def test_help_text(self):
        parser = ArgParser("test")
        parser.add_positional("file", help="The input file")
        parser.add_option("output", short="o", help="Output path")
        parser.add_flag("verbose", short="v", help="Enable verbose")
        text = parser.help_text()
        self.assertIn("Positional", text)
        self.assertIn("Options", text)
        self.assertIn("Flags", text)
        self.assertIn("The input file", text)

    def test_quoted_args(self):
        parser = ArgParser("cmd")
        parser.add_positional("msg")
        result = parser.parse('"hello world"')
        self.assertEqual(result.positional, ["hello world"])

    def test_parse_error_bad_quotes(self):
        parser = ArgParser("cmd")
        result = parser.parse('"unclosed')
        self.assertTrue(any("Parse error" in e for e in result.errors))


if __name__ == "__main__":
    unittest.main()
