"""Shared fixtures: fully-mocked httpx transports for Gamma, CLOB and Live Tennis.

No test in this suite touches the network. Each mock transport answers the exact
endpoints the clients call, with payloads shaped like the real (verified)
responses — Gamma's JSON-string ``outcomes``/``outcomePrices``/``clobTokenIds``
included.
"""

from __future__ import annotations

import json

import httpx
import pytest

# A representative live tennis market (fields verified against a real response).
SINNER_MARKET = {
    "id": "1088471",
    "question": "Will Jannik Sinner win the 2026 Men's US Open?",
    "slug": "will-jannik-sinner-win-the-2026-mens-us-open",
    "conditionId": "0x65bbe9ee978b2e7f99596407bd92599db3600cbd19e0ef6cba303553c5cd3b84",
    "outcomes": json.dumps(["Yes", "No"]),
    "outcomePrices": json.dumps(["0.405", "0.595"]),
    "clobTokenIds": json.dumps(
        ["11111111111111111111111111111111", "22222222222222222222222222222222"]
    ),
    "closed": False,
    "active": True,
    "endDate": "2026-09-13T00:00:00Z",
}

YES_TOKEN = "11111111111111111111111111111111"

# A recorded implied-probability series spanning 2026-02-10..2026-02-13 (UTC),
# several points per day so daily resampling produces distinct O/H/L/C.
HISTORY_POINTS = [
    {"t": 1770681600, "p": 0.50},  # 2026-02-10 00:00
    {"t": 1770703200, "p": 0.62},  # 2026-02-10 06:00
    {"t": 1770724800, "p": 0.44},  # 2026-02-10 12:00
    {"t": 1770746400, "p": 0.55},  # 2026-02-10 18:00
    {"t": 1770768000, "p": 0.58},  # 2026-02-11 00:00
    {"t": 1770811200, "p": 0.66},  # 2026-02-11 12:00
    {"t": 1770854400, "p": 0.60},  # 2026-02-12 00:00
    {"t": 1770897600, "p": 0.48},  # 2026-02-12 12:00
    {"t": 1770940800, "p": 0.52},  # 2026-02-13 00:00
]


def _gamma_handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    params = dict(request.url.params)
    if path == "/markets/1088471":
        return httpx.Response(200, json=SINNER_MARKET)
    if path == "/markets":
        slug = params.get("slug")
        if slug == SINNER_MARKET["slug"]:
            return httpx.Response(200, json=[SINNER_MARKET])
        if params.get("tag_id") == "864":
            return httpx.Response(200, json=[SINNER_MARKET])
        return httpx.Response(200, json=[])
    return httpx.Response(404, json={"error": "not found"})


def _clob_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/prices-history":
        params = dict(request.url.params)
        if params.get("market") == YES_TOKEN:
            return httpx.Response(200, json={"history": HISTORY_POINTS})
        return httpx.Response(200, json={"history": []})
    return httpx.Response(404, json={"error": "not found"})


@pytest.fixture
def gamma_client():
    from vibe_trading_livetennis.gamma import GammaClient

    transport = httpx.MockTransport(_gamma_handler)
    client = httpx.Client(transport=transport, base_url="https://gamma-api.polymarket.com")
    yield GammaClient(client=client)
    client.close()


@pytest.fixture
def clob_client():
    from vibe_trading_livetennis.gamma import ClobClient

    transport = httpx.MockTransport(_clob_handler)
    client = httpx.Client(transport=transport, base_url="https://clob.polymarket.com")
    yield ClobClient(client=client)
    client.close()


@pytest.fixture
def loader(gamma_client, clob_client):
    from vibe_trading_livetennis.loader import DataLoader

    return DataLoader(gamma=gamma_client, clob=clob_client)
