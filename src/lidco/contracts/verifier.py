"""Contract Verifier — verify providers against contracts.

Checks that a provider implementation satisfies the contract, validates
backward compatibility between contract versions, and supports mock consumers.
"""

from __future__ import annotations

import copy
import enum
from dataclasses import dataclass, field
from typing import Any, Callable

from lidco.contracts.definitions import (
    ContractDefinition,
    EndpointSchema,
    FieldSchema,
    FieldType,
)


class Severity(enum.Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True)
class VerificationIssue:
    """A single verification issue."""

    endpoint: str
    message: str
    severity: Severity = Severity.ERROR
    field_name: str = ""

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "endpoint": self.endpoint,
            "message": self.message,
            "severity": self.severity.value,
        }
        if self.field_name:
            d["field_name"] = self.field_name
        return d


@dataclass(frozen=True)
class VerificationResult:
    """Result of contract verification."""

    contract_name: str
    contract_version: str
    passed: bool
    issues: tuple[VerificationIssue, ...] = ()
    endpoints_checked: int = 0

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.WARNING)

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_name": self.contract_name,
            "contract_version": self.contract_version,
            "passed": self.passed,
            "endpoints_checked": self.endpoints_checked,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "issues": [i.to_dict() for i in self.issues],
        }


# -- Provider implementation descriptor -----------------------------------

@dataclass(frozen=True)
class ProviderEndpoint:
    """Describes one endpoint the provider actually exposes."""

    method: str
    path: str
    request_fields: tuple[str, ...] = ()
    response_fields: tuple[str, ...] = ()
    status_code: int = 200


@dataclass(frozen=True)
class ProviderSpec:
    """Describes the full set of endpoints a provider exposes."""

    name: str
    endpoints: tuple[ProviderEndpoint, ...] = ()


# -- Verifier -------------------------------------------------------------

def _type_compatible(expected: FieldType, actual_value: Any) -> bool:
    """Check if a value is compatible with the expected field type."""
    mapping: dict[FieldType, type | tuple[type, ...]] = {
        FieldType.STRING: str,
        FieldType.INTEGER: int,
        FieldType.FLOAT: (int, float),
        FieldType.BOOLEAN: bool,
        FieldType.ARRAY: (list, tuple),
        FieldType.OBJECT: dict,
    }
    if expected in (FieldType.ANY, FieldType.NULL):
        return True
    return isinstance(actual_value, mapping.get(expected, object))


class ContractVerifier:
    """Verify a provider implementation against a contract."""

    def verify(
        self,
        contract: ContractDefinition,
        provider: ProviderSpec,
    ) -> VerificationResult:
        """Check every endpoint in the contract against the provider."""
        issues: list[VerificationIssue] = []
        checked = 0

        provider_map: dict[tuple[str, str], ProviderEndpoint] = {
            (ep.method.upper(), ep.path): ep for ep in provider.endpoints
        }

        for ep in contract.endpoints:
            checked += 1
            key = (ep.method.upper(), ep.path)
            pep = provider_map.get(key)

            if pep is None:
                issues.append(VerificationIssue(
                    endpoint=f"{ep.method} {ep.path}",
                    message="Endpoint not implemented by provider",
                ))
                continue

            if pep.status_code != ep.status_code:
                issues.append(VerificationIssue(
                    endpoint=f"{ep.method} {ep.path}",
                    message=(
                        f"Status code mismatch: expected {ep.status_code}, "
                        f"got {pep.status_code}"
                    ),
                    severity=Severity.WARNING,
                ))

            pep_resp_set = set(pep.response_fields)
            for rf in ep.response_fields:
                if rf.required and rf.name not in pep_resp_set:
                    issues.append(VerificationIssue(
                        endpoint=f"{ep.method} {ep.path}",
                        message=f"Required response field '{rf.name}' missing",
                        field_name=rf.name,
                    ))

        passed = all(i.severity != Severity.ERROR for i in issues)
        return VerificationResult(
            contract_name=contract.name,
            contract_version=contract.version,
            passed=passed,
            issues=tuple(issues),
            endpoints_checked=checked,
        )

    def check_backward_compatibility(
        self,
        old: ContractDefinition,
        new: ContractDefinition,
    ) -> VerificationResult:
        """Check that *new* is backward-compatible with *old*.

        Rules:
        - All old endpoints must still exist in new.
        - All required old response fields must still exist in new.
        - New required request fields are a breaking change.
        """
        issues: list[VerificationIssue] = []
        checked = 0

        new_ep_map: dict[tuple[str, str], EndpointSchema] = {
            (ep.method.upper(), ep.path): ep for ep in new.endpoints
        }

        for ep in old.endpoints:
            checked += 1
            key = (ep.method.upper(), ep.path)
            nep = new_ep_map.get(key)

            if nep is None:
                issues.append(VerificationIssue(
                    endpoint=f"{ep.method} {ep.path}",
                    message="Endpoint removed in new version",
                ))
                continue

            new_resp_names = {f.name for f in nep.response_fields}
            for rf in ep.response_fields:
                if rf.required and rf.name not in new_resp_names:
                    issues.append(VerificationIssue(
                        endpoint=f"{ep.method} {ep.path}",
                        message=f"Required response field '{rf.name}' removed",
                        field_name=rf.name,
                    ))

            old_req_names = {f.name for f in ep.request_fields}
            for nf in nep.request_fields:
                if nf.required and nf.name not in old_req_names:
                    issues.append(VerificationIssue(
                        endpoint=f"{ep.method} {ep.path}",
                        message=f"New required request field '{nf.name}' added",
                        field_name=nf.name,
                        severity=Severity.WARNING,
                    ))

        passed = all(i.severity != Severity.ERROR for i in issues)
        return VerificationResult(
            contract_name=new.name,
            contract_version=new.version,
            passed=passed,
            issues=tuple(issues),
            endpoints_checked=checked,
        )

    def mock_consumer(
        self,
        contract: ContractDefinition,
    ) -> dict[str, dict[str, Any]]:
        """Generate mock responses for each endpoint based on the contract.

        Returns a mapping of ``"METHOD /path"`` to mock response dicts.
        """
        mocks: dict[str, dict[str, Any]] = {}
        for ep in contract.endpoints:
            key = f"{ep.method.upper()} {ep.path}"
            mocks[key] = {
                "status_code": ep.status_code,
                "body": {f.name: _mock_value(f) for f in ep.response_fields},
            }
        return mocks


def _mock_value(f: FieldSchema) -> Any:
    """Generate a mock value for a field."""
    if f.default is not None:
        return copy.deepcopy(f.default)
    defaults: dict[FieldType, Any] = {
        FieldType.STRING: "",
        FieldType.INTEGER: 0,
        FieldType.FLOAT: 0.0,
        FieldType.BOOLEAN: False,
        FieldType.ARRAY: [],
        FieldType.OBJECT: {},
        FieldType.NULL: None,
        FieldType.ANY: None,
    }
    return defaults.get(f.field_type)
