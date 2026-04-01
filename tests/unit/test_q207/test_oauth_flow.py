"""Tests for lidco.auth.oauth_flow."""

from __future__ import annotations

import time
import urllib.parse

from lidco.auth.oauth_flow import (
    OAuthConfig,
    OAuthError,
    OAuthFlow,
    OAuthToken,
    PKCEChallenge,
)


def _cfg(**overrides) -> OAuthConfig:
    defaults = {
        "client_id": "test-client",
        "auth_url": "https://auth.example.com/authorize",
        "token_url": "https://auth.example.com/token",
    }
    defaults.update(overrides)
    return OAuthConfig(**defaults)


def test_oauth_config_defaults():
    cfg = _cfg()
    assert cfg.redirect_uri == "http://localhost:8765/callback"
    assert cfg.scopes == ()


def test_generate_pkce_produces_valid_pair():
    flow = OAuthFlow(_cfg())
    pkce = flow.generate_pkce()
    assert isinstance(pkce, PKCEChallenge)
    assert pkce.method == "S256"
    assert len(pkce.verifier) > 20
    assert len(pkce.challenge) > 20
    assert pkce.verifier != pkce.challenge


def test_generate_pkce_unique_each_call():
    flow = OAuthFlow(_cfg())
    a = flow.generate_pkce()
    b = flow.generate_pkce()
    assert a.verifier != b.verifier


def test_build_auth_url_basic():
    flow = OAuthFlow(_cfg())
    url = flow.build_auth_url()
    assert url.startswith("https://auth.example.com/authorize?")
    parsed = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    assert parsed["client_id"] == ["test-client"]
    assert parsed["response_type"] == ["code"]


def test_build_auth_url_with_state_and_pkce():
    flow = OAuthFlow(_cfg(scopes=("read", "write")))
    pkce = flow.generate_pkce()
    url = flow.build_auth_url(state="abc123", pkce=pkce)
    parsed = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    assert parsed["state"] == ["abc123"]
    assert parsed["code_challenge"] == [pkce.challenge]
    assert parsed["code_challenge_method"] == ["S256"]
    assert parsed["scope"] == ["read write"]


def test_exchange_code_returns_token():
    flow = OAuthFlow(_cfg())
    token = flow.exchange_code("authcode123")
    assert isinstance(token, OAuthToken)
    assert "authcode123" in token.access_token
    assert token.refresh_token != ""
    assert token.token_type == "Bearer"
    assert token.expires_at > time.time()


def test_exchange_code_empty_raises():
    flow = OAuthFlow(_cfg())
    try:
        flow.exchange_code("")
        assert False, "Expected OAuthError"
    except OAuthError:
        pass


def test_refresh_returns_new_token():
    flow = OAuthFlow(_cfg())
    original = flow.exchange_code("code1")
    refreshed = flow.refresh(original)
    assert refreshed.access_token != original.access_token
    assert refreshed.refresh_token == original.refresh_token
    assert refreshed.expires_at > time.time()


def test_refresh_no_refresh_token_raises():
    flow = OAuthFlow(_cfg())
    token = OAuthToken(access_token="abc")
    try:
        flow.refresh(token)
        assert False, "Expected OAuthError"
    except OAuthError:
        pass


def test_is_expired_false_for_future():
    flow = OAuthFlow(_cfg())
    token = OAuthToken(access_token="a", expires_at=time.time() + 9999)
    assert flow.is_expired(token) is False


def test_is_expired_true_for_past():
    flow = OAuthFlow(_cfg())
    token = OAuthToken(access_token="a", expires_at=time.time() - 10)
    assert flow.is_expired(token) is True


def test_is_expired_zero_means_no_expiry():
    flow = OAuthFlow(_cfg())
    token = OAuthToken(access_token="a", expires_at=0.0)
    assert flow.is_expired(token) is False


def test_revoke_success():
    flow = OAuthFlow(_cfg())
    token = OAuthToken(access_token="abc")
    assert flow.revoke(token) is True


def test_revoke_empty_token_returns_false():
    flow = OAuthFlow(_cfg())
    token = OAuthToken(access_token="")
    assert flow.revoke(token) is False
