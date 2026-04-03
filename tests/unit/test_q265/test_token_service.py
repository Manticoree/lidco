"""Tests for Q265 TokenService."""
from __future__ import annotations

import time
import unittest
from unittest.mock import patch

from lidco.identity.token_service import Token, TokenClaims, TokenService


class TestTokenService(unittest.TestCase):
    def _make(self, **kwargs) -> TokenService:
        return TokenService(**kwargs)

    def test_create_token(self):
        svc = self._make()
        tok = svc.create("user1")
        assert isinstance(tok, Token)
        assert tok.claims.sub == "user1"
        assert tok.claims.iss == "lidco"
        assert tok.token

    def test_create_with_roles(self):
        svc = self._make()
        tok = svc.create("user1", roles=["admin", "editor"])
        assert tok.claims.roles == ["admin", "editor"]

    def test_create_with_custom_ttl(self):
        svc = self._make()
        tok = svc.create("user1", ttl=60.0)
        assert tok.claims.exp - tok.claims.iat < 61.0

    def test_create_with_custom_claims(self):
        svc = self._make()
        tok = svc.create("user1", custom={"org": "acme"})
        assert tok.claims.custom == {"org": "acme"}

    def test_validate_valid_token(self):
        svc = self._make()
        tok = svc.create("user1")
        claims = svc.validate(tok.token)
        assert claims is not None
        assert claims.sub == "user1"

    def test_validate_invalid_token(self):
        svc = self._make()
        assert svc.validate("garbage") is None

    def test_validate_expired_token(self):
        svc = self._make()
        tok = svc.create("user1", ttl=1.0)
        with patch("lidco.identity.token_service.time") as mock_time:
            mock_time.time.return_value = tok.claims.exp + 10
            assert svc.validate(tok.token) is None

    def test_revoke_token(self):
        svc = self._make()
        tok = svc.create("user1")
        assert svc.revoke(tok.token) is True
        assert svc.validate(tok.token) is None

    def test_revoke_unknown(self):
        svc = self._make()
        assert svc.revoke("no-such-token") is False

    def test_revoke_already_revoked(self):
        svc = self._make()
        tok = svc.create("user1")
        svc.revoke(tok.token)
        assert svc.revoke(tok.token) is False

    def test_is_revoked(self):
        svc = self._make()
        tok = svc.create("user1")
        assert svc.is_revoked(tok.token) is False
        svc.revoke(tok.token)
        assert svc.is_revoked(tok.token) is True

    def test_refresh_token(self):
        svc = self._make()
        tok = svc.create("user1", roles=["admin"])
        new_tok = svc.refresh(tok.token)
        assert new_tok is not None
        assert new_tok.token != tok.token
        assert new_tok.claims.sub == "user1"
        assert new_tok.claims.roles == ["admin"]
        # Old is revoked
        assert svc.is_revoked(tok.token) is True

    def test_refresh_revoked(self):
        svc = self._make()
        tok = svc.create("user1")
        svc.revoke(tok.token)
        assert svc.refresh(tok.token) is None

    def test_refresh_unknown(self):
        svc = self._make()
        assert svc.refresh("nope") is None

    def test_active_tokens(self):
        svc = self._make()
        svc.create("u1")
        svc.create("u2")
        tok3 = svc.create("u3")
        svc.revoke(tok3.token)
        active = svc.active_tokens()
        assert len(active) == 2

    def test_cleanup_expired(self):
        svc = self._make()
        svc.create("u1", ttl=0.001)
        svc.create("u2", ttl=0.001)
        time.sleep(0.01)
        removed = svc.cleanup_expired()
        assert removed == 2

    def test_summary(self):
        svc = self._make()
        svc.create("u1")
        s = svc.summary()
        assert s["active"] == 1
        assert s["revoked"] == 0

    def test_different_secrets_reject(self):
        svc1 = self._make(secret="key1")
        svc2 = self._make(secret="key2")
        tok = svc1.create("user1")
        assert svc2.validate(tok.token) is None


if __name__ == "__main__":
    unittest.main()
