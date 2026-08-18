"""Gamma client parsing: JSON-string fields, market lookup, tennis tag."""

from __future__ import annotations

from vibe_trading_livetennis.gamma import decode_json_list, to_float


def test_decode_json_list_accepts_json_string():
    assert decode_json_list('["Yes", "No"]') == ["Yes", "No"]


def test_decode_json_list_accepts_real_list():
    assert decode_json_list(["Yes", "No"]) == ["Yes", "No"]


def test_decode_json_list_bad_input_is_empty():
    assert decode_json_list(None) == []
    assert decode_json_list("not json") == []
    assert decode_json_list('{"a": 1}') == []  # object, not a list


def test_to_float_coerces_strings_and_rejects_bools():
    assert to_float("0.405") == 0.405
    assert to_float(0.5) == 0.5
    assert to_float(None) is None
    assert to_float(True) is None
    assert to_float("nan") != to_float("nan")  # NaN, but parses


def test_market_by_id(gamma_client):
    market = gamma_client.market("1088471")
    assert market is not None
    names = decode_json_list(market["outcomes"])
    prices = decode_json_list(market["outcomePrices"])
    assert names == ["Yes", "No"]
    assert prices == ["0.405", "0.595"]


def test_market_by_slug(gamma_client):
    market = gamma_client.market("will-jannik-sinner-win-the-2026-mens-us-open")
    assert market is not None
    assert market["id"] == "1088471"


def test_missing_slug_returns_none(gamma_client):
    assert gamma_client.market("no-such-market-slug") is None


def test_tennis_markets_uses_tag_864(gamma_client):
    markets = gamma_client.tennis_markets()
    assert markets and markets[0]["id"] == "1088471"
