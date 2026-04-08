"""Tests for lidco.cli.commands.q319_cmds — /terraform, /cloudformation, /pulumi, /validate-iac."""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock


def _make_registry() -> MagicMock:
    """Create a mock registry and register Q319 commands."""
    from lidco.cli.commands.q319_cmds import register_q319_commands

    registry = MagicMock()
    handlers: dict[str, object] = {}

    def capture(name: str, desc: str, handler: object) -> None:
        handlers[name] = handler

    registry.register_async.side_effect = capture
    register_q319_commands(registry)
    registry._handlers = handlers
    return registry


class TestRegisterCommands(unittest.TestCase):
    def test_all_commands_registered(self) -> None:
        reg = _make_registry()
        names = list(reg._handlers.keys())
        self.assertIn("terraform", names)
        self.assertIn("cloudformation", names)
        self.assertIn("pulumi", names)
        self.assertIn("validate-iac", names)
        self.assertEqual(reg.register_async.call_count, 4)


class TestTerraformHandler(unittest.TestCase):
    def test_default(self) -> None:
        reg = _make_registry()
        handler = reg._handlers["terraform"]
        result = asyncio.run(handler(""))
        self.assertIn("Generated", result)
        self.assertIn("Terraform", result)

    def test_with_provider_and_region(self) -> None:
        reg = _make_registry()
        handler = reg._handlers["terraform"]
        result = asyncio.run(handler("--provider gcp --region us-central1"))
        self.assertIn("gcp", result)

    def test_with_resource(self) -> None:
        reg = _make_registry()
        handler = reg._handlers["terraform"]
        result = asyncio.run(handler("--resource aws_instance:web"))
        self.assertIn("aws_instance", result)

    def test_with_state(self) -> None:
        reg = _make_registry()
        handler = reg._handlers["terraform"]
        result = asyncio.run(handler("--state s3"))
        self.assertIn("backend", result)


class TestCloudFormationHandler(unittest.TestCase):
    def test_default(self) -> None:
        reg = _make_registry()
        handler = reg._handlers["cloudformation"]
        result = asyncio.run(handler(""))
        self.assertIn("CloudFormation", result)

    def test_with_desc(self) -> None:
        reg = _make_registry()
        handler = reg._handlers["cloudformation"]
        result = asyncio.run(handler('--desc "My stack"'))
        self.assertIn("template.json", result)

    def test_with_resource(self) -> None:
        reg = _make_registry()
        handler = reg._handlers["cloudformation"]
        result = asyncio.run(handler("--resource Bucket:AWS::S3::Bucket"))
        self.assertIn("Bucket", result)

    def test_with_output(self) -> None:
        reg = _make_registry()
        handler = reg._handlers["cloudformation"]
        result = asyncio.run(handler("--output BucketArn:arn"))
        self.assertIn("BucketArn", result)


class TestPulumiHandler(unittest.TestCase):
    def test_default(self) -> None:
        reg = _make_registry()
        handler = reg._handlers["pulumi"]
        result = asyncio.run(handler(""))
        self.assertIn("Pulumi", result)

    def test_with_lang_typescript(self) -> None:
        reg = _make_registry()
        handler = reg._handlers["pulumi"]
        result = asyncio.run(handler("--lang typescript"))
        self.assertIn("index.ts", result)

    def test_with_resource(self) -> None:
        reg = _make_registry()
        handler = reg._handlers["pulumi"]
        result = asyncio.run(handler("--resource bucket:aws:s3:Bucket"))
        self.assertIn("bucket", result)

    def test_with_stack(self) -> None:
        reg = _make_registry()
        handler = reg._handlers["pulumi"]
        result = asyncio.run(handler("--stack dev"))
        self.assertIn("Pulumi.dev.yaml", result)

    def test_with_name(self) -> None:
        reg = _make_registry()
        handler = reg._handlers["pulumi"]
        result = asyncio.run(handler("--name myproject"))
        self.assertIn("myproject", result)


class TestValidateIacHandler(unittest.TestCase):
    def test_terraform_default(self) -> None:
        reg = _make_registry()
        handler = reg._handlers["validate-iac"]
        result = asyncio.run(handler(""))
        self.assertIn("Validation", result)
        self.assertIn("PASS", result)

    def test_cloudformation_type(self) -> None:
        reg = _make_registry()
        handler = reg._handlers["validate-iac"]
        result = asyncio.run(handler("--type cloudformation"))
        self.assertIn("FAIL", result)

    def test_pulumi_type(self) -> None:
        reg = _make_registry()
        handler = reg._handlers["validate-iac"]
        result = asyncio.run(handler("--type pulumi"))
        self.assertIn("FAIL", result)


if __name__ == "__main__":
    unittest.main()
