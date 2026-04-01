"""Tests for lidco.auth.token_manager."""

from __future__ import annotations

import time

from lidco.auth.oauth_flow import OAuthConfig, OAuthFlow, OAuthToken
from lidco.auth.token_manager import TokenManager


def _make_token(access: str = "tok", refresh: str = "ref", expires_at: float = 0.0) -> OAuthToken:
    return OAuthToken(access_token=access, refresh_token=refresh, expires_at=expires_at)


def test_store_and_get():
    mgr = TokenManager()
    tok = _make_token("a1")
    mgr.store("svc", tok)
    assert mgr.get("svc") is tok


def test_get_missing_returns_none():
    mgr = TokenManager()
    assert mgr.get("nope") is None


def test_remove():
    mgr = TokenManager()
    mgr.store("svc", _make_token())
    assert mgr.remove("svc") is True
    assert mgr.remove("svc") is False
    assert mgr.get("svc") is None


def test_list_services():
    mgr = TokenManager()
    mgr.store("beta", _make_token())
    mgr.store("alpha", _make_token())
    assert mgr.list_services() == ["alpha", "beta"]


def test_is_expired_missing():
    mgr = TokenManager()
    assert mgr.is_expired("missing") is True


def test_is_expired_not_expired():
    mgr = TokenManager()
    mgr.store("svc", _make_token(expires_at=time.time() + 9999))
    assert mgr.is_expired("svc") is False


def test_refresh_if_needed_expired():
    cfg = OAuthConfig(
        client_id="c",
        auth_url="https://a.com/auth",
        token_url="https://a.com/token",
    )
    flow = OAuthFlow(cfg)
    mgr = TokenManager()
    old = _make_token("old", "ref", expires_at=time.time() - 100)
    mgr.store("svc", old)
    new = mgr.refresh_if_needed("svc", flow)
    assert new is not None
    assert new.access_token != "old"
    assert mgr.get("svc") == new


def test_refresh_if_needed_not_expired():
    cfg = OAuthConfig(client_id="c", auth_url="https://a.com/auth", token_url="https://a.com/token")
    flow = OAuthFlow(cfg)
    mgr = TokenManager()
    tok = _make_token("still_good", "ref", expires_at=time.time() + 9999)
    mgr.store("svc", tok)
    result = mgr.refresh_if_needed("svc", flow)
    assert result is tok


def test_clear_and_count():
    mgr = TokenManager()
    mgr.store("a", _make_token())
    mgr.store("b", _make_token())
    assert mgr.token_count() == 2
    assert mgr.clear() == 2
    assert mgr.token_count() == 0
