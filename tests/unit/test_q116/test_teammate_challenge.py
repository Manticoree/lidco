"""Tests for TeammateChallengeProtocol (Task 715)."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from lidco.agents.teammate_challenge import (
    ChallengeLog,
    ChallengeProtocol,
    ChallengeRequest,
    ChallengeResponse,
)


class TestChallengeRequest(unittest.TestCase):
    def test_create(self):
        req = ChallengeRequest(id="abc", challenger="a", target="b", finding="bug")
        self.assertEqual(req.id, "abc")
        self.assertEqual(req.challenger, "a")
        self.assertEqual(req.target, "b")
        self.assertEqual(req.finding, "bug")

    def test_defaults(self):
        req = ChallengeRequest(id="x", challenger="a", target="b", finding="f")
        self.assertEqual(req.rationale, "")
        self.assertEqual(req.created_at, "")


class TestChallengeResponse(unittest.TestCase):
    def test_create_accepted(self):
        resp = ChallengeResponse(request_id="x", responder="b", accepted=True)
        self.assertTrue(resp.accepted)

    def test_create_rejected(self):
        resp = ChallengeResponse(request_id="x", responder="b", accepted=False, counter="no way")
        self.assertFalse(resp.accepted)
        self.assertEqual(resp.counter, "no way")


class TestChallengeLog(unittest.TestCase):
    def test_empty_log(self):
        log = ChallengeLog()
        self.assertEqual(log.accepted_count, 0)
        self.assertEqual(log.rejected_count, 0)
        self.assertEqual(log.pending_count, 0)

    def test_pending_count(self):
        req = ChallengeRequest(id="1", challenger="a", target="b", finding="f")
        log = ChallengeLog(entries=[(req, None)])
        self.assertEqual(log.pending_count, 1)

    def test_accepted_count(self):
        req = ChallengeRequest(id="1", challenger="a", target="b", finding="f")
        resp = ChallengeResponse(request_id="1", responder="b", accepted=True)
        log = ChallengeLog(entries=[(req, resp)])
        self.assertEqual(log.accepted_count, 1)
        self.assertEqual(log.rejected_count, 0)

    def test_rejected_count(self):
        req = ChallengeRequest(id="1", challenger="a", target="b", finding="f")
        resp = ChallengeResponse(request_id="1", responder="b", accepted=False)
        log = ChallengeLog(entries=[(req, resp)])
        self.assertEqual(log.rejected_count, 1)

    def test_mixed_counts(self):
        r1 = ChallengeRequest(id="1", challenger="a", target="b", finding="f1")
        r2 = ChallengeRequest(id="2", challenger="a", target="b", finding="f2")
        r3 = ChallengeRequest(id="3", challenger="a", target="b", finding="f3")
        resp1 = ChallengeResponse(request_id="1", responder="b", accepted=True)
        resp2 = ChallengeResponse(request_id="2", responder="b", accepted=False)
        log = ChallengeLog(entries=[(r1, resp1), (r2, resp2), (r3, None)])
        self.assertEqual(log.accepted_count, 1)
        self.assertEqual(log.rejected_count, 1)
        self.assertEqual(log.pending_count, 1)


class TestChallengeProtocol(unittest.TestCase):
    def test_init_no_mailbox(self):
        cp = ChallengeProtocol()
        self.assertIsNotNone(cp)

    def test_issue_returns_request(self):
        cp = ChallengeProtocol()
        req = cp.issue("alice", "bob", "wrong logic")
        self.assertIsInstance(req, ChallengeRequest)
        self.assertEqual(req.challenger, "alice")
        self.assertEqual(req.target, "bob")
        self.assertEqual(req.finding, "wrong logic")

    def test_issue_sets_id(self):
        cp = ChallengeProtocol()
        req = cp.issue("a", "b", "f")
        self.assertTrue(len(req.id) > 0)

    def test_issue_sets_created_at(self):
        cp = ChallengeProtocol()
        req = cp.issue("a", "b", "f")
        self.assertTrue(len(req.created_at) > 0)

    def test_issue_with_rationale(self):
        cp = ChallengeProtocol()
        req = cp.issue("a", "b", "f", rationale="because")
        self.assertEqual(req.rationale, "because")

    def test_issue_sends_mailbox_message(self):
        mb = MagicMock()
        cp = ChallengeProtocol(mailbox=mb)
        cp.issue("a", "b", "finding")
        mb.send.assert_called_once()
        call_kwargs = mb.send.call_args
        self.assertEqual(call_kwargs.kwargs.get("to") or call_kwargs[1].get("to", call_kwargs[0][0] if call_kwargs[0] else None), "b")

    def test_issue_no_mailbox_no_crash(self):
        cp = ChallengeProtocol()
        req = cp.issue("a", "b", "f")
        self.assertIsNotNone(req)

    def test_respond_returns_response(self):
        cp = ChallengeProtocol()
        req = cp.issue("a", "b", "f")
        resp = cp.respond("b", req.id, True)
        self.assertIsInstance(resp, ChallengeResponse)
        self.assertTrue(resp.accepted)

    def test_respond_rejected(self):
        cp = ChallengeProtocol()
        req = cp.issue("a", "b", "f")
        resp = cp.respond("b", req.id, False, counter="disagree")
        self.assertFalse(resp.accepted)
        self.assertEqual(resp.counter, "disagree")

    def test_respond_updates_log(self):
        cp = ChallengeProtocol()
        req = cp.issue("a", "b", "f")
        cp.respond("b", req.id, True)
        log = cp.get_log()
        self.assertEqual(log.accepted_count, 1)
        self.assertEqual(log.pending_count, 0)

    def test_respond_sends_mailbox_reply(self):
        mb = MagicMock()
        cp = ChallengeProtocol(mailbox=mb)
        req = cp.issue("alice", "bob", "bug")
        cp.respond("bob", req.id, False, counter="nah")
        # Two calls: one for issue, one for respond
        self.assertEqual(mb.send.call_count, 2)

    def test_get_log_empty(self):
        cp = ChallengeProtocol()
        log = cp.get_log()
        self.assertEqual(len(log.entries), 0)

    def test_get_log_after_issues(self):
        cp = ChallengeProtocol()
        cp.issue("a", "b", "f1")
        cp.issue("a", "b", "f2")
        log = cp.get_log()
        self.assertEqual(len(log.entries), 2)

    def test_get_pending(self):
        cp = ChallengeProtocol()
        cp.issue("a", "bob", "f1")
        cp.issue("a", "bob", "f2")
        pending = cp.get_pending("bob")
        self.assertEqual(len(pending), 2)

    def test_get_pending_after_respond(self):
        cp = ChallengeProtocol()
        r1 = cp.issue("a", "bob", "f1")
        cp.issue("a", "bob", "f2")
        cp.respond("bob", r1.id, True)
        pending = cp.get_pending("bob")
        self.assertEqual(len(pending), 1)

    def test_get_pending_wrong_target(self):
        cp = ChallengeProtocol()
        cp.issue("a", "bob", "f1")
        pending = cp.get_pending("alice")
        self.assertEqual(len(pending), 0)

    def test_unique_ids(self):
        cp = ChallengeProtocol()
        r1 = cp.issue("a", "b", "f1")
        r2 = cp.issue("a", "b", "f2")
        self.assertNotEqual(r1.id, r2.id)

    def test_respond_sets_responded_at(self):
        cp = ChallengeProtocol()
        req = cp.issue("a", "b", "f")
        resp = cp.respond("b", req.id, True)
        self.assertTrue(len(resp.responded_at) > 0)

    def test_respond_sets_responder(self):
        cp = ChallengeProtocol()
        req = cp.issue("a", "b", "f")
        resp = cp.respond("bob", req.id, False)
        self.assertEqual(resp.responder, "bob")

    def test_mailbox_message_contains_finding(self):
        mb = MagicMock()
        cp = ChallengeProtocol(mailbox=mb)
        cp.issue("a", "b", "memory leak detected")
        msg = mb.send.call_args[1].get("message", mb.send.call_args[0][2] if len(mb.send.call_args[0]) > 2 else "")
        # Check keyword arg
        call_kw = mb.send.call_args
        sent_msg = call_kw.kwargs.get("message", "")
        self.assertIn("memory leak detected", sent_msg)


if __name__ == "__main__":
    unittest.main()
