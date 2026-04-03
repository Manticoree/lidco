"""Tests for lidco.gateway.api_gateway."""
from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from lidco.gateway.api_gateway import ApiGateway, Endpoint, GatewayRequest, GatewayResponse


class TestEndpointDataclass:
    def test_defaults(self) -> None:
        ep = Endpoint(name="a", url="http://a.com")
        assert ep.healthy is True
        assert ep.weight == 1
        assert ep.failure_count == 0

    def test_gateway_request_frozen(self) -> None:
        req = GatewayRequest(provider="openai", path="/v1/chat")
        assert req.method == "POST"
        with pytest.raises(AttributeError):
            req.method = "GET"  # type: ignore[misc]

    def test_gateway_response_frozen(self) -> None:
        resp = GatewayResponse(status=200, body="ok", endpoint="a", latency_ms=12.3)
        assert resp.status == 200
        with pytest.raises(AttributeError):
            resp.status = 500  # type: ignore[misc]


class TestApiGateway:
    def test_add_endpoint(self) -> None:
        gw = ApiGateway()
        ep = gw.add_endpoint("ep1", "http://ep1.com", weight=3)
        assert ep.name == "ep1"
        assert ep.weight == 3
        assert len(gw.all_endpoints()) == 1

    def test_remove_endpoint(self) -> None:
        gw = ApiGateway()
        gw.add_endpoint("ep1", "http://ep1.com")
        assert gw.remove_endpoint("ep1") is True
        assert gw.remove_endpoint("ep1") is False
        assert len(gw.all_endpoints()) == 0

    def test_select_endpoint_none_when_empty(self) -> None:
        gw = ApiGateway()
        assert gw.select_endpoint() is None

    def test_select_endpoint_returns_healthy(self) -> None:
        gw = ApiGateway()
        gw.add_endpoint("ep1", "http://ep1.com")
        ep = gw.select_endpoint()
        assert ep is not None
        assert ep.name == "ep1"

    def test_select_endpoint_filters_by_provider(self) -> None:
        gw = ApiGateway()
        gw.add_endpoint("openai", "http://openai.com")
        gw.add_endpoint("anthropic", "http://anthropic.com")
        ep = gw.select_endpoint(provider="anthropic")
        assert ep is not None
        assert ep.name == "anthropic"

    def test_mark_failure_increments(self) -> None:
        gw = ApiGateway(failure_threshold=3)
        gw.add_endpoint("ep1", "http://ep1.com")
        gw.mark_failure("ep1")
        gw.mark_failure("ep1")
        ep = gw.mark_failure("ep1")
        assert ep.failure_count == 3
        assert ep.healthy is False

    def test_mark_failure_below_threshold_stays_healthy(self) -> None:
        gw = ApiGateway(failure_threshold=5)
        gw.add_endpoint("ep1", "http://ep1.com")
        ep = gw.mark_failure("ep1")
        assert ep.healthy is True

    def test_mark_success_resets(self) -> None:
        gw = ApiGateway(failure_threshold=1)
        gw.add_endpoint("ep1", "http://ep1.com")
        gw.mark_failure("ep1")
        ep = gw.mark_success("ep1")
        assert ep.failure_count == 0
        assert ep.healthy is True

    def test_check_health_already_healthy(self) -> None:
        gw = ApiGateway()
        gw.add_endpoint("ep1", "http://ep1.com")
        assert gw.check_health("ep1") is True

    def test_check_health_recovers_after_timeout(self) -> None:
        gw = ApiGateway(failure_threshold=1, recovery_timeout=0.01)
        gw.add_endpoint("ep1", "http://ep1.com")
        gw.mark_failure("ep1")
        assert gw.check_health("ep1") is False
        time.sleep(0.02)
        assert gw.check_health("ep1") is True

    def test_healthy_endpoints_excludes_unhealthy(self) -> None:
        gw = ApiGateway(failure_threshold=1)
        gw.add_endpoint("ep1", "http://ep1.com")
        gw.add_endpoint("ep2", "http://ep2.com")
        gw.mark_failure("ep1")
        healthy = gw.healthy_endpoints()
        assert len(healthy) == 1
        assert healthy[0].name == "ep2"

    def test_summary(self) -> None:
        gw = ApiGateway(failure_threshold=1)
        gw.add_endpoint("ep1", "http://ep1.com")
        gw.add_endpoint("ep2", "http://ep2.com")
        gw.mark_failure("ep1")
        s = gw.summary()
        assert s["total"] == 2
        assert s["healthy"] == 1
        assert s["unhealthy"] == 1
        assert len(s["endpoints"]) == 2
