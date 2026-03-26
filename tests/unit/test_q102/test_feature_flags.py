"""Tests for src/lidco/features/flags.py — FeatureFlags."""
import pytest
from lidco.features.flags import FeatureFlags, FlagConfig, FeatureFlagNotFoundError


class TestFeatureFlagsBasic:
    def setup_method(self):
        self.flags = FeatureFlags(path=None)

    def test_define_and_check(self):
        self.flags.define("my_flag", enabled=True, rollout=100.0)
        assert self.flags.is_enabled("my_flag") is True

    def test_disabled_flag(self):
        self.flags.define("off_flag", enabled=False, rollout=100.0)
        assert self.flags.is_enabled("off_flag") is False

    def test_missing_flag_returns_false(self):
        assert self.flags.is_enabled("nonexistent") is False

    def test_zero_rollout_disabled(self):
        self.flags.define("pct_flag", enabled=True, rollout=0.0)
        assert self.flags.is_enabled("pct_flag", "user1") is False

    def test_full_rollout_enabled(self):
        self.flags.define("full_flag", enabled=True, rollout=100.0)
        assert self.flags.is_enabled("full_flag", "anyuser") is True

    def test_allowlist_overrides_rollout(self):
        self.flags.define("allow_flag", enabled=True, rollout=0.0,
                          allowlist=["vip_user"])
        assert self.flags.is_enabled("allow_flag", "vip_user") is True

    def test_denylist_overrides_rollout(self):
        self.flags.define("deny_flag", enabled=True, rollout=100.0,
                          denylist=["banned"])
        assert self.flags.is_enabled("deny_flag", "banned") is False

    def test_denylist_checked_before_allowlist(self):
        # denylist takes priority
        self.flags.define("combo_flag", enabled=True, rollout=100.0,
                          allowlist=["user"], denylist=["user"])
        assert self.flags.is_enabled("combo_flag", "user") is False

    def test_remove_flag(self):
        self.flags.define("temp", enabled=True)
        self.flags.remove("temp")
        assert self.flags.is_enabled("temp") is False

    def test_remove_nonexistent(self):
        assert self.flags.remove("nope") is False

    def test_list_flags(self):
        self.flags.define("b_flag", enabled=True)
        self.flags.define("a_flag", enabled=True)
        names = self.flags.list_flags()
        assert names == ["a_flag", "b_flag"]

    def test_get_config(self):
        self.flags.define("cfg_flag", enabled=True, rollout=50.0)
        cfg = self.flags.get_config("cfg_flag")
        assert isinstance(cfg, FlagConfig)
        assert cfg.rollout == 50.0

    def test_get_config_missing_raises(self):
        with pytest.raises(FeatureFlagNotFoundError) as exc:
            self.flags.get_config("nope")
        assert exc.value.flag_name == "nope"

    def test_len(self):
        assert len(self.flags) == 0
        self.flags.define("f1", enabled=True)
        assert len(self.flags) == 1

    def test_contains(self):
        self.flags.define("f1", enabled=True)
        assert "f1" in self.flags
        assert "f2" not in self.flags


class TestFeatureFlagsRollout:
    def test_rollout_deterministic(self):
        flags = FeatureFlags(path=None)
        flags.define("det_flag", enabled=True, rollout=50.0)
        result1 = flags.is_enabled("det_flag", "stable_user")
        result2 = flags.is_enabled("det_flag", "stable_user")
        assert result1 == result2

    def test_hash_bucket_range(self):
        bucket = FeatureFlags._hash_bucket("flag", "user")
        assert 0.0 <= bucket < 100.0

    def test_rollout_clamp_over_100(self):
        flags = FeatureFlags(path=None)
        cfg = flags.define("over", enabled=True, rollout=150.0)
        assert cfg.rollout == 100.0

    def test_rollout_clamp_negative(self):
        flags = FeatureFlags(path=None)
        cfg = flags.define("neg", enabled=True, rollout=-10.0)
        assert cfg.rollout == 0.0


class TestFeatureFlagsPersistence:
    def test_save_and_reload(self, tmp_path):
        path = tmp_path / "flags.json"
        flags1 = FeatureFlags(path=path)
        flags1.define("persist_flag", enabled=True, rollout=75.0)

        flags2 = FeatureFlags(path=path)
        assert "persist_flag" in flags2
        cfg = flags2.get_config("persist_flag")
        assert cfg.rollout == 75.0

    def test_reload_method(self, tmp_path):
        path = tmp_path / "flags.json"
        flags1 = FeatureFlags(path=path)
        flags1.define("flag_a", enabled=True)

        flags2 = FeatureFlags(path=path)
        flags1.define("flag_b", enabled=True)

        flags2.reload()
        assert "flag_b" in flags2


class TestFeatureFlagDecorator:
    def test_decorator_calls_fn_when_enabled(self):
        flags = FeatureFlags(path=None)
        flags.define("feat", enabled=True, rollout=100.0)

        @flags.feature_flag("feat", identifier="user1")
        def my_func():
            return "executed"

        assert my_func() == "executed"

    def test_decorator_returns_default_when_disabled(self):
        flags = FeatureFlags(path=None)
        flags.define("feat", enabled=False)

        @flags.feature_flag("feat", identifier="user1", default="fallback")
        def my_func():
            return "executed"

        assert my_func() == "fallback"

    def test_decorator_missing_flag(self):
        flags = FeatureFlags(path=None)

        @flags.feature_flag("not_defined", default="nope")
        def fn():
            return "called"

        assert fn() == "nope"
