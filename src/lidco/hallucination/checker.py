"""FactChecker — verify claims against the codebase."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class Claim:
    """A factual claim extracted from a response."""

    text: str
    claim_type: str  # "file_exists", "function_exists", "import_path", "general"
    target: str = ""  # file path, function name, etc.
    verified: bool | None = None
    confidence: float = 0.5
    evidence: str = ""


@dataclass
class FactCheckResult:
    """Result of fact-checking a response."""

    claims: list[Claim]
    verified_count: int = 0
    failed_count: int = 0
    unchecked_count: int = 0
    overall_confidence: float = 0.5


class FactChecker:
    """Verify claims in AI responses against the codebase."""

    def __init__(self, project_root: str = ".") -> None:
        self._project_root = project_root
        self._results: list[FactCheckResult] = []

    def extract_claims(self, text: str) -> list[Claim]:
        """Extract verifiable claims from response text."""
        claims: list[Claim] = []
        lines = text.split("\n")
        for line in lines:
            stripped = line.strip()
            # Detect file references
            if "/" in stripped or "\\" in stripped:
                for word in stripped.split():
                    clean = word.strip("`\"'(),;:")
                    if ("/" in clean or "\\" in clean) and "." in clean:
                        claims.append(Claim(
                            text=f"File reference: {clean}",
                            claim_type="file_exists",
                            target=clean,
                        ))
            # Detect function references like func() or def func
            if "()" in stripped or stripped.startswith("def "):
                for word in stripped.split():
                    raw = word.strip("`\"',;:")
                    if raw.endswith("()"):
                        fname = raw[:-2]
                        if fname:
                            claims.append(Claim(
                                text=f"Function reference: {fname}",
                                claim_type="function_exists",
                                target=fname,
                            ))
                    elif stripped.startswith("def "):
                        candidate = stripped.split()[1].rstrip("(:") if len(stripped.split()) > 1 else ""
                        if candidate and word.strip("`\"',;:").rstrip("(:") == candidate:
                            claims.append(Claim(
                                text=f"Function reference: {candidate}",
                                claim_type="function_exists",
                                target=candidate,
                            ))
                            break
            # Detect import paths
            if "import " in stripped:
                parts = stripped.split("import ")
                if len(parts) > 1:
                    mod = parts[-1].strip().split()[0].strip(",;")
                    claims.append(Claim(
                        text=f"Import: {mod}",
                        claim_type="import_path",
                        target=mod,
                    ))
        return claims

    def verify_file(self, path: str) -> bool:
        """Check if a file exists in the project."""
        full = os.path.join(self._project_root, path)
        return os.path.isfile(full)

    def verify_claim(self, claim: Claim) -> Claim:
        """Verify a single claim."""
        if claim.claim_type == "file_exists":
            exists = self.verify_file(claim.target)
            return Claim(
                text=claim.text,
                claim_type=claim.claim_type,
                target=claim.target,
                verified=exists,
                confidence=1.0 if exists else 0.0,
                evidence="File found" if exists else "File not found",
            )
        if claim.claim_type == "import_path":
            # Heuristic: convert dotted path to file
            path = claim.target.replace(".", os.sep) + ".py"
            exists = self.verify_file(path)
            return Claim(
                text=claim.text,
                claim_type=claim.claim_type,
                target=claim.target,
                verified=exists,
                confidence=0.9 if exists else 0.2,
                evidence="Module file found" if exists else "Module file not found",
            )
        # General or function_exists — can't verify without search
        return Claim(
            text=claim.text,
            claim_type=claim.claim_type,
            target=claim.target,
            verified=None,
            confidence=0.5,
            evidence="Cannot verify automatically",
        )

    def check(self, text: str) -> FactCheckResult:
        """Extract and verify all claims in a text."""
        claims = self.extract_claims(text)
        verified_claims = [self.verify_claim(c) for c in claims]
        verified_count = sum(1 for c in verified_claims if c.verified is True)
        failed_count = sum(1 for c in verified_claims if c.verified is False)
        unchecked = sum(1 for c in verified_claims if c.verified is None)

        total = len(verified_claims)
        if total > 0:
            confidence = (verified_count + unchecked * 0.5) / total
        else:
            confidence = 1.0

        result = FactCheckResult(
            claims=verified_claims,
            verified_count=verified_count,
            failed_count=failed_count,
            unchecked_count=unchecked,
            overall_confidence=round(confidence, 3),
        )
        self._results.append(result)
        return result

    def history(self) -> list[FactCheckResult]:
        return list(self._results)
