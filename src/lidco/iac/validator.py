"""IaC Validator — Validate IaC templates, security checks, cost estimation, best practices, policy compliance."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Severity(Enum):
    """Validation finding severity."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class Category(Enum):
    """Validation finding category."""

    SECURITY = "security"
    COST = "cost"
    BEST_PRACTICE = "best_practice"
    POLICY = "policy"
    SYNTAX = "syntax"


@dataclass(frozen=True)
class Finding:
    """A single validation finding."""

    message: str
    severity: Severity
    category: Category
    resource: str = ""
    suggestion: str = ""


@dataclass(frozen=True)
class CostEstimate:
    """Estimated monthly cost for a resource."""

    resource: str
    resource_type: str
    monthly_usd: float
    detail: str = ""


@dataclass(frozen=True)
class ValidationResult:
    """Result of IaC validation."""

    valid: bool
    findings: list[Finding] = field(default_factory=list)
    cost_estimates: list[CostEstimate] = field(default_factory=list)

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity in (Severity.ERROR, Severity.CRITICAL)]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == Severity.WARNING]

    @property
    def total_monthly_cost(self) -> float:
        return sum(c.monthly_usd for c in self.cost_estimates)


# --------------------------------------------------------------------------- #
# Built-in rules
# --------------------------------------------------------------------------- #

_INSECURE_PATTERNS: list[tuple[str, str]] = [
    ("0.0.0.0/0", "Ingress open to all IPs (0.0.0.0/0)"),
    ("::/0", "Ingress open to all IPv6 (::/0)"),
    ("*", "Wildcard access granted"),
]

_COST_MAP: dict[str, float] = {
    # Very rough monthly estimates for demo purposes
    "aws_instance": 30.0,
    "aws_rds_instance": 50.0,
    "aws_s3_bucket": 5.0,
    "aws_lambda_function": 2.0,
    "aws_lb": 25.0,
    "AWS::EC2::Instance": 30.0,
    "AWS::RDS::DBInstance": 50.0,
    "AWS::S3::Bucket": 5.0,
    "AWS::Lambda::Function": 2.0,
}


class IaCValidator:
    """Validate IaC configurations against security, cost, best-practice, and policy rules."""

    def __init__(self) -> None:
        self._policies: list[_PolicyRule] = []

    # -- public API -------------------------------------------------------

    def add_policy(
        self,
        name: str,
        check: _CheckFn,
        severity: Severity = Severity.ERROR,
    ) -> None:
        """Register a custom policy rule."""
        self._policies.append(_PolicyRule(name=name, check=check, severity=severity))

    def validate_terraform(self, files: dict[str, str]) -> ValidationResult:
        """Validate Terraform file contents (simple heuristic scan)."""
        findings: list[Finding] = []
        cost_estimates: list[CostEstimate] = []

        for fname, content in files.items():
            findings.extend(self._check_security(content, fname))
            findings.extend(self._check_best_practices_tf(content, fname))
            cost_estimates.extend(self._estimate_cost_tf(content))

        findings.extend(self._run_policies(files))
        valid = not any(
            f.severity in (Severity.ERROR, Severity.CRITICAL) for f in findings
        )
        return ValidationResult(valid=valid, findings=findings, cost_estimates=cost_estimates)

    def validate_cloudformation(self, template: dict[str, Any]) -> ValidationResult:
        """Validate a parsed CloudFormation template dict."""
        findings: list[Finding] = []
        cost_estimates: list[CostEstimate] = []

        if "AWSTemplateFormatVersion" not in template:
            findings.append(
                Finding(
                    message="Missing AWSTemplateFormatVersion",
                    severity=Severity.WARNING,
                    category=Category.SYNTAX,
                )
            )

        resources = template.get("Resources", {})
        if not resources:
            findings.append(
                Finding(
                    message="Template has no resources",
                    severity=Severity.ERROR,
                    category=Category.SYNTAX,
                )
            )

        for logical_id, rdef in resources.items():
            rtype = rdef.get("Type", "")
            props = rdef.get("Properties", {})

            # Security: check for open ingress
            content_str = str(props)
            for pattern, msg in _INSECURE_PATTERNS:
                if pattern in content_str:
                    findings.append(
                        Finding(
                            message=msg,
                            severity=Severity.CRITICAL,
                            category=Category.SECURITY,
                            resource=logical_id,
                            suggestion="Restrict to specific CIDR ranges",
                        )
                    )

            # Cost
            if rtype in _COST_MAP:
                cost_estimates.append(
                    CostEstimate(
                        resource=logical_id,
                        resource_type=rtype,
                        monthly_usd=_COST_MAP[rtype],
                    )
                )

        valid = not any(
            f.severity in (Severity.ERROR, Severity.CRITICAL) for f in findings
        )
        return ValidationResult(valid=valid, findings=findings, cost_estimates=cost_estimates)

    def validate_pulumi(self, files: dict[str, str]) -> ValidationResult:
        """Validate Pulumi program file contents (heuristic scan)."""
        findings: list[Finding] = []

        for fname, content in files.items():
            findings.extend(self._check_security(content, fname))

        # Check for Pulumi.yaml
        if "Pulumi.yaml" not in files:
            findings.append(
                Finding(
                    message="Missing Pulumi.yaml project file",
                    severity=Severity.ERROR,
                    category=Category.SYNTAX,
                )
            )

        findings.extend(self._run_policies(files))
        valid = not any(
            f.severity in (Severity.ERROR, Severity.CRITICAL) for f in findings
        )
        return ValidationResult(valid=valid, findings=findings)

    # -- internals --------------------------------------------------------

    def _check_security(self, content: str, filename: str) -> list[Finding]:
        findings: list[Finding] = []
        for pattern, msg in _INSECURE_PATTERNS:
            if pattern in content:
                findings.append(
                    Finding(
                        message=f"{msg} in {filename}",
                        severity=Severity.CRITICAL,
                        category=Category.SECURITY,
                        resource=filename,
                        suggestion="Restrict to specific CIDR ranges",
                    )
                )
        # Hardcoded secrets heuristic
        lower = content.lower()
        for secret_kw in ("password", "secret_key", "access_key"):
            if secret_kw in lower:
                # Only flag if there's a literal string value nearby
                idx = lower.find(secret_kw)
                snippet = content[idx : idx + 80]
                if "=" in snippet and ('"' in snippet or "'" in snippet):
                    findings.append(
                        Finding(
                            message=f"Possible hardcoded secret ({secret_kw}) in {filename}",
                            severity=Severity.CRITICAL,
                            category=Category.SECURITY,
                            resource=filename,
                            suggestion="Use variables or secret manager instead",
                        )
                    )
        return findings

    def _check_best_practices_tf(self, content: str, filename: str) -> list[Finding]:
        findings: list[Finding] = []
        if "terraform {" not in content and filename == "main.tf":
            findings.append(
                Finding(
                    message="No terraform block in main.tf (recommended for version pinning)",
                    severity=Severity.WARNING,
                    category=Category.BEST_PRACTICE,
                    resource=filename,
                    suggestion="Add required_version and required_providers",
                )
            )
        return findings

    def _estimate_cost_tf(self, content: str) -> list[CostEstimate]:
        estimates: list[CostEstimate] = []
        for rtype, cost in _COST_MAP.items():
            if rtype.startswith("aws_") and f'"{rtype}"' in content:
                estimates.append(
                    CostEstimate(
                        resource=rtype,
                        resource_type=rtype,
                        monthly_usd=cost,
                    )
                )
        return estimates

    def _run_policies(self, files: dict[str, str]) -> list[Finding]:
        findings: list[Finding] = []
        for policy in self._policies:
            try:
                result = policy.check(files)
                if result:
                    findings.append(
                        Finding(
                            message=f"Policy '{policy.name}' violation: {result}",
                            severity=policy.severity,
                            category=Category.POLICY,
                        )
                    )
            except Exception:
                findings.append(
                    Finding(
                        message=f"Policy '{policy.name}' check failed",
                        severity=Severity.WARNING,
                        category=Category.POLICY,
                    )
                )
        return findings


# --------------------------------------------------------------------------- #
# Internal types
# --------------------------------------------------------------------------- #

from typing import Callable

_CheckFn = Callable[[dict[str, str]], str | None]


@dataclass(frozen=True)
class _PolicyRule:
    name: str
    check: _CheckFn
    severity: Severity = Severity.ERROR
