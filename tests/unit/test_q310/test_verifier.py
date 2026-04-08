"""Tests for lidco.contracts.verifier."""

import unittest

from lidco.contracts.definitions import (
    ContractDefinition,
    EndpointSchema,
    FieldSchema,
    FieldType,
)
from lidco.contracts.verifier import (
    ContractVerifier,
    ProviderEndpoint,
    ProviderSpec,
    Severity,
    VerificationIssue,
    VerificationResult,
    _mock_value,
)


def _contract(endpoints=()):
    return ContractDefinition(
        name="test-api",
        version="1.0.0",
        provider="svc",
        consumer="web",
        endpoints=endpoints,
    )


def _endpoint(method="GET", path="/test", req=(), resp=(), status=200):
    return EndpointSchema(
        method=method, path=path,
        request_fields=req, response_fields=resp,
        status_code=status,
    )


def _field(name, ft=FieldType.STRING, required=True):
    return FieldSchema(name=name, field_type=ft, required=required)


class TestVerificationIssue(unittest.TestCase):
    def test_to_dict(self):
        issue = VerificationIssue(
            endpoint="GET /x", message="missing", field_name="id",
        )
        d = issue.to_dict()
        self.assertEqual(d["endpoint"], "GET /x")
        self.assertEqual(d["field_name"], "id")
        self.assertEqual(d["severity"], "error")

    def test_to_dict_no_field(self):
        issue = VerificationIssue(endpoint="GET /x", message="bad")
        d = issue.to_dict()
        self.assertNotIn("field_name", d)


class TestVerificationResult(unittest.TestCase):
    def test_passed(self):
        r = VerificationResult(
            contract_name="a", contract_version="1.0.0", passed=True,
        )
        self.assertTrue(r.passed)
        self.assertEqual(r.error_count, 0)
        self.assertEqual(r.warning_count, 0)

    def test_counts(self):
        issues = (
            VerificationIssue("ep", "err", Severity.ERROR),
            VerificationIssue("ep", "warn", Severity.WARNING),
            VerificationIssue("ep", "info", Severity.INFO),
        )
        r = VerificationResult(
            contract_name="a", contract_version="1.0.0",
            passed=False, issues=issues,
        )
        self.assertEqual(r.error_count, 1)
        self.assertEqual(r.warning_count, 1)

    def test_to_dict(self):
        r = VerificationResult(
            contract_name="a", contract_version="1.0.0",
            passed=True, endpoints_checked=3,
        )
        d = r.to_dict()
        self.assertEqual(d["endpoints_checked"], 3)
        self.assertTrue(d["passed"])


class TestContractVerifier(unittest.TestCase):
    def setUp(self):
        self.verifier = ContractVerifier()

    def test_empty_contract(self):
        result = self.verifier.verify(
            _contract(), ProviderSpec(name="svc"),
        )
        self.assertTrue(result.passed)
        self.assertEqual(result.endpoints_checked, 0)

    def test_missing_endpoint(self):
        contract = _contract(endpoints=(_endpoint(),))
        result = self.verifier.verify(
            contract, ProviderSpec(name="svc"),
        )
        self.assertFalse(result.passed)
        self.assertEqual(result.error_count, 1)
        self.assertIn("not implemented", result.issues[0].message)

    def test_matching_endpoint(self):
        resp = (_field("id", FieldType.INTEGER),)
        contract = _contract(endpoints=(_endpoint(resp=resp),))
        provider = ProviderSpec(
            name="svc",
            endpoints=(
                ProviderEndpoint(
                    method="GET", path="/test",
                    response_fields=("id",),
                ),
            ),
        )
        result = self.verifier.verify(contract, provider)
        self.assertTrue(result.passed)

    def test_missing_required_response_field(self):
        resp = (_field("id"), _field("name"))
        contract = _contract(endpoints=(_endpoint(resp=resp),))
        provider = ProviderSpec(
            name="svc",
            endpoints=(
                ProviderEndpoint(
                    method="GET", path="/test",
                    response_fields=("id",),
                ),
            ),
        )
        result = self.verifier.verify(contract, provider)
        self.assertFalse(result.passed)
        self.assertEqual(result.error_count, 1)

    def test_optional_field_not_required(self):
        resp = (_field("id"), _field("extra", required=False))
        contract = _contract(endpoints=(_endpoint(resp=resp),))
        provider = ProviderSpec(
            name="svc",
            endpoints=(
                ProviderEndpoint(
                    method="GET", path="/test",
                    response_fields=("id",),
                ),
            ),
        )
        result = self.verifier.verify(contract, provider)
        self.assertTrue(result.passed)

    def test_status_code_mismatch_warning(self):
        contract = _contract(endpoints=(_endpoint(status=200),))
        provider = ProviderSpec(
            name="svc",
            endpoints=(
                ProviderEndpoint(method="GET", path="/test", status_code=201),
            ),
        )
        result = self.verifier.verify(contract, provider)
        self.assertTrue(result.passed)  # warnings don't fail
        self.assertEqual(result.warning_count, 1)

    def test_case_insensitive_method(self):
        contract = _contract(endpoints=(_endpoint(method="get"),))
        provider = ProviderSpec(
            name="svc",
            endpoints=(ProviderEndpoint(method="GET", path="/test"),),
        )
        result = self.verifier.verify(contract, provider)
        self.assertTrue(result.passed)


class TestBackwardCompatibility(unittest.TestCase):
    def setUp(self):
        self.verifier = ContractVerifier()

    def test_identical_contracts_compatible(self):
        ep = _endpoint(resp=(_field("id"),))
        old = _contract(endpoints=(ep,))
        new = _contract(endpoints=(ep,))
        result = self.verifier.check_backward_compatibility(old, new)
        self.assertTrue(result.passed)

    def test_removed_endpoint_breaks(self):
        old = _contract(endpoints=(_endpoint(),))
        new = ContractDefinition(
            name="test-api", version="2.0.0",
            provider="svc", consumer="web",
        )
        result = self.verifier.check_backward_compatibility(old, new)
        self.assertFalse(result.passed)

    def test_removed_required_field_breaks(self):
        old_ep = _endpoint(resp=(_field("id"), _field("name")))
        new_ep = _endpoint(resp=(_field("id"),))
        old = _contract(endpoints=(old_ep,))
        new = ContractDefinition(
            name="test-api", version="2.0.0",
            provider="svc", consumer="web",
            endpoints=(new_ep,),
        )
        result = self.verifier.check_backward_compatibility(old, new)
        self.assertFalse(result.passed)

    def test_new_required_request_field_is_warning(self):
        old_ep = _endpoint(req=(_field("name"),))
        new_ep = _endpoint(req=(_field("name"), _field("email")))
        old = _contract(endpoints=(old_ep,))
        new = ContractDefinition(
            name="test-api", version="2.0.0",
            provider="svc", consumer="web",
            endpoints=(new_ep,),
        )
        result = self.verifier.check_backward_compatibility(old, new)
        self.assertTrue(result.passed)  # warning, not error
        self.assertEqual(result.warning_count, 1)

    def test_adding_endpoint_is_fine(self):
        ep1 = _endpoint(method="GET", path="/a")
        ep2 = _endpoint(method="GET", path="/b")
        old = _contract(endpoints=(ep1,))
        new = ContractDefinition(
            name="test-api", version="2.0.0",
            provider="svc", consumer="web",
            endpoints=(ep1, ep2),
        )
        result = self.verifier.check_backward_compatibility(old, new)
        self.assertTrue(result.passed)


class TestMockConsumer(unittest.TestCase):
    def test_generates_mocks(self):
        resp = (
            _field("id", FieldType.INTEGER),
            _field("name", FieldType.STRING),
            _field("active", FieldType.BOOLEAN),
        )
        contract = _contract(endpoints=(_endpoint(resp=resp),))
        verifier = ContractVerifier()
        mocks = verifier.mock_consumer(contract)
        self.assertIn("GET /test", mocks)
        body = mocks["GET /test"]["body"]
        self.assertEqual(body["id"], 0)
        self.assertEqual(body["name"], "")
        self.assertFalse(body["active"])

    def test_mock_uses_default(self):
        f = FieldSchema(
            name="count", field_type=FieldType.INTEGER, default=42,
        )
        contract = _contract(endpoints=(_endpoint(resp=(f,)),))
        verifier = ContractVerifier()
        mocks = verifier.mock_consumer(contract)
        self.assertEqual(mocks["GET /test"]["body"]["count"], 42)

    def test_mock_empty_contract(self):
        contract = _contract()
        verifier = ContractVerifier()
        mocks = verifier.mock_consumer(contract)
        self.assertEqual(mocks, {})


class TestMockValue(unittest.TestCase):
    def test_all_types(self):
        self.assertEqual(_mock_value(_field("x", FieldType.STRING)), "")
        self.assertEqual(_mock_value(_field("x", FieldType.INTEGER)), 0)
        self.assertEqual(_mock_value(_field("x", FieldType.FLOAT)), 0.0)
        self.assertFalse(_mock_value(_field("x", FieldType.BOOLEAN)))
        self.assertEqual(_mock_value(_field("x", FieldType.ARRAY)), [])
        self.assertEqual(_mock_value(_field("x", FieldType.OBJECT)), {})
        self.assertIsNone(_mock_value(_field("x", FieldType.NULL)))
        self.assertIsNone(_mock_value(_field("x", FieldType.ANY)))


if __name__ == "__main__":
    unittest.main()
