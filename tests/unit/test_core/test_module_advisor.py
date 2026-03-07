"""Tests for module_advisor — ModuleNotFoundError advisor."""

from __future__ import annotations

import pytest

from lidco.core.module_advisor import (
    ModuleAdvice,
    _levenshtein,
    _find_candidates,
    advise_module_not_found,
    format_advice,
)


# ---------------------------------------------------------------------------
# _levenshtein
# ---------------------------------------------------------------------------


class TestLevenshtein:
    def test_identical_strings_zero(self):
        assert _levenshtein("pydantic", "pydantic") == 0

    def test_single_substitution(self):
        assert _levenshtein("abc", "axc") == 1

    def test_single_insertion(self):
        assert _levenshtein("abc", "abcd") == 1

    def test_single_deletion(self):
        assert _levenshtein("abcd", "abc") == 1

    def test_empty_strings(self):
        assert _levenshtein("", "") == 0

    def test_one_empty(self):
        assert _levenshtein("", "abc") == 3
        assert _levenshtein("abc", "") == 3

    def test_completely_different(self):
        dist = _levenshtein("abc", "xyz")
        assert dist == 3

    def test_symmetric(self):
        assert _levenshtein("pydantic", "pydantics") == _levenshtein("pydantics", "pydantic")

    def test_hyphen_underscore(self):
        # scikit-learn vs scikit_learn → 1 substitution
        assert _levenshtein("scikit-learn", "scikit_learn") == 1


# ---------------------------------------------------------------------------
# _find_candidates
# ---------------------------------------------------------------------------


class TestFindCandidates:
    def test_case_insensitive_match(self):
        # "YAML" vs "yaml" should distance 0 after lowering
        packages = ["yaml", "pyyaml"]
        candidates = _find_candidates("YAML", packages)
        assert "yaml" in candidates

    def test_exact_match_first(self):
        packages = ["pydantic", "requests", "flask"]
        candidates = _find_candidates("pydantic", packages)
        assert candidates[0] == "pydantic"

    def test_typo_detected(self):
        packages = ["pydantic", "requests", "flask"]
        candidates = _find_candidates("pydantics", packages)
        assert "pydantic" in candidates

    def test_no_close_match_returns_empty(self):
        packages = ["pydantic", "requests", "flask"]
        candidates = _find_candidates("xyznotreal", packages)
        assert candidates == []

    def test_top_k_limit(self):
        packages = ["pydantic", "pydantics", "pydantic2", "pydantic3", "other"]
        candidates = _find_candidates("pydantic", packages, top_k=2)
        assert len(candidates) <= 2

    def test_empty_known_packages(self):
        candidates = _find_candidates("pydantic", [])
        assert candidates == []

    def test_max_distance_respected(self):
        # "pydantic" vs "requests" — distance >> 3
        packages = ["requests"]
        candidates = _find_candidates("pydantic", packages, max_distance=3)
        assert candidates == []

    def test_distance_zero_with_max_one(self):
        packages = ["pydantic"]
        candidates = _find_candidates("pydantic", packages, max_distance=1)
        assert "pydantic" in candidates


# ---------------------------------------------------------------------------
# advise_module_not_found
# ---------------------------------------------------------------------------


class TestAdviseModuleNotFound:
    def test_stdlib_module_detected(self):
        advice = advise_module_not_found("os", installed_packages=[])
        assert advice is not None
        assert advice.is_stdlib is True
        assert advice.module_name == "os"

    def test_stdlib_json_detected(self):
        advice = advise_module_not_found("json", installed_packages=[])
        assert advice is not None
        assert advice.is_stdlib is True

    def test_known_alias_pil_to_pillow(self):
        advice = advise_module_not_found("PIL", installed_packages=[])
        assert advice is not None
        assert advice.pip_install == "pillow"

    def test_known_alias_pil_lowercase(self):
        # Alias lookup must be case-insensitive
        advice = advise_module_not_found("pil", installed_packages=[])
        assert advice is not None
        assert advice.pip_install == "pillow"

    def test_known_alias_cv2(self):
        advice = advise_module_not_found("cv2", installed_packages=[])
        assert advice is not None
        assert advice.pip_install == "opencv-python"

    def test_known_alias_sklearn(self):
        advice = advise_module_not_found("sklearn", installed_packages=[])
        assert advice is not None
        assert advice.pip_install == "scikit-learn"

    def test_typo_suggestion_from_installed(self):
        advice = advise_module_not_found(
            "pydantics",  # typo
            installed_packages=["pydantic", "requests"],
        )
        assert advice is not None
        assert "pydantic" in advice.candidates

    def test_close_match_sets_pip_install(self):
        advice = advise_module_not_found(
            "pydantics",
            installed_packages=["pydantic", "requests"],
        )
        assert advice is not None
        # pip_install should suggest the closest match
        assert advice.pip_install is not None
        assert "pydantic" in advice.pip_install

    def test_no_match_no_alias_returns_module_name_as_pip(self):
        advice = advise_module_not_found(
            "totally_unknown_pkg",
            installed_packages=[],
        )
        assert advice is not None
        # Falls back to module_name as pip package name
        assert advice.pip_install == "totally_unknown_pkg"

    def test_advice_contains_module_name(self):
        advice = advise_module_not_found("requests", installed_packages=["requests"])
        assert advice is not None
        assert advice.module_name == "requests"

    def test_exact_match_in_installed(self):
        advice = advise_module_not_found(
            "requests",
            installed_packages=["requests", "pydantic"],
        )
        assert advice is not None
        assert "requests" in advice.candidates

    def test_none_installed_uses_live_env(self):
        # When installed_packages=None, uses importlib.metadata — must not raise
        advice = advise_module_not_found("totally_unknown_xyz", installed_packages=None)
        assert advice is not None  # always returns advice (even if no candidates)
        assert advice.module_name == "totally_unknown_xyz"

    def test_submodule_uses_top_level(self):
        # "numpy.linalg" → advisor should look for "numpy"
        advice = advise_module_not_found(
            "numpy.linalg",
            installed_packages=["numpy"],
        )
        assert advice is not None
        assert "numpy" in advice.candidates or advice.pip_install == "numpy"


# ---------------------------------------------------------------------------
# ModuleAdvice dataclass
# ---------------------------------------------------------------------------


class TestModuleAdviceDataclass:
    def test_frozen(self):
        advice = ModuleAdvice(
            module_name="foo",
            candidates=["bar"],
            pip_install="bar",
            is_stdlib=False,
        )
        with pytest.raises((AttributeError, TypeError)):
            advice.module_name = "other"  # type: ignore[misc]

    def test_fields(self):
        advice = ModuleAdvice(
            module_name="PIL",
            candidates=[],
            pip_install="pillow",
            is_stdlib=False,
        )
        assert advice.module_name == "PIL"
        assert advice.pip_install == "pillow"
        assert advice.is_stdlib is False
        assert advice.candidates == []


# ---------------------------------------------------------------------------
# format_advice
# ---------------------------------------------------------------------------


class TestFormatAdvice:
    def test_stdlib_output(self):
        advice = ModuleAdvice(
            module_name="os",
            candidates=[],
            pip_install=None,
            is_stdlib=True,
        )
        result = format_advice(advice)
        assert "os" in result
        assert "stdlib" in result.lower() or "standard" in result.lower() or "built-in" in result.lower()

    def test_alias_output_contains_pip_command(self):
        advice = ModuleAdvice(
            module_name="PIL",
            candidates=[],
            pip_install="pillow",
            is_stdlib=False,
        )
        result = format_advice(advice)
        assert "pillow" in result
        assert "pip install" in result

    def test_candidates_shown(self):
        advice = ModuleAdvice(
            module_name="pydantics",
            candidates=["pydantic"],
            pip_install="pydantic",
            is_stdlib=False,
        )
        result = format_advice(advice)
        assert "pydantic" in result

    def test_no_candidates_no_crash(self):
        advice = ModuleAdvice(
            module_name="mystery",
            candidates=[],
            pip_install="mystery",
            is_stdlib=False,
        )
        result = format_advice(advice)
        assert isinstance(result, str)
        assert "mystery" in result
