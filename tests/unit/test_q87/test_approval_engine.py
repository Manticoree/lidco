"""Tests for ApprovalEngine (T570)."""
from __future__ import annotations
import pytest
from lidco.review.approval_engine import (
    ApprovalEngine, ApprovalRule, parse_diff_stats, _has_secrets
)

SMALL_DIFF = """\
--- a/mod.py
+++ b/mod.py
@@ -1,3 +1,4 @@
 def foo():
-    pass
+    return 42
+    # fixed
"""

BIG_DIFF = "+" + "\n+".join(["x = 1"] * 100)

SECRET_DIFF = """\
+++ b/config.py
+api_key = 'sk-abc123xyz789verylongkey'
"""


def test_parse_diff_stats_small():
    stats = parse_diff_stats(SMALL_DIFF)
    assert stats.lines_added >= 1
    assert stats.lines_removed >= 1
    assert "mod.py" in stats.files_changed


def test_has_secrets_detected():
    assert _has_secrets(SECRET_DIFF) is True


def test_has_secrets_clean():
    assert _has_secrets(SMALL_DIFF) is False


def test_small_diff_approved():
    engine = ApprovalEngine()
    engine.load_defaults()
    assert engine.is_auto_approvable(SMALL_DIFF) is True


def test_big_diff_blocked():
    engine = ApprovalEngine()
    engine.load_defaults()
    assert engine.is_auto_approvable(BIG_DIFF) is False


def test_secret_blocked():
    engine = ApprovalEngine()
    engine.load_defaults()
    assert engine.is_auto_approvable(SECRET_DIFF) is False


def test_evaluate_returns_reasons():
    engine = ApprovalEngine()
    rule = ApprovalRule(name="test", description="test", max_lines_changed=5)
    decision = engine.evaluate(BIG_DIFF, rule)
    assert not decision.approved
    assert len(decision.reasons) > 0


def test_docs_only_rule():
    engine = ApprovalEngine()
    engine.load_defaults()
    docs_diff = "+++ b/README.md\n+# New section\n"
    decisions = engine.evaluate_all(docs_diff)
    docs_decision = next((d for d in decisions if d.rule_name == "docs-only"), None)
    assert docs_decision is not None and docs_decision.approved


def test_format_decision():
    engine = ApprovalEngine()
    rule = ApprovalRule(name="r", description="d")
    d = engine.evaluate(SMALL_DIFF, rule)
    fmt = d.format()
    assert "APPROVED" in fmt or "BLOCKED" in fmt
