"""Tests for Task 464: DriftDetector — spec drift detection."""
import json
import pytest
from pathlib import Path
from unittest.mock import patch
from lidco.spec.drift_detector import DriftDetector, DriftReport
from lidco.spec.writer import SpecDocument


def _write_requirements(project_dir: Path, criteria: list[str] | None = None) -> None:
    spec_dir = project_dir / ".lidco" / "spec"
    spec_dir.mkdir(parents=True, exist_ok=True)
    ac = criteria or [
        "The system shall authenticate users when credentials provided",
        "The system shall return token when login succeeds",
    ]
    doc = SpecDocument(
        title="Auth",
        overview="Authentication system.",
        user_stories=[],
        acceptance_criteria=ac,
        out_of_scope=[],
    )
    (spec_dir / "requirements.md").write_text(doc.to_markdown(), encoding="utf-8")


class TestDriftReport:
    def test_has_drift_true(self):
        r = DriftReport(drifted_criteria=["X"], ok_criteria=[])
        assert r.has_drift is True

    def test_has_drift_false(self):
        r = DriftReport(drifted_criteria=[], ok_criteria=["Y"])
        assert r.has_drift is False

    def test_to_markdown(self):
        r = DriftReport(
            drifted_criteria=["The system shall X"],
            ok_criteria=["The system shall Y"],
            confidence=0.7,
            summary="Test summary.",
        )
        md = r.to_markdown()
        assert "Drifted" in md
        assert "The system shall X" in md
        assert "Test summary" in md


class TestDriftDetectorNoSpec:
    def test_check_returns_report_when_no_spec(self, tmp_path):
        det = DriftDetector()
        report = det.check(tmp_path)
        assert isinstance(report, DriftReport)
        assert "No spec" in report.summary


class TestDriftDetectorHeuristic:
    def test_check_returns_drift_report(self, tmp_path):
        _write_requirements(tmp_path)
        det = DriftDetector()
        with patch.object(det, "_get_recent_diff", return_value=""), \
             patch.object(det, "_get_test_names", return_value=[]):
            report = det.check(tmp_path)
        assert isinstance(report, DriftReport)

    def test_criteria_with_keyword_match_ok(self, tmp_path):
        _write_requirements(tmp_path, ["The system shall authenticate users"])
        det = DriftDetector()
        with patch.object(det, "_get_recent_diff", return_value="authenticate user login credentials"), \
             patch.object(det, "_get_test_names", return_value=["test_authenticate_user"]):
            report = det.check(tmp_path)
        assert len(report.ok_criteria) > 0

    def test_criteria_with_no_match_drifted(self, tmp_path):
        _write_requirements(tmp_path, ["The system shall handle quantum teleportation events"])
        det = DriftDetector()
        with patch.object(det, "_get_recent_diff", return_value="x = 1"), \
             patch.object(det, "_get_test_names", return_value=[]):
            report = det.check(tmp_path)
        # "quantum teleportation" not found in code
        assert len(report.drifted_criteria) > 0

    def test_confidence_is_float(self, tmp_path):
        _write_requirements(tmp_path)
        det = DriftDetector()
        with patch.object(det, "_get_recent_diff", return_value=""), \
             patch.object(det, "_get_test_names", return_value=[]):
            report = det.check(tmp_path)
        assert 0.0 <= report.confidence <= 1.0

    def test_empty_criteria_returns_report(self, tmp_path):
        spec_dir = tmp_path / ".lidco" / "spec"
        spec_dir.mkdir(parents=True)
        doc = SpecDocument(
            title="Empty",
            overview="O",
            user_stories=[],
            acceptance_criteria=[],
            out_of_scope=[],
        )
        (spec_dir / "requirements.md").write_text(doc.to_markdown(), encoding="utf-8")
        det = DriftDetector()
        report = det.check(tmp_path)
        assert isinstance(report, DriftReport)


class TestDriftDetectorLLM:
    def test_llm_check_classifies_criteria(self, tmp_path):
        _write_requirements(tmp_path, [
            "The system shall authenticate users",
            "The system shall send notifications",
        ])

        def fake_llm(messages):
            return json.dumps({"ok": [1], "drifted": [2]})

        det = DriftDetector(llm_client=fake_llm)
        with patch.object(det, "_get_recent_diff", return_value="authenticate"), \
             patch.object(det, "_get_test_names", return_value=[]):
            report = det.check(tmp_path)
        assert len(report.ok_criteria) == 1
        assert len(report.drifted_criteria) == 1

    def test_llm_failure_falls_back_to_heuristic(self, tmp_path):
        _write_requirements(tmp_path)

        def bad_llm(messages):
            raise RuntimeError("LLM unavailable")

        det = DriftDetector(llm_client=bad_llm)
        with patch.object(det, "_get_recent_diff", return_value=""), \
             patch.object(det, "_get_test_names", return_value=[]):
            report = det.check(tmp_path)
        assert isinstance(report, DriftReport)
