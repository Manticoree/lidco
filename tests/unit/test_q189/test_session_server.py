"""Tests for RemoteSessionServer — Q189, task 1057."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from lidco.remote.session_server import RemoteSessionServer, ServerInfo


class TestServerInfo(unittest.TestCase):
    def test_frozen(self):
        info = ServerInfo(host="localhost", port=9000, token="abc", url="ws://localhost:9000")
        with self.assertRaises(AttributeError):
            info.host = "other"  # type: ignore[misc]

    def test_fields(self):
        info = ServerInfo(host="h", port=1, token="t", url="u")
        self.assertEqual(info.host, "h")
        self.assertEqual(info.port, 1)
        self.assertEqual(info.token, "t")
        self.assertEqual(info.url, "u")


class TestRemoteSessionServer(unittest.TestCase):
    def test_init_defaults(self):
        s = RemoteSessionServer()
        self.assertFalse(s.is_running)
        self.assertEqual(s.connected_clients, 0)

    def test_init_custom(self):
        s = RemoteSessionServer(host="0.0.0.0", port=8080, auth_token="secret")
        self.assertEqual(s._host, "0.0.0.0")
        self.assertEqual(s._port, 8080)
        self.assertEqual(s._auth_token, "secret")

    def test_start_returns_server_info(self):
        s = RemoteSessionServer(host="localhost", port=5555)
        info = s.start()
        self.assertIsInstance(info, ServerInfo)
        self.assertEqual(info.host, "localhost")
        self.assertEqual(info.port, 5555)
        self.assertTrue(s.is_running)

    def test_start_ephemeral_port(self):
        s = RemoteSessionServer(port=0)
        info = s.start()
        self.assertGreater(info.port, 0)

    def test_start_twice_raises(self):
        s = RemoteSessionServer()
        s.start()
        with self.assertRaises(RuntimeError):
            s.start()

    def test_stop(self):
        s = RemoteSessionServer()
        s.start()
        s.stop()
        self.assertFalse(s.is_running)
        self.assertEqual(s.connected_clients, 0)

    def test_stop_when_not_running(self):
        s = RemoteSessionServer()
        s.stop()  # should not raise
        self.assertFalse(s.is_running)

    def test_send_message(self):
        s = RemoteSessionServer()
        s.start()
        s.send_message("hello")
        self.assertEqual(s._messages, ["hello"])

    def test_send_message_not_running_raises(self):
        s = RemoteSessionServer()
        with self.assertRaises(RuntimeError):
            s.send_message("nope")

    def test_on_message_callback(self):
        s = RemoteSessionServer()
        s.start()
        received: list[str] = []
        s.on_message(received.append)
        s._simulate_receive("hi")
        self.assertEqual(received, ["hi"])

    def test_simulate_connect_disconnect(self):
        s = RemoteSessionServer()
        s.start()
        self.assertEqual(s.connected_clients, 0)
        s._simulate_connect()
        self.assertEqual(s.connected_clients, 1)
        s._simulate_connect()
        self.assertEqual(s.connected_clients, 2)
        s._simulate_disconnect()
        self.assertEqual(s.connected_clients, 1)

    def test_simulate_connect_not_running_raises(self):
        s = RemoteSessionServer()
        with self.assertRaises(RuntimeError):
            s._simulate_connect()

    def test_disconnect_below_zero(self):
        s = RemoteSessionServer()
        s.start()
        s._simulate_disconnect()
        self.assertEqual(s.connected_clients, 0)

    def test_url_format(self):
        s = RemoteSessionServer(host="myhost", port=1234)
        info = s.start()
        self.assertEqual(info.url, "ws://myhost:1234")

    def test_auth_token_generated_when_none(self):
        s = RemoteSessionServer()
        self.assertTrue(len(s._auth_token) > 0)

    def test_multiple_callbacks(self):
        s = RemoteSessionServer()
        s.start()
        a: list[str] = []
        b: list[str] = []
        s.on_message(a.append)
        s.on_message(b.append)
        s._simulate_receive("msg")
        self.assertEqual(a, ["msg"])
        self.assertEqual(b, ["msg"])


if __name__ == "__main__":
    unittest.main()
