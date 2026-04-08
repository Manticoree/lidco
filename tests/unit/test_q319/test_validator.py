"""Tests for lidco.iac.validator — IaCValidator, security checks, cost estimation, policies."""

from __future__ import annotations

import unittest

from lidco.iac.validator import (
    Category,
    CostEstimate,
    Finding,
    IaCValidator,
    Severity,
    ValidationResult,
)


class TestSeverityAndCategory(unittest.TestCase):
    def test_severity_values(self) -> None:
        self.assertEqual(Severity.INFO.value, "info")
        self.assertEqual(Severity.CRITICAL.value, "critical")

    def test_category_values(self) -> None:
        self.assertEqual(Category.SECURITY.value, "security")
        self.assertEqual(Category.COST.value, "cost")


class TestFinding(unittest.TestCase):
    def test_creation(self) -> None:
        f = Finding(
            message="open ingress",
            severity=Severity.CRITICAL,
            category=Category.SECURITY,
            resource="sg",
            suggestion="restrict",
        )
        self.assertEqual(f.message, "open ingress")
        self.assertEqual(f.suggestion, "restrict")

    def test_frozen(self) -> None:
        f = Finding("x", Severity.INFO, Category.SYNTAX)
        with self.assertRaises(AttributeError):
            f.message = "y"  # type: ignore[misc]


class TestCostEstimate(unittest.TestCase):
    def test_creation(self) -> None:
        c = CostEstimate(resource="web", resource_type="aws_instance", monthly_usd=30.0)
        self.assertEqual(c.monthly_usd, 30.0)


class TestValidationResult(unittest.TestCase):
    def test_valid_empty(self) -> None:
        r = ValidationResult(valid=True)
        self.assertTrue(r.valid)
        self.assertEqual(r.errors, [])
        self.assertEqual(r.warnings, [])
        self.assertEqual(r.total_monthly_cost, 0.0)

    def test_errors_and_warnings(self) -> None:
        findings = [
            Finding("err", Severity.ERROR, Category.SYNTAX),
            Finding("warn", Severity.WARNING, Category.BEST_PRACTICE),
            Finding("crit", Severity.CRITICAL, Category.SECURITY),
            Finding("info", Severity.INFO, Category.COST),
        ]
        r = ValidationResult(valid=False, findings=findings)
        self.assertEqual(len(r.errors), 2)
        self.assertEqual(len(r.warnings), 1)

    def test_total_monthly_cost(self) -> None:
        costs = [
            CostEstimate("a", "aws_instance", 30.0),
            CostEstimate("b", "aws_s3_bucket", 5.0),
        ]
        r = ValidationResult(valid=True, cost_estimates=costs)
        self.assertAlmostEqual(r.total_monthly_cost, 35.0)


class TestValidateTerraform(unittest.TestCase):
    def test_empty_files_valid(self) -> None:
        v = IaCValidator()
        result = v.validate_terraform({})
        self.assertTrue(result.valid)

    def test_detects_open_ingress(self) -> None:
        v = IaCValidator()
        files = {"main.tf": 'ingress { cidr_blocks = ["0.0.0.0/0"] }'}
        result = v.validate_terraform(files)
        self.assertFalse(result.valid)
        security = [f for f in result.findings if f.category == Category.SECURITY]
        self.assertTrue(len(security) > 0)

    def test_detects_wildcard(self) -> None:
        v = IaCValidator()
        files = {"main.tf": 'actions = ["*"]'}
        result = v.validate_terraform(files)
        security = [f for f in result.findings if f.category == Category.SECURITY]
        self.assertTrue(len(security) > 0)

    def test_cost_estimation(self) -> None:
        v = IaCValidator()
        files = {"main.tf": 'resource "aws_instance" "web" { ami = "x" }'}
        result = v.validate_terraform(files)
        self.assertTrue(len(result.cost_estimates) > 0)
        self.assertTrue(result.total_monthly_cost > 0)

    def test_best_practice_no_terraform_block(self) -> None:
        v = IaCValidator()
        files = {"main.tf": 'provider "aws" { region = "us-east-1" }'}
        result = v.validate_terraform(files)
        bp = [f for f in result.findings if f.category == Category.BEST_PRACTICE]
        self.assertTrue(len(bp) > 0)

    def test_hardcoded_secret_detection(self) -> None:
        v = IaCValidator()
        files = {"main.tf": 'password = "mysecretpass"'}
        result = v.validate_terraform(files)
        security = [f for f in result.findings if f.category == Category.SECURITY]
        self.assertTrue(any("secret" in f.message.lower() or "password" in f.message.lower() for f in security))


class TestValidateCloudFormation(unittest.TestCase):
    def test_empty_template_no_resources(self) -> None:
        v = IaCValidator()
        result = v.validate_cloudformation({})
        self.assertFalse(result.valid)
        msgs = [f.message for f in result.findings]
        self.assertTrue(any("no resources" in m.lower() for m in msgs))

    def test_missing_version(self) -> None:
        v = IaCValidator()
        result = v.validate_cloudformation({"Resources": {"X": {"Type": "AWS::SNS::Topic"}}})
        warns = [f for f in result.findings if f.severity == Severity.WARNING]
        self.assertTrue(any("version" in f.message.lower() for f in warns))

    def test_valid_template(self) -> None:
        v = IaCValidator()
        tpl = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Resources": {
                "Bucket": {"Type": "AWS::S3::Bucket", "Properties": {"BucketName": "safe"}},
            },
        }
        result = v.validate_cloudformation(tpl)
        self.assertTrue(result.valid)

    def test_open_ingress_cf(self) -> None:
        v = IaCValidator()
        tpl = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Resources": {
                "SG": {
                    "Type": "AWS::EC2::SecurityGroup",
                    "Properties": {"CidrIp": "0.0.0.0/0"},
                },
            },
        }
        result = v.validate_cloudformation(tpl)
        self.assertFalse(result.valid)

    def test_cost_estimation_cf(self) -> None:
        v = IaCValidator()
        tpl = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Resources": {
                "Server": {"Type": "AWS::EC2::Instance", "Properties": {}},
            },
        }
        result = v.validate_cloudformation(tpl)
        self.assertTrue(len(result.cost_estimates) > 0)


class TestValidatePulumi(unittest.TestCase):
    def test_missing_pulumi_yaml(self) -> None:
        v = IaCValidator()
        result = v.validate_pulumi({"__main__.py": "import pulumi"})
        self.assertFalse(result.valid)

    def test_valid_pulumi(self) -> None:
        v = IaCValidator()
        result = v.validate_pulumi({
            "Pulumi.yaml": "name: test\nruntime: python\n",
            "__main__.py": "import pulumi\n",
        })
        self.assertTrue(result.valid)

    def test_security_check_pulumi(self) -> None:
        v = IaCValidator()
        result = v.validate_pulumi({
            "Pulumi.yaml": "name: test\nruntime: python\n",
            "__main__.py": 'cidr = "0.0.0.0/0"',
        })
        self.assertFalse(result.valid)


class TestCustomPolicies(unittest.TestCase):
    def test_policy_violation(self) -> None:
        v = IaCValidator()
        v.add_policy(
            "no-s3",
            lambda files: "S3 not allowed" if any("s3" in c for c in files.values()) else None,
            severity=Severity.ERROR,
        )
        result = v.validate_terraform({"main.tf": 'resource "aws_s3_bucket" "x" {}'})
        policy = [f for f in result.findings if f.category == Category.POLICY]
        self.assertTrue(len(policy) > 0)

    def test_policy_pass(self) -> None:
        v = IaCValidator()
        v.add_policy("no-s3", lambda files: None)
        result = v.validate_terraform({"main.tf": 'resource "aws_instance" "x" {}'})
        policy = [f for f in result.findings if f.category == Category.POLICY]
        self.assertEqual(len(policy), 0)

    def test_policy_exception_handled(self) -> None:
        v = IaCValidator()

        def bad_policy(files: dict[str, str]) -> str | None:
            raise RuntimeError("boom")

        v.add_policy("bad", bad_policy)
        result = v.validate_terraform({"main.tf": ""})
        policy = [f for f in result.findings if f.category == Category.POLICY]
        self.assertTrue(len(policy) > 0)
        self.assertTrue(any("failed" in f.message for f in policy))


if __name__ == "__main__":
    unittest.main()
