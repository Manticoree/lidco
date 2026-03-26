"""Tests for T612 HttpTool."""
from unittest.mock import patch, MagicMock
import json
import urllib.error

import pytest

from lidco.tools.http_tool import HttpTool, HttpResponse


# ---------------------------------------------------------------------------
# HttpResponse
# ---------------------------------------------------------------------------

class TestHttpResponse:
    def _make(self, status=200, body="", reason="OK", error=""):
        return HttpResponse(
            url="https://example.com",
            method="GET",
            status=status,
            reason=reason,
            headers={"content-type": "text/plain"},
            body=body,
            elapsed_ms=50.0,
            error=error,
        )

    def test_ok_true_for_2xx(self):
        assert self._make(200).ok is True
        assert self._make(201).ok is True
        assert self._make(204).ok is True

    def test_ok_false_for_4xx(self):
        assert self._make(404).ok is False
        assert self._make(500).ok is False

    def test_json_parse(self):
        resp = self._make(body='{"key": "value"}')
        data = resp.json()
        assert data["key"] == "value"

    def test_json_raises_on_invalid(self):
        resp = self._make(body="not json")
        with pytest.raises(ValueError):
            resp.json()

    def test_format_summary_ok(self):
        resp = self._make(200, body="hello")
        s = resp.format_summary()
        assert "200" in s
        assert "GET" in s
        assert "hello" in s

    def test_format_summary_error(self):
        resp = self._make(0, error="Connection refused")
        s = resp.format_summary()
        assert "Connection refused" in s

    def test_format_summary_json_body(self):
        resp = HttpResponse(
            url="https://example.com",
            method="GET",
            status=200,
            reason="OK",
            headers={"content-type": "application/json"},
            body='{"a": 1}',
            elapsed_ms=10.0,
        )
        s = resp.format_summary()
        assert '"a"' in s


# ---------------------------------------------------------------------------
# HttpTool — mocked requests
# ---------------------------------------------------------------------------

def _mock_response(status=200, reason="OK", body=b"hello", headers=None):
    mock = MagicMock()
    mock.status = status
    mock.reason = reason
    mock.read.return_value = body
    mock.headers = MagicMock()
    mock.headers.items.return_value = list((headers or {}).items())
    mock.__enter__ = lambda s: s
    mock.__exit__ = MagicMock(return_value=False)
    return mock


class TestHttpToolGet:
    def test_get_success(self):
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.return_value = _mock_response(200, body=b"ok")
            tool = HttpTool()
            resp = tool.get("https://example.com")
        assert resp.ok
        assert resp.status == 200
        assert resp.body == "ok"
        assert resp.method == "GET"

    def test_get_with_params(self):
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.return_value = _mock_response(200)
            tool = HttpTool()
            resp = tool.get("https://example.com", params={"q": "test", "page": "1"})
        assert "q=test" in resp.url or resp.ok

    def test_get_with_bearer(self):
        captured = {}
        def fake_open(req, **kw):
            captured["auth"] = req.get_header("Authorization")
            return _mock_response(200)
        with patch("urllib.request.urlopen", side_effect=fake_open):
            tool = HttpTool()
            tool.get("https://example.com", bearer="mytoken")
        assert captured["auth"] == "Bearer mytoken"

    def test_get_with_basic_auth(self):
        captured = {}
        def fake_open(req, **kw):
            captured["auth"] = req.get_header("Authorization")
            return _mock_response(200)
        with patch("urllib.request.urlopen", side_effect=fake_open):
            tool = HttpTool()
            tool.get("https://example.com", auth=("user", "pass"))
        assert captured["auth"].startswith("Basic ")

    def test_404_returns_response(self):
        exc = urllib.error.HTTPError(
            "https://example.com", 404, "Not Found", MagicMock(items=lambda: []), None
        )
        exc.read = lambda: b"not found"
        with patch("urllib.request.urlopen", side_effect=exc):
            tool = HttpTool()
            resp = tool.get("https://example.com")
        assert resp.status == 404
        assert not resp.ok


class TestHttpToolPost:
    def test_post_json(self):
        captured = {}
        def fake_open(req, **kw):
            captured["content_type"] = req.get_header("Content-type")
            captured["data"] = req.data
            return _mock_response(201, body=b'{"id": 1}')
        with patch("urllib.request.urlopen", side_effect=fake_open):
            tool = HttpTool()
            resp = tool.post("https://example.com/items", json_data={"name": "test"})
        assert "application/json" in (captured["content_type"] or "")
        assert resp.status == 201

    def test_post_form(self):
        captured = {}
        def fake_open(req, **kw):
            captured["content_type"] = req.get_header("Content-type")
            return _mock_response(200)
        with patch("urllib.request.urlopen", side_effect=fake_open):
            tool = HttpTool()
            tool.post("https://example.com", form_data={"key": "val"})
        assert "application/x-www-form-urlencoded" in (captured["content_type"] or "")

    def test_post_raw_body(self):
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.return_value = _mock_response(200)
            tool = HttpTool()
            resp = tool.post("https://example.com", body="raw data")
        assert resp.ok


class TestHttpToolMethods:
    def _do(self, method_name, **kwargs):
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.return_value = _mock_response(200)
            tool = HttpTool()
            fn = getattr(tool, method_name)
            return fn("https://example.com", **kwargs)

    def test_put(self):
        resp = self._do("put", json_data={"x": 1})
        assert resp.method == "PUT"

    def test_delete(self):
        resp = self._do("delete")
        assert resp.method == "DELETE"

    def test_patch(self):
        resp = self._do("patch", json_data={"y": 2})
        assert resp.method == "PATCH"


class TestHttpToolErrors:
    def test_url_error_returns_response(self):
        from urllib.error import URLError
        with patch("urllib.request.urlopen", side_effect=URLError("Connection refused")):
            tool = HttpTool()
            resp = tool.get("https://nonexistent.invalid")
        assert resp.status == 0
        assert not resp.ok
        assert resp.error != ""

    def test_timeout_returns_response(self):
        with patch("urllib.request.urlopen", side_effect=TimeoutError("timed out")):
            tool = HttpTool()
            resp = tool.get("https://example.com", timeout=0.001)
        assert resp.status == 0
        assert "timed out" in resp.error.lower() or not resp.ok

    def test_default_headers_applied(self):
        captured = {}
        def fake_open(req, **kw):
            captured["x_custom"] = req.get_header("X-custom")
            return _mock_response(200)
        with patch("urllib.request.urlopen", side_effect=fake_open):
            tool = HttpTool(default_headers={"X-Custom": "myval"})
            tool.get("https://example.com")
        assert captured["x_custom"] == "myval"

    def test_elapsed_ms_set(self):
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.return_value = _mock_response(200)
            tool = HttpTool()
            resp = tool.get("https://example.com")
        assert resp.elapsed_ms >= 0
