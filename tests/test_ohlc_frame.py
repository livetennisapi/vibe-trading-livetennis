"""OHLC frame construction: shape, invariants, resampling, clipping, batch."""

from __future__ import annotations

import pandas as pd

from vibe_trading_livetennis.loader import points_to_ohlc, validate_ohlc

from .conftest import HISTORY_POINTS

_REQUIRED = ["open", "high", "low", "close", "volume"]


def _fetch_daily(loader):
    return loader.fetch(["1088471#Yes"], "2026-02-10", "2026-02-13", interval="1D")


def test_fetch_returns_frame_keyed_by_symbol(loader):
    out = _fetch_daily(loader)
    assert list(out) == ["1088471#Yes"]


def test_frame_columns_and_index(loader):
    frame = _fetch_daily(loader)["1088471#Yes"]
    assert list(frame.columns) == _REQUIRED
    assert isinstance(frame.index, pd.DatetimeIndex)
    assert frame.index.name == "trade_date"
    assert frame.index.tz is None
    assert frame.index.is_monotonic_increasing
    assert all(frame[c].dtype == float for c in _REQUIRED)


def test_daily_bar_ohlc_values(loader):
    frame = _fetch_daily(loader)["1088471#Yes"]
    day = frame.loc["2026-02-10"]
    # points that day: 0.50 (open), 0.62 (high), 0.44 (low), 0.55 (close)
    assert day["open"] == 0.50
    assert day["high"] == 0.62
    assert day["low"] == 0.44
    assert day["close"] == 0.55
    assert day["volume"] == 0.0


def test_frame_satisfies_host_ohlc_invariants(loader):
    frame = _fetch_daily(loader)["1088471#Yes"]
    # No row is dropped by the host-style validator => all invariants already hold.
    assert validate_ohlc(frame).equals(frame)
    assert (frame["high"] >= frame["low"]).all()
    assert (frame["high"] >= frame[["open", "close"]].max(axis=1)).all()
    assert (frame["low"] <= frame[["open", "close"]].min(axis=1)).all()
    assert (frame[["open", "high", "low", "close"]] > 0).all().all()


def test_clipping_to_window():
    # Only keep 2026-02-11 (exclude 02-10 and 02-12+).
    frame = points_to_ohlc(HISTORY_POINTS, "2026-02-11", "2026-02-11", "1D")
    assert list(frame.index.strftime("%Y-%m-%d")) == ["2026-02-11"]


def test_volume_is_zero_everywhere():
    frame = points_to_ohlc(HISTORY_POINTS, "2026-02-10", "2026-02-13", "1D")
    assert (frame["volume"] == 0.0).all()


def test_empty_history_yields_empty_frame():
    assert points_to_ohlc([], "2026-02-10", "2026-02-13", "1D").empty


def test_validate_ohlc_drops_structural_and_nonpositive():
    bad = pd.DataFrame(
        {
            "open": [0.5, 0.5, 0.5],
            "high": [0.6, 0.4, 0.6],   # row 1: high < low  -> dropped
            "low": [0.4, 0.5, 0.0],    # row 2: low == 0 (nonpositive) -> dropped
            "close": [0.55, 0.45, 0.55],
            "volume": [0.0, 0.0, 0.0],
        }
    )
    out = validate_ohlc(bad)
    assert len(out) == 1
    assert out.iloc[0]["high"] == 0.6 and out.iloc[0]["low"] == 0.4


def test_unresolved_symbol_is_omitted_not_fatal(loader):
    out = loader.fetch(["no-such-slug", "1088471#Yes"], "2026-02-10", "2026-02-13")
    assert list(out) == ["1088471#Yes"]


def test_bad_outcome_is_omitted(loader):
    out = loader.fetch(["1088471#Nope"], "2026-02-10", "2026-02-13")
    assert out == {}


def test_reversed_date_range_raises(loader):
    try:
        loader.fetch(["1088471#Yes"], "2026-02-13", "2026-02-10")
    except ValueError:
        return
    raise AssertionError("expected ValueError on start > end")


def test_hourly_interval_produces_more_bars_than_daily(loader):
    hourly = loader.fetch(["1088471#Yes"], "2026-02-10", "2026-02-13", interval="1H")
    daily = loader.fetch(["1088471#Yes"], "2026-02-10", "2026-02-13", interval="1D")
    assert len(hourly["1088471#Yes"]) >= len(daily["1088471#Yes"])
