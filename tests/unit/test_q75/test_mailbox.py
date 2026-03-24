"""Tests for AgentMailbox — T498."""
from __future__ import annotations
import threading
import pytest
from lidco.agents.mailbox import AgentMailbox, MailMessage


class TestAgentMailbox:
    def test_send_and_receive(self):
        box = AgentMailbox()
        box.send(to="agent_b", from_="agent_a", message="hello")
        msgs = box.receive("agent_b")
        assert len(msgs) == 1
        assert msgs[0].message == "hello"

    def test_receive_empty(self):
        box = AgentMailbox()
        msgs = box.receive("nobody")
        assert msgs == []

    def test_message_fields(self):
        box = AgentMailbox()
        box.send(to="b", from_="a", message="test")
        msg = box.receive("b")[0]
        assert msg.from_ == "a"
        assert msg.to == "b"
        assert msg.timestamp > 0

    def test_broadcast(self):
        box = AgentMailbox()
        box.broadcast(from_="coord", message="start", recipients=["a", "b", "c"])
        for agent in ["a", "b", "c"]:
            msgs = box.receive(agent)
            assert len(msgs) == 1
            assert msgs[0].message == "start"

    def test_pending_count(self):
        box = AgentMailbox()
        box.send(to="x", from_="y", message="1")
        box.send(to="x", from_="y", message="2")
        assert box.pending_count("x") == 2

    def test_clear(self):
        box = AgentMailbox()
        box.send(to="x", from_="y", message="1")
        box.clear("x")
        assert box.pending_count("x") == 0

    def test_thread_safe_concurrent_send(self):
        box = AgentMailbox()
        def sender(n):
            for i in range(10):
                box.send(to="target", from_=f"sender_{n}", message=f"msg_{i}")
        threads = [threading.Thread(target=sender, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        msgs = box.receive("target")
        assert len(msgs) == 50

    def test_mail_message_dataclass(self):
        m = MailMessage(from_="a", to="b", message="hi")
        assert m.from_ == "a"
