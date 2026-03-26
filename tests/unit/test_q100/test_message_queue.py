"""Tests for T633 MessageQueue."""
import pytest

from lidco.messaging.queue import Message, MessageQueue


class TestMessageQueue:
    def _make(self, max_attempts=3):
        return MessageQueue(path=None, max_attempts=max_attempts)

    def test_enqueue_returns_message(self):
        mq = self._make()
        msg = mq.enqueue("topic", {"k": "v"})
        assert isinstance(msg, Message)
        assert len(msg.id) > 0
        assert msg.topic == "topic"

    def test_dequeue_fifo(self):
        mq = self._make()
        m1 = mq.enqueue("t", {"n": 1})
        m2 = mq.enqueue("t", {"n": 2})
        d1 = mq.dequeue("t")
        assert d1.payload == {"n": 1}
        d2 = mq.dequeue("t")
        assert d2.payload == {"n": 2}

    def test_dequeue_empty_returns_none(self):
        mq = self._make()
        assert mq.dequeue("empty") is None

    def test_ack_removes_from_processing(self):
        mq = self._make()
        mq.enqueue("t", {})
        msg = mq.dequeue("t")
        assert mq.ack(msg.id) is True

    def test_ack_unknown_returns_false(self):
        mq = self._make()
        assert mq.ack("nonexistent") is False

    def test_nack_requeues(self):
        mq = self._make(max_attempts=3)
        mq.enqueue("t", {"v": 1})
        msg = mq.dequeue("t")
        assert msg.attempts == 1
        mq.nack(msg.id)
        # Should be back in queue
        requeued = mq.dequeue("t")
        assert requeued is not None
        assert requeued.payload == {"v": 1}
        assert requeued.attempts == 2

    def test_nack_to_dlq_after_max_attempts(self):
        mq = self._make(max_attempts=2)
        mq.enqueue("t", {"v": 1})
        # First attempt
        msg = mq.dequeue("t")
        mq.nack(msg.id)  # attempts=1, re-enqueued
        # Second attempt
        msg2 = mq.dequeue("t")
        mq.nack(msg2.id)  # attempts=2 >= max_attempts, goes to DLQ
        assert len(mq.dead_letters("t")) == 1

    def test_dead_letters_by_topic(self):
        mq = self._make(max_attempts=1)
        mq.enqueue("alpha", {})
        mq.enqueue("beta", {})
        m1 = mq.dequeue("alpha")
        mq.nack(m1.id)
        m2 = mq.dequeue("beta")
        mq.nack(m2.id)
        assert len(mq.dead_letters("alpha")) == 1
        assert len(mq.dead_letters("beta")) == 1
        assert len(mq.dead_letters()) == 2

    def test_list_topics(self):
        mq = self._make()
        mq.enqueue("a", {})
        mq.enqueue("b", {})
        topics = mq.list_topics()
        assert "a" in topics and "b" in topics

    def test_queue_size(self):
        mq = self._make()
        mq.enqueue("x", {})
        mq.enqueue("x", {})
        mq.enqueue("x", {})
        assert mq.queue_size("x") == 3

    def test_clear_specific_topic(self):
        mq = self._make()
        mq.enqueue("a", {})
        mq.enqueue("b", {})
        count = mq.clear("a")
        assert count == 1
        assert mq.queue_size("b") == 1

    def test_clear_all_topics(self):
        mq = self._make()
        mq.enqueue("a", {})
        mq.enqueue("b", {})
        count = mq.clear()
        assert count == 2
