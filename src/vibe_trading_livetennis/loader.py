"""A Vibe-Trading data loader for tennis event-market price series.

Disclosure: maintained by the **Live Tennis API** team
(https://livetennisapi.com). The OHLC series this loader returns is built from
**Polymarket's public, keyless CLOB price history** — the recorded
implied-probability series for a tennis event-market outcome. Each outcome share
settles at $1 if the outcome happens and $0 otherwise, so the price *is* the
market's implied probability (0-1), and that price series is the tradeable
market observation this loader exposes — the same kind of read the built-in
``prediction_market`` tool performs.

Honest coverage (read before backtesting):

* The series is a **genuine recorded history** of the outcome's implied
  probability, pulled from CLOB ``/prices-history``. It is not fabricated and
  not a live snapshot dressed up as history.
* It is **implied probability in [0, 1]**, not a conventional asset price. High
  and low are the max/min probability inside each bar.
* CLOB history carries **no per-bar volume**, so ``volume`` is ``0.0`` on every
  bar (documented, not inferred). Notional-sizing that divides by volume must
  not use this source.
* Coverage is only as deep as the market's own lifetime — a tennis market lives
  days to weeks, so ``interval="max"`` covers roughly the whole market. There is
  **no multi-year OHLC** here; deep historical backtests need your own recorded
  series. This loader serves the market's real recorded window, live/recent
  included.
* A market must exist on Polymarket and be resolvable to one outcome token. When
  it cannot be, that symbol is omitted from the result — one bad symbol never
  aborts the batch.

The loader satisfies Vibe-Trading's ``DataLoaderProtocol`` structurally: it
exposes ``name`` / ``markets`` / ``requires_auth`` / ``is_available`` and a
``fetch`` that returns ``{symbol: DataFrame(trade_date index; open/high/low/
close/volume)}``. It runs the same OHLC-invariant guard the host applies at the
loader boundary, so the frame is safe to feed straight into a backtest.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from .gamma import ClobClient, GammaClient, decode_json_list

logger = logging.getLogger(__name__)

_OHLC_COLUMNS = ("open", "high", "low", "close", "volume")

# Backtest interval -> (pandas resample rule, CLOB history fidelity in minutes).
# Daily is the primary granularity; finer bars are supported where the history
# fidelity can carry them.
_INTERVAL_MAP: dict[str, tuple[str, int]] = {
    "1D": ("1D", 1440),
    "1H": ("1h", 60),
    "4H": ("4h", 240),
    "1W": ("1W", 1440),
    "1M": ("1MS", 1440),
}


def _resolve_interval(interval: str) -> tuple[str, int]:
    """Map a project interval to a (pandas rule, fidelity-minutes) pair."""
    raw = str(interval or "1D").strip()
    upper = raw.upper()
    if upper in _INTERVAL_MAP:
        return _INTERVAL_MAP[upper]
    # Bare trailing lowercase "m" is minutes (e.g. "5m", "15m").
    if raw.endswith("m") and not raw.endswith("M"):
        digits = raw[:-1]
        if digits.isdigit() and int(digits) > 0:
            return (f"{int(digits)}min", int(digits))
    # Unknown: fall back to daily bars.
    return _INTERVAL_MAP["1D"]


def validate_ohlc(frame: pd.DataFrame) -> pd.DataFrame:
    """Drop bars that violate OHLC invariants (mirrors the host's boundary check).

    Removes structurally dirty bars (``high < low``, or high/low failing to
    bracket open/close) and any non-positive price, so the frame that reaches a
    backtest cannot surface as NaN/inf downstream. A settled outcome that prints
    an exact ``0.0`` is dropped by the positivity rule; such prints are vanishingly
    rare (settled losers clear near ``4e-7``, not ``0``).
    """
    required = ("open", "high", "low", "close")
    if frame.empty or not all(col in frame.columns for col in required):
        return frame
    open_, high, low, close = (frame[c] for c in required)
    structural = (
        (high < low)
        | (high < open_)
        | (high < close)
        | (low > open_)
        | (low > close)
    )
    nonpositive = (open_ <= 0) | (high <= 0) | (low <= 0) | (close <= 0)
    invalid = structural | nonpositive
    if not bool(invalid.any()):
        return frame
    return frame[~invalid]


def _split_code(code: str) -> tuple[str, str | None]:
    """Split ``"slug#Yes"`` into ``("slug", "Yes")``; no ``#`` -> outcome ``None``."""
    if "#" in code:
        identifier, outcome = code.split("#", 1)
        outcome = outcome.strip()
        return identifier.strip(), (outcome or None)
    return code.strip(), None


def _is_clob_token_id(value: str) -> bool:
    """Whether the identifier is a raw CLOB token id (a large uint256 decimal)."""
    if not (value.isascii() and value.isdigit()):
        return False
    # CLOB token ids are keccak-derived uint256; gamma catalogue ids fit int64.
    return int(value) > (2**63 - 1)


def points_to_ohlc(
    points: list[dict[str, Any]],
    start_date: str,
    end_date: str,
    interval: str,
) -> pd.DataFrame:
    """Resample ``[{"t": epoch_s, "p": price}]`` into a clipped OHLC frame.

    Args:
        points: Ascending price points from CLOB ``/prices-history``.
        start_date: Inclusive window start (``YYYY-MM-DD``).
        end_date: Inclusive window end (``YYYY-MM-DD``).
        interval: Backtest interval such as ``1D`` or ``1H``.

    Returns:
        A DataFrame indexed by a tz-naive ``trade_date`` with float
        ``open/high/low/close/volume`` columns (``volume`` always ``0.0``),
        clipped to the inclusive window and OHLC-validated. Empty when no point
        carries a usable price inside the window.
    """
    rule, _ = _resolve_interval(interval)
    rows: list[tuple[pd.Timestamp, float]] = []
    for point in points:
        epoch = point.get("t")
        price = point.get("p")
        if epoch is None or price is None:
            continue
        try:
            ts = pd.to_datetime(int(epoch), unit="s", utc=True).tz_convert(None)
            value = float(price)
        except (ValueError, TypeError):
            continue
        rows.append((ts, value))
    if not rows:
        return pd.DataFrame()

    series = pd.Series(
        [v for _, v in rows],
        index=pd.DatetimeIndex([t for t, _ in rows], name="trade_date"),
    ).sort_index()

    agg = series.resample(rule).agg(["first", "max", "min", "last"]).dropna(how="all")
    if agg.empty:
        return pd.DataFrame()
    frame = pd.DataFrame(
        {
            "open": agg["first"],
            "high": agg["max"],
            "low": agg["min"],
            "close": agg["last"],
            "volume": 0.0,
        }
    ).dropna(subset=["open", "high", "low", "close"])
    frame.index.name = "trade_date"

    lower = pd.Timestamp(start_date).normalize()
    upper = pd.Timestamp(end_date).normalize() + pd.Timedelta(days=1)
    frame = frame[(frame.index >= lower) & (frame.index < upper)]
    if frame.empty:
        return frame
    frame = frame.loc[:, list(_OHLC_COLUMNS)].astype(float).sort_index()
    return validate_ohlc(frame)


class DataLoader:
    """Polymarket tennis event-market OHLC loader (public, keyless, read-only).

    Register it into a Vibe-Trading install with
    :func:`vibe_trading_livetennis.register`, then request it explicitly with
    ``source="polymarket_tennis"``. It declares its own ``prediction_market``
    market type, so it never sits in an equity/crypto auto-fallback chain — a
    tennis event-market price can never silently substitute for a stock.
    """

    name = "polymarket_tennis"
    markets = {"prediction_market"}
    requires_auth = False

    def __init__(
        self,
        gamma: GammaClient | None = None,
        clob: ClobClient | None = None,
    ) -> None:
        """Construct the loader.

        Args:
            gamma: Optional injected :class:`GammaClient` (tests inject a mock).
            clob: Optional injected :class:`ClobClient`.
        """
        self._gamma = gamma
        self._clob = clob

    def is_available(self) -> bool:
        """Always available: it uses Polymarket's public keyless endpoints."""
        return True

    def _gamma_client(self) -> GammaClient:
        if self._gamma is None:
            self._gamma = GammaClient()
        return self._gamma

    def _clob_client(self) -> ClobClient:
        if self._clob is None:
            self._clob = ClobClient()
        return self._clob

    def _resolve_token(self, identifier: str, outcome: str | None) -> str | None:
        """Resolve a market identifier + outcome to one CLOB token id, or ``None``."""
        if _is_clob_token_id(identifier):
            return identifier
        market = self._gamma_client().market(identifier)
        if not isinstance(market, dict):
            return None
        names = [str(n) for n in decode_json_list(market.get("outcomes"))]
        tokens = [str(t) for t in decode_json_list(market.get("clobTokenIds"))]
        if not tokens:
            return None
        index = 0
        if outcome is not None:
            matches = [i for i, n in enumerate(names) if n.lower() == outcome.lower()]
            if not matches:
                logger.warning(
                    "outcome %r not found for %s (have %s)", outcome, identifier, names
                )
                return None
            index = matches[0]
        if index >= len(tokens):
            return None
        return tokens[index]

    def fetch(
        self,
        codes: list[str],
        start_date: str,
        end_date: str,
        *,
        interval: str = "1D",
        fields: list[str] | None = None,
    ) -> dict[str, pd.DataFrame]:
        """Fetch OHLC implied-probability history keyed by the input symbols.

        Args:
            codes: Tennis-market symbols. Each is a Polymarket market slug, a
                numeric gamma market id, a ``0x`` condition id, or a raw CLOB
                token id — optionally suffixed ``#<outcome>`` to pick an outcome
                (default: the market's first outcome).
            start_date: Inclusive start date (``YYYY-MM-DD``).
            end_date: Inclusive end date (``YYYY-MM-DD``).
            interval: Backtest interval such as ``1D`` or ``1H``.
            fields: Ignored; present for interface compatibility.

        Returns:
            Mapping of input symbol to a normalized OHLC DataFrame. A symbol that
            cannot be resolved or has no priced history is omitted; one failure
            never aborts the batch.
        """
        del fields
        if not codes:
            return {}
        if pd.Timestamp(start_date) > pd.Timestamp(end_date):
            raise ValueError(f"start_date ({start_date}) > end_date ({end_date})")

        _, fidelity = _resolve_interval(interval)
        result: dict[str, pd.DataFrame] = {}
        for code in codes:
            try:
                identifier, outcome = _split_code(code)
                token_id = self._resolve_token(identifier, outcome)
                if token_id is None:
                    logger.warning("polymarket_tennis: could not resolve %s", code)
                    continue
                points = self._clob_client().prices_history(
                    token_id, interval="max", fidelity=fidelity
                )
                frame = points_to_ohlc(points, start_date, end_date, interval)
                if not frame.empty:
                    result[code] = frame
            except Exception as exc:  # noqa: BLE001 - one bad symbol never aborts
                logger.warning("polymarket_tennis failed for %s: %s", code, exc)
        return result
