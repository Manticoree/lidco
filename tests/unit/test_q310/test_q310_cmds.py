"""Tests for Q310 CLI commands."""

import asyncio
import json
import unittest


class _FakeRegistry:
    """Minimal registry to capture registrations."""

    def __init__(self):
        self.commands: dict[str, object] = {}

    def register_async(self, name: str, description: str, handler) -> None:
        self.commands[name] = handler


def _build_registry() -> _FakeRegistry:
    from lidco.cli.commands.q310_cmds import register_q310_commands
    reg = _FakeRegistry()
    register_q310_commands(reg)
    return reg


class TestRegistration(unittest.TestCase):
    def test_registers_contract(self):
        reg = _build_registry()
        self.assertIn("contract", reg.commands)

    def test_registers_verify_contract(self):
        reg = _build_registry()
        self.assertIn("verify-contract", reg.commands)

    def test_registers_gen_contract(self):
        reg = _build_registry()
        self.assertIn("gen-contract", reg.commands)

    def test_registers_contract_broker(self):
        reg = _build_registry()
        self.assertIn("contract-broker", reg.commands)

    def test_four_commands(self):
        reg = _build_registry()
        self.assertEqual(len(reg.commands), 4)


class TestContractHandler(unittest.TestCase):
    def _handler(self):
        return _build_registry().commands["contract"]

    def test_no_args_shows_usage(self):
        result = asyncio.run(self._handler()(""))
        self.assertIn("Usage", result)

    def test_list(self):
        result = asyncio.run(self._handler()("list"))
        self.assertIn("Contracts", result)

    def test_show_missing_args(self):
        result = asyncio.run(self._handler()("show api"))
        self.assertIn("Usage", result)

    def test_show(self):
        result = asyncio.run(self._handler()("show api 1.0.0"))
        self.assertIn("api", result)

    def test_define_valid(self):
        data = json.dumps({
            "name": "api", "version": "1.0.0",
            "provider": "svc", "consumer": "web",
        })
        result = asyncio.run(self._handler()(f"define {data}"))
        self.assertIn("Defined contract", result)
        self.assertIn("api", result)

    def test_define_invalid_json(self):
        result = asyncio.run(self._handler()("define {bad"))
        self.assertIn("Error", result)

    def test_define_no_args(self):
        result = asyncio.run(self._handler()("define"))
        self.assertIn("Usage", result)

    def test_versions_missing(self):
        result = asyncio.run(self._handler()("versions"))
        self.assertIn("Usage", result)

    def test_versions(self):
        result = asyncio.run(self._handler()("versions api"))
        self.assertIn("api", result)

    def test_remove_missing(self):
        result = asyncio.run(self._handler()("remove api"))
        self.assertIn("Usage", result)

    def test_remove(self):
        result = asyncio.run(self._handler()("remove api 1.0.0"))
        self.assertIn("Removed", result)

    def test_unknown_subcmd(self):
        result = asyncio.run(self._handler()("badcmd"))
        self.assertIn("Unknown", result)


class TestVerifyContractHandler(unittest.TestCase):
    def _handler(self):
        return _build_registry().commands["verify-contract"]

    def test_no_args_shows_usage(self):
        result = asyncio.run(self._handler()(""))
        self.assertIn("Usage", result)

    def test_compat_missing_args(self):
        result = asyncio.run(self._handler()("compat"))
        self.assertIn("Usage", result)

    def test_mock_no_args(self):
        result = asyncio.run(self._handler()("mock"))
        self.assertIn("Usage", result)

    def test_mock_valid(self):
        data = json.dumps({
            "name": "api", "version": "1.0.0",
            "provider": "svc", "consumer": "web",
            "endpoints": [{
                "method": "GET", "path": "/test",
                "response": [{"name": "id", "type": "integer", "required": True}],
            }],
        })
        result = asyncio.run(self._handler()(f"mock {data}"))
        self.assertIn("GET /test", result)

    def test_parse_contract(self):
        data = json.dumps({
            "name": "api", "version": "1.0.0",
            "provider": "svc", "consumer": "web",
        })
        result = asyncio.run(self._handler()(data))
        self.assertIn("api", result)

    def test_parse_invalid(self):
        result = asyncio.run(self._handler()("{bad}"))
        self.assertIn("Error", result)


class TestGenContractHandler(unittest.TestCase):
    def _handler(self):
        return _build_registry().commands["gen-contract"]

    def test_no_args_shows_usage(self):
        result = asyncio.run(self._handler()(""))
        self.assertIn("Usage", result)

    def test_record_missing_args(self):
        result = asyncio.run(self._handler()("record"))
        self.assertIn("Usage", result)

    def test_record(self):
        result = asyncio.run(self._handler()("record GET /api"))
        self.assertIn("Recorded", result)
        self.assertIn("GET", result)

    def test_record_with_status(self):
        result = asyncio.run(self._handler()("record POST /api 201"))
        self.assertIn("201", result)

    def test_generate_missing_args(self):
        result = asyncio.run(self._handler()("generate api"))
        self.assertIn("Usage", result)

    def test_generate(self):
        result = asyncio.run(self._handler()("generate api 1.0.0 svc web"))
        self.assertIn("Generated", result)
        self.assertIn("api", result)

    def test_generate_bad_version(self):
        result = asyncio.run(self._handler()("generate api bad svc web"))
        self.assertIn("Error", result)

    def test_pact_missing_args(self):
        result = asyncio.run(self._handler()("pact"))
        self.assertIn("Usage", result)

    def test_pact(self):
        result = asyncio.run(self._handler()("pact svc web"))
        data = json.loads(result)
        self.assertEqual(data["provider"]["name"], "svc")

    def test_clear(self):
        result = asyncio.run(self._handler()("clear"))
        self.assertIn("Cleared", result)

    def test_unknown(self):
        result = asyncio.run(self._handler()("badcmd"))
        self.assertIn("Unknown", result)


class TestContractBrokerHandler(unittest.TestCase):
    def _handler(self):
        return _build_registry().commands["contract-broker"]

    def test_no_args_shows_usage(self):
        result = asyncio.run(self._handler()(""))
        self.assertIn("Usage", result)

    def test_publish_no_args(self):
        result = asyncio.run(self._handler()("publish"))
        self.assertIn("Usage", result)

    def test_publish_valid(self):
        data = json.dumps({
            "name": "api", "version": "1.0.0",
            "provider": "svc", "consumer": "web",
        })
        result = asyncio.run(self._handler()(f"publish {data}"))
        self.assertIn("Published", result)

    def test_publish_invalid(self):
        result = asyncio.run(self._handler()("publish {bad"))
        self.assertIn("Error", result)

    def test_list_empty(self):
        result = asyncio.run(self._handler()("list"))
        self.assertIn("No contracts", result)

    def test_matrix_empty(self):
        result = asyncio.run(self._handler()("matrix"))
        self.assertIn("No verification", result)

    def test_dashboard_empty(self):
        result = asyncio.run(self._handler()("dashboard"))
        self.assertIn("No data", result)

    def test_webhook(self):
        result = asyncio.run(self._handler()("webhook https://example.com"))
        self.assertIn("Registered", result)

    def test_webhook_missing(self):
        result = asyncio.run(self._handler()("webhook"))
        self.assertIn("Usage", result)

    def test_unknown(self):
        result = asyncio.run(self._handler()("badcmd"))
        self.assertIn("Unknown", result)


if __name__ == "__main__":
    unittest.main()
