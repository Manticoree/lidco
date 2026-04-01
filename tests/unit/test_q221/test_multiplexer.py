"""Tests for lidco.streaming.fanout_multiplexer."""
from __future__ import annotations

from lidco.streaming.fanout_multiplexer import FanOutMultiplexer, OutputTarget, TargetConfig


class TestTargetConfig:
    def test_frozen(self) -> None:
        cfg = TargetConfig(name="t", target_type=OutputTarget.TERMINAL)
        try:
            cfg.name = "x"  # type: ignore[misc]
            assert False, "should be frozen"
        except AttributeError:
            pass

    def test_defaults(self) -> None:
        cfg = TargetConfig(name="t", target_type=OutputTarget.FILE)
        assert cfg.destination == ""
        assert cfg.active is True


class TestFanOutMultiplexer:
    def test_add_and_get_targets(self) -> None:
        mux = FanOutMultiplexer()
        cfg = mux.add_target("term", OutputTarget.TERMINAL)
        assert cfg.name == "term"
        assert len(mux.get_targets()) == 1

    def test_remove_target(self) -> None:
        mux = FanOutMultiplexer()
        mux.add_target("f", OutputTarget.FILE, "/tmp/out")
        assert mux.remove_target("f") is True
        assert mux.remove_target("f") is False
        assert mux.get_targets() == []

    def test_send_all(self) -> None:
        mux = FanOutMultiplexer()
        mux.add_target("a", OutputTarget.TERMINAL)
        mux.add_target("b", OutputTarget.WEBSOCKET)
        count = mux.send("hello")
        assert count == 2

    def test_send_specific_target(self) -> None:
        mux = FanOutMultiplexer()
        mux.add_target("a", OutputTarget.TERMINAL)
        mux.add_target("b", OutputTarget.FILE)
        count = mux.send("msg", target_name="a")
        assert count == 1

    def test_send_unknown_target(self) -> None:
        mux = FanOutMultiplexer()
        assert mux.send("msg", target_name="nope") == 0

    def test_buffer(self) -> None:
        mux = FanOutMultiplexer()
        mux.add_target("t", OutputTarget.TERMINAL)
        mux.send("e1")
        mux.send("e2")
        assert mux.get_buffer() == ["e1", "e2"]

    def test_pause_resume(self) -> None:
        mux = FanOutMultiplexer()
        mux.add_target("t", OutputTarget.TERMINAL)
        assert mux.pause_target("t") is True
        assert mux.send("msg") == 0  # paused
        assert mux.resume_target("t") is True
        assert mux.send("msg2") == 1

    def test_pause_unknown(self) -> None:
        mux = FanOutMultiplexer()
        assert mux.pause_target("x") is False
        assert mux.resume_target("x") is False

    def test_stats(self) -> None:
        mux = FanOutMultiplexer()
        mux.add_target("t", OutputTarget.TERMINAL)
        mux.send("a")
        mux.send("b")
        assert mux.stats()["t"] == 2

    def test_summary(self) -> None:
        mux = FanOutMultiplexer()
        mux.add_target("t", OutputTarget.TERMINAL)
        s = mux.summary()
        assert "1 targets" in s
        assert "t" in s
