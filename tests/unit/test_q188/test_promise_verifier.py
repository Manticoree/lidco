"""Tests for promise_verifier (task 1054)."""

import pytest
from lidco.autonomous.loop_config import IterationResult
from lidco.autonomous.promise_verifier import (
    HonestyReport,
    PromiseVerifier,
    VerificationResult,
)


@pytest.fixture
def verifier():
    return PromiseVerifier()


# -- verify ---------------------------------------------------------------


def test_verify_promise_present_with_support(verifier):
    output = "All tasks are complete. ALL TESTS PASS. Everything finished successfully."
    result = verifier.verify(output, "ALL TESTS PASS")
    assert result.verified is True
    assert result.confidence > 0.5


def test_verify_promise_absent(verifier):
    output = "Still working on it..."
    result = verifier.verify(output, "ALL TESTS PASS")
    assert result.verified is False
    assert result.confidence == 0.0


def test_verify_promise_present_but_errors(verifier):
    output = "ALL TESTS PASS but ERROR: something failed with exception traceback"
    result = verifier.verify(output, "ALL TESTS PASS")
    # Confidence should be low due to error signals
    assert result.confidence < 0.8


def test_verify_case_insensitive(verifier):
    output = "all tests pass and done"
    result = verifier.verify(output, "ALL TESTS PASS")
    assert result.verified is True


def test_verify_returns_verification_result(verifier):
    result = verifier.verify("x", "y")
    assert isinstance(result, VerificationResult)


def test_verify_evidence_string_nonempty(verifier):
    result = verifier.verify("ALL TESTS PASS done", "ALL TESTS PASS")
    assert len(result.evidence) > 0


def test_verify_confidence_range(verifier):
    result = verifier.verify("ALL TESTS PASS completed successfully finished done", "ALL TESTS PASS")
    assert 0.0 <= result.confidence <= 1.0


# -- extract_claims -------------------------------------------------------


def test_extract_claims_finds_completion(verifier):
    output = "Step 1 done. All tasks complete. Moving on."
    claims = verifier.extract_claims(output)
    assert len(claims) >= 1
    assert any("done" in c.lower() or "complete" in c.lower() for c in claims)


def test_extract_claims_empty_for_no_claims(verifier):
    output = "Working on iteration 3. Still processing."
    claims = verifier.extract_claims(output)
    assert isinstance(claims, list)
    # "Working" and "processing" don't match completion patterns
    assert len(claims) == 0


def test_extract_claims_multiple(verifier):
    output = "Task completed. Everything is done. All items finished."
    claims = verifier.extract_claims(output)
    assert len(claims) >= 2


def test_extract_claims_empty_string(verifier):
    assert verifier.extract_claims("") == []


# -- check_honesty -------------------------------------------------------


def _make_iter(i: int, output: str = "ok", claimed: bool = False) -> IterationResult:
    return IterationResult(iteration=i, output=output, duration_ms=10, claimed_complete=claimed)


def test_honesty_clean_history(verifier):
    iters = [_make_iter(1, "step 1"), _make_iter(2, "step 2"), _make_iter(3, "step 3", claimed=True)]
    report = verifier.check_honesty(iters)
    assert report.honest is True
    assert len(report.flags) == 0


def test_honesty_premature_claim(verifier):
    iters = [_make_iter(1, claimed=True)]
    report = verifier.check_honesty(iters)
    assert "premature_claim" in report.flags
    assert report.honest is False


def test_honesty_flip_flop(verifier):
    iters = [
        _make_iter(1, claimed=True),
        _make_iter(2, claimed=False),
        _make_iter(3, claimed=True),
        _make_iter(4, claimed=False),
        _make_iter(5, claimed=True),
    ]
    report = verifier.check_honesty(iters)
    assert "flip_flop" in report.flags


def test_honesty_stuck_loop(verifier):
    iters = [
        _make_iter(1, output="same"),
        _make_iter(2, output="same"),
        _make_iter(3, output="same"),
    ]
    report = verifier.check_honesty(iters)
    assert "stuck_loop" in report.flags


def test_honesty_persistent_error(verifier):
    iters = [
        _make_iter(1, output="ERROR: fail1"),
        _make_iter(2, output="ERROR: fail2"),
        _make_iter(3, output="ERROR: fail3"),
    ]
    report = verifier.check_honesty(iters)
    assert "persistent_error" in report.flags


def test_honesty_empty_iterations(verifier):
    report = verifier.check_honesty([])
    assert report.honest is True


def test_honesty_report_has_recommendation(verifier):
    iters = [_make_iter(1, output="same"), _make_iter(2, output="same"), _make_iter(3, output="same")]
    report = verifier.check_honesty(iters)
    assert isinstance(report.recommendation, str)
    assert len(report.recommendation) > 0


def test_honesty_report_is_frozen():
    report = HonestyReport(honest=True, flags=(), recommendation="ok")
    with pytest.raises(AttributeError):
        report.honest = False  # type: ignore[misc]


# -- __all__ ---------------------------------------------------------------


def test_all_exports():
    from lidco.autonomous import promise_verifier
    assert "PromiseVerifier" in promise_verifier.__all__
    assert "VerificationResult" in promise_verifier.__all__
    assert "HonestyReport" in promise_verifier.__all__
