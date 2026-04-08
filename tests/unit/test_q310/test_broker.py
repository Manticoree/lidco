"""Tests for lidco.contracts.broker."""

import json
import os
import tempfile
import unittest
from unittest.mock import patch

from lidco.contracts.broker import (
    ContractBroker,
    DashboardEntry,
    MatrixEntry,
    WebhookConfig,
)
from lidco.contracts.definitions import ContractDefinition, EndpointSchema, FieldSchema, FieldType
from lidco.contracts.verifier import VerificationResult


def _contract(name="api", version="1.0.0", provider="svc", consumer="web"):
    return ContractDefinition(
        name=name, version=version, provider=provider, consumer=consumer,
    )


def _result(passed=True, errors=0, warnings=0):
    from lidco.contracts.verifier import Severity, VerificationIssue
    issues = []
    for _ in range(errors):
        issues.append(VerificationIssue("ep", "err", Severity.ERROR))
    for _ in range(warnings):
        issues.append(VerificationIssue("ep", "warn", Severity.WARNING))
    return VerificationResult(
        contract_name="api", contract_version="1.0.0",
        passed=passed, issues=tuple(issues),
    )


class TestWebhookConfig(unittest.TestCase):
    def test_defaults(self):
        wh = WebhookConfig(url="https://example.com/hook")
        self.assertEqual(wh.url, "https://example.com/hook")
        self.assertEqual(wh.events, ("break",))
        self.assertTrue(wh.enabled)


class TestMatrixEntry(unittest.TestCase):
    def test_creation(self):
        e = MatrixEntry(
            provider="p", consumer="c", contract_name="api",
            version="1.0.0", compatible=True,
        )
        self.assertTrue(e.compatible)


class TestDashboardEntry(unittest.TestCase):
    def test_creation(self):
        e = DashboardEntry(
            contract_name="api", total_versions=2,
            compatible_count=1, incompatible_count=1,
            latest_version="2.0.0",
        )
        self.assertEqual(e.incompatible_count, 1)


class TestContractBroker(unittest.TestCase):
    def test_empty(self):
        broker = ContractBroker()
        self.assertEqual(broker.contract_count, 0)
        self.assertEqual(broker.list_contracts(), [])

    def test_publish(self):
        broker = ContractBroker()
        broker.publish(_contract())
        self.assertEqual(broker.contract_count, 1)

    def test_get_contract(self):
        broker = ContractBroker()
        broker.publish(_contract())
        self.assertIsNotNone(broker.get_contract("api", "1.0.0"))
        self.assertIsNone(broker.get_contract("api", "9.0.0"))

    def test_list_contracts(self):
        broker = ContractBroker()
        broker.publish(_contract(name="a"))
        broker.publish(_contract(name="b"))
        self.assertEqual(len(broker.list_contracts()), 2)

    def test_list_versions(self):
        broker = ContractBroker()
        broker.publish(_contract(version="1.0.0"))
        broker.publish(_contract(version="2.0.0"))
        self.assertEqual(broker.list_versions("api"), ["1.0.0", "2.0.0"])

    def test_record_verification_pass(self):
        broker = ContractBroker()
        c = _contract()
        broker.publish(c)
        broker.record_verification(c, _result(passed=True))
        matrix = broker.version_matrix()
        self.assertEqual(len(matrix), 1)
        self.assertTrue(matrix[0].compatible)

    def test_record_verification_fail_fires_webhook(self):
        broker = ContractBroker()
        broker.add_webhook(WebhookConfig(url="https://hook.example.com"))
        c = _contract()
        broker.publish(c)
        broker.record_verification(c, _result(passed=False, errors=2))
        self.assertEqual(len(broker.webhook_log), 1)
        self.assertEqual(broker.webhook_log[0]["event"], "break")
        self.assertEqual(broker.webhook_log[0]["payload"]["errors"], 2)

    def test_webhook_disabled(self):
        broker = ContractBroker()
        broker.add_webhook(WebhookConfig(url="https://x.com", enabled=False))
        c = _contract()
        broker.record_verification(c, _result(passed=False, errors=1))
        self.assertEqual(len(broker.webhook_log), 0)

    def test_webhook_event_filter(self):
        broker = ContractBroker()
        broker.add_webhook(WebhookConfig(url="https://x.com", events=("publish",)))
        c = _contract()
        broker.record_verification(c, _result(passed=False, errors=1))
        self.assertEqual(len(broker.webhook_log), 0)

    def test_version_matrix_filtered(self):
        broker = ContractBroker()
        c1 = _contract(name="a")
        c2 = _contract(name="b")
        broker.record_verification(c1, _result())
        broker.record_verification(c2, _result())
        self.assertEqual(len(broker.version_matrix("a")), 1)
        self.assertEqual(len(broker.version_matrix()), 2)

    def test_dashboard_empty(self):
        broker = ContractBroker()
        self.assertEqual(broker.dashboard(), [])

    def test_dashboard(self):
        broker = ContractBroker()
        c = _contract()
        broker.record_verification(c, _result(passed=True))
        c2 = _contract(version="2.0.0")
        broker.record_verification(c2, _result(passed=False, errors=1))
        dash = broker.dashboard()
        self.assertEqual(len(dash), 1)
        entry = dash[0]
        self.assertEqual(entry.contract_name, "api")
        self.assertEqual(entry.compatible_count, 1)
        self.assertEqual(entry.incompatible_count, 1)
        self.assertEqual(entry.latest_version, "2.0.0")

    def test_webhook_count(self):
        broker = ContractBroker()
        self.assertEqual(broker.webhook_count, 0)
        broker.add_webhook(WebhookConfig(url="https://a.com"))
        self.assertEqual(broker.webhook_count, 1)

    def test_export_import_json(self):
        broker = ContractBroker()
        broker.publish(_contract(version="1.0.0"))
        broker.publish(_contract(version="2.0.0"))
        exported = broker.export_json()

        broker2 = ContractBroker()
        count = broker2.import_json(exported)
        self.assertEqual(count, 2)
        self.assertEqual(broker2.contract_count, 2)

    def test_save_load(self):
        broker = ContractBroker()
        broker.publish(_contract())
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "contracts.json")
            broker.save(path)

            broker2 = ContractBroker()
            count = broker2.load(path)
            self.assertEqual(count, 1)
            self.assertEqual(broker2.contract_count, 1)

    def test_load_nonexistent(self):
        broker = ContractBroker()
        count = broker.load("/nonexistent/path.json")
        self.assertEqual(count, 0)

    def test_save_creates_dirs(self):
        broker = ContractBroker()
        broker.publish(_contract())
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "sub", "dir", "contracts.json")
            broker.save(path)
            self.assertTrue(os.path.exists(path))


if __name__ == "__main__":
    unittest.main()
