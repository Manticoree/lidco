"""Tests for src/lidco/versioning/semver.py."""
import pytest

from lidco.versioning.semver import (
    SemVerError, Version, VersionRange,
    compare, latest, parse, satisfies, sort_versions,
)


class TestVersionParse:
    def test_basic(self):
        v = Version.parse("1.2.3")
        assert (v.major, v.minor, v.patch) == (1, 2, 3)

    def test_with_pre(self):
        v = Version.parse("1.0.0-alpha.1")
        assert v.pre == "alpha.1"

    def test_with_build(self):
        v = Version.parse("1.0.0+build.1")
        assert v.build == "build.1"

    def test_with_pre_and_build(self):
        v = Version.parse("1.0.0-rc.1+build.5")
        assert v.pre == "rc.1"
        assert v.build == "build.5"

    def test_v_prefix_stripped(self):
        v = Version.parse("v1.2.3")
        assert str(v) == "1.2.3"

    def test_invalid_raises(self):
        with pytest.raises(SemVerError):
            Version.parse("not_a_version")

    def test_parse_loose_missing_patch(self):
        v = Version.parse_loose("1.2")
        assert v.patch == 0

    def test_parse_loose_missing_minor_patch(self):
        v = Version.parse_loose("1")
        assert v.minor == 0
        assert v.patch == 0

    def test_from_tuple(self):
        v = Version.from_tuple((2, 3, 4))
        assert (v.major, v.minor, v.patch) == (2, 3, 4)

    def test_from_tuple_too_short(self):
        with pytest.raises(SemVerError):
            Version.from_tuple((1, 2))

    def test_str(self):
        assert str(Version.parse("1.2.3")) == "1.2.3"
        assert str(Version.parse("1.0.0-alpha")) == "1.0.0-alpha"


class TestVersionComparison:
    def test_equal(self):
        assert Version.parse("1.2.3") == Version.parse("1.2.3")

    def test_less_than(self):
        assert Version.parse("1.0.0") < Version.parse("2.0.0")

    def test_less_than_minor(self):
        assert Version.parse("1.1.0") < Version.parse("1.2.0")

    def test_less_than_patch(self):
        assert Version.parse("1.0.0") < Version.parse("1.0.1")

    def test_pre_less_than_release(self):
        assert Version.parse("1.0.0-alpha") < Version.parse("1.0.0")

    def test_sorted(self):
        versions = [Version.parse(v) for v in ["2.0.0", "1.0.0", "1.2.3"]]
        assert sorted(versions)[0] == Version.parse("1.0.0")

    def test_not_equal_different_pre(self):
        assert Version.parse("1.0.0-alpha") != Version.parse("1.0.0-beta")

    def test_hash_equal(self):
        assert hash(Version.parse("1.2.3")) == hash(Version.parse("1.2.3"))


class TestVersionBump:
    def test_bump_major(self):
        assert str(Version.parse("1.2.3").bump_major()) == "2.0.0"

    def test_bump_minor(self):
        assert str(Version.parse("1.2.3").bump_minor()) == "1.3.0"

    def test_bump_patch(self):
        assert str(Version.parse("1.2.3").bump_patch()) == "1.2.4"

    def test_bump_clears_pre(self):
        v = Version.parse("1.2.3-alpha").bump_patch()
        assert v.pre == ""

    def test_with_pre(self):
        v = Version.parse("1.0.0").with_pre("rc.1")
        assert v.pre == "rc.1"

    def test_release_strips_pre(self):
        v = Version.parse("1.0.0-beta").release()
        assert not v.pre

    def test_next_versions_keys(self):
        nexts = Version.parse("1.0.0").next_versions()
        assert set(nexts.keys()) == {"major", "minor", "patch"}


class TestVersionPredicates:
    def test_is_stable_true(self):
        assert Version.parse("1.0.0").is_stable() is True

    def test_is_stable_false_prerelease(self):
        assert Version.parse("1.0.0-alpha").is_stable() is False

    def test_is_stable_false_zero_major(self):
        assert Version.parse("0.9.0").is_stable() is False

    def test_is_prerelease_true(self):
        assert Version.parse("1.0.0-rc.1").is_prerelease() is True

    def test_is_prerelease_false(self):
        assert Version.parse("1.0.0").is_prerelease() is False

    def test_is_compatible_with(self):
        assert Version.parse("1.2.3").is_compatible_with(Version.parse("1.0.0"))
        assert not Version.parse("2.0.0").is_compatible_with(Version.parse("1.0.0"))

    def test_as_tuple(self):
        assert Version.parse("3.1.4").as_tuple() == (3, 1, 4)


class TestVersionRange:
    def test_wildcard(self):
        r = VersionRange("*")
        assert r.satisfies("1.0.0")
        assert r.satisfies("99.0.0")

    def test_caret_same_major(self):
        r = VersionRange("^1.2.0")
        assert r.satisfies("1.2.0")
        assert r.satisfies("1.9.9")
        assert not r.satisfies("2.0.0")

    def test_tilde_same_minor(self):
        r = VersionRange("~1.2.0")
        assert r.satisfies("1.2.0")
        assert r.satisfies("1.2.9")
        assert not r.satisfies("1.3.0")

    def test_gte(self):
        r = VersionRange(">=1.5.0")
        assert r.satisfies("1.5.0")
        assert r.satisfies("2.0.0")
        assert not r.satisfies("1.4.9")

    def test_lt(self):
        r = VersionRange("<2.0.0")
        assert r.satisfies("1.9.9")
        assert not r.satisfies("2.0.0")

    def test_exact(self):
        r = VersionRange("=1.2.3")
        assert r.satisfies("1.2.3")
        assert not r.satisfies("1.2.4")

    def test_filter(self):
        versions = [Version.parse(v) for v in ["1.0.0", "1.5.0", "2.0.0"]]
        r = VersionRange("^1.0.0")
        filtered = r.filter(versions)
        assert all(v.major == 1 for v in filtered)

    def test_max_satisfying(self):
        versions = [Version.parse(v) for v in ["1.0.0", "1.5.0", "2.0.0"]]
        r = VersionRange("^1.0.0")
        assert str(r.max_satisfying(versions)) == "1.5.0"

    def test_max_satisfying_none(self):
        r = VersionRange("^3.0.0")
        versions = [Version.parse("1.0.0")]
        assert r.max_satisfying(versions) is None


class TestConvenienceFunctions:
    def test_parse_fn(self):
        assert str(parse("1.2.3")) == "1.2.3"

    def test_compare_less(self):
        assert compare("1.0.0", "2.0.0") == -1

    def test_compare_equal(self):
        assert compare("1.0.0", "1.0.0") == 0

    def test_compare_greater(self):
        assert compare("2.0.0", "1.0.0") == 1

    def test_sort_versions(self):
        result = sort_versions(["2.0.0", "1.0.0", "1.5.0"])
        assert result == ["1.0.0", "1.5.0", "2.0.0"]

    def test_sort_reverse(self):
        result = sort_versions(["1.0.0", "2.0.0"], reverse=True)
        assert result[0] == "2.0.0"

    def test_latest(self):
        assert latest(["1.0.0", "2.0.0", "1.5.0"]) == "2.0.0"

    def test_latest_empty(self):
        assert latest([]) is None

    def test_latest_stable_only(self):
        result = latest(["1.0.0", "2.0.0-alpha", "1.5.0"], stable_only=True)
        assert result in ("1.5.0", "1.0.0")

    def test_satisfies(self):
        assert satisfies("1.2.3", "^1.0.0") is True
        assert satisfies("2.0.0", "^1.0.0") is False
