"""Optional Live Tennis enrichment: gated on the key, degrades without it."""

from __future__ import annotations

import httpx
import pytest

from vibe_trading_livetennis.livetennis import (
    API_KEY_ENV,
    LiveTennisClient,
    enrichment_enabled,
)

_MATCH = {
    "data": {
        "id": 555,
        "status": "live",
        "server": 1,
        "points": ["30", "40"],  # receiver break point
        "sets": [[6, 4], [3, 2]],
    }
}


def _live_handler(request: httpx.Request) -> httpx.Response:
    assert request.headers.get("X-API-Key") == "sk_test", "key must be sent as X-API-Key"
    path = request.url.path  # full path includes the /api/public/v1 base
    if path.endswith("/matches/555/score"):
        return httpx.Response(200, json=_MATCH)
    if path.endswith("/matches"):
        return httpx.Response(200, json={"data": [_MATCH["data"]]})
    return httpx.Response(404, json={"error": "not found"})


def _client(api_key):
    transport = httpx.MockTransport(_live_handler)
    inner = httpx.Client(transport=transport, base_url="https://api.livetennisapi.com")
    return LiveTennisClient(api_key=api_key, client=inner)


def test_enrichment_disabled_without_key(monkeypatch):
    monkeypatch.delenv(API_KEY_ENV, raising=False)
    assert enrichment_enabled() is False
    client = _client(None)
    assert client.is_enabled() is False
    # No key -> no network call, graceful empty/None results.
    assert client.live_matches() == []
    assert client.match_score(555) is None
    assert client.enrich(555) is None


def test_enrichment_enabled_with_key(monkeypatch):
    monkeypatch.setenv(API_KEY_ENV, "sk_env")
    assert enrichment_enabled() is True


def test_enrich_returns_state_with_break_point():
    client = _client("sk_test")
    assert client.is_enabled() is True
    record = client.enrich(555)
    assert record is not None
    assert record["status"] == "live"
    assert record["server"] == 1
    assert record["break_point"] is True  # 40 vs 30


def test_live_matches_sent_with_key():
    client = _client("sk_test")
    rows = client.live_matches()
    assert rows and rows[0]["id"] == 555


def test_explicit_key_argument_overrides_absent_env(monkeypatch):
    monkeypatch.delenv(API_KEY_ENV, raising=False)
    assert enrichment_enabled("sk_arg") is True


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__]))
