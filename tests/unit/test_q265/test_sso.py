"""Tests for Q265 SSOClient."""
from __future__ import annotations

import time
import unittest
from unittest.mock import patch

from lidco.identity.sso import SSOClient, SSOConfig, SSOSession


class TestSSOConfig(unittest.TestCase):
    def test_defaults(self):
        cfg = SSOConfig(provider="okta", issuer_url="https://okta.example.com", client_id="abc")
        assert cfg.protocol == "oidc"
        assert cfg.client_secret == ""
        assert cfg.redirect_uri == ""

    def test_saml_protocol(self):
        cfg = SSOConfig(provider="adfs", issuer_url="https://adfs.local", client_id="x", protocol="saml")
        assert cfg.protocol == "saml"


class TestSSOClient(unittest.TestCase):
    def _make_client(self, protocol: str = "oidc") -> SSOClient:
        cfg = SSOConfig(
            provider="test-idp",
            issuer_url="https://idp.example.com",
            client_id="client123",
            redirect_uri="http://localhost/callback",
            protocol=protocol,
        )
        return SSOClient(cfg)

    def test_initiate_login_oidc(self):
        client = self._make_client("oidc")
        url = client.initiate_login()
        assert "authorize" in url
        assert "client123" in url
        assert "response_type=code" in url

    def test_initiate_login_saml(self):
        client = self._make_client("saml")
        url = client.initiate_login()
        assert "saml/auth" in url
        assert "client123" in url

    def test_exchange_token(self):
        client = self._make_client()
        session = client.exchange_token("auth-code-xyz")
        assert isinstance(session, SSOSession)
        assert session.provider == "test-idp"
        assert session.token
        assert session.attributes.get("code") == "auth-code-xyz"

    def test_validate_session(self):
        client = self._make_client()
        session = client.exchange_token("code1")
        result = client.validate_session(session.token)
        assert result is not None
        assert result.user_id == session.user_id

    def test_validate_session_unknown_token(self):
        client = self._make_client()
        assert client.validate_session("bogus") is None

    def test_validate_session_expired(self):
        client = self._make_client()
        session = client.exchange_token("code2")
        with patch("lidco.identity.sso.time") as mock_time:
            mock_time.time.return_value = session.expires_at + 1
            assert client.validate_session(session.token) is None

    def test_logout(self):
        client = self._make_client()
        session = client.exchange_token("code3")
        assert client.logout(session.token) is True
        assert client.validate_session(session.token) is None

    def test_logout_unknown(self):
        client = self._make_client()
        assert client.logout("unknown") is False

    def test_active_sessions(self):
        client = self._make_client()
        client.exchange_token("c1")
        client.exchange_token("c2")
        assert len(client.active_sessions()) == 2

    def test_refresh(self):
        client = self._make_client()
        session = client.exchange_token("code4")
        refreshed = client.refresh(session.token)
        assert refreshed is not None
        assert refreshed.token != session.token
        assert refreshed.user_id == session.user_id
        # Old token gone
        assert client.validate_session(session.token) is None

    def test_refresh_unknown(self):
        client = self._make_client()
        assert client.refresh("no-such") is None

    def test_summary(self):
        client = self._make_client()
        client.exchange_token("c1")
        s = client.summary()
        assert s["provider"] == "test-idp"
        assert s["active_sessions"] == 1


if __name__ == "__main__":
    unittest.main()
