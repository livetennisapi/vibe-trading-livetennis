"""Read-only clients for Polymarket's public, keyless Gamma + CLOB APIs.

Disclosure: this package is maintained by the **Live Tennis API** team
(https://livetennisapi.com). The price series it loads, however, comes from
Polymarket's own public endpoints — no key, no order/wallet surface, GET only.

Two services are used, both keyless and read-only:

* Gamma (``https://gamma-api.polymarket.com``) — the market *catalogue* and
  current quotes. ``GET /markets`` and ``GET /events`` accept ``tag_id`` (tennis
  is ``864``) / ``tag_slug=tennis``. Gamma serialises ``outcomes``,
  ``outcomePrices`` and ``clobTokenIds`` as JSON **strings**, not arrays, so they
  must be decoded before use (field names verified against a live response).
* CLOB (``https://clob.polymarket.com``) — ``GET /prices-history?market=<clob
  token id>&interval=&fidelity=`` returns ``{"history": [{"t": epoch_seconds,
  "p": price}]}``: the recorded implied-probability series for **one outcome
  token**. ``interval`` grammar is ``1h/6h/1d/1w/1m/max`` where ``1m`` means one
  *month*; ``fidelity`` is the bar width in minutes.

Neither client touches order books for trading, wallets, positions or accounts.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

__all__ = [
    "GAMMA_BASE_URL",
    "CLOB_BASE_URL",
    "TENNIS_TAG_ID",
    "GammaClient",
    "ClobClient",
    "decode_json_list",
    "to_float",
]

GAMMA_BASE_URL = "https://gamma-api.polymarket.com"
CLOB_BASE_URL = "https://clob.polymarket.com"
# Polymarket's numeric tag id for tennis event markets.
TENNIS_TAG_ID = 864
_USER_AGENT = (
    "vibe-trading-livetennis/0.1 "
    "(+https://github.com/livetennisapi/vibe-trading-livetennis)"
)
# CLOB history windows the server accepts. "1m" is one MONTH; "max" is full.
HISTORY_INTERVALS = ("1h", "6h", "1d", "1w", "1m", "max")


def decode_json_list(value: Any) -> list[Any]:
    """Decode a Gamma field that arrives as a JSON string *or* a real list.

    Gamma returns ``outcomes`` / ``outcomePrices`` / ``clobTokenIds`` as JSON
    strings (``'["Yes", "No"]'``); a mocked or already-decoded payload may hand
    over a real list. Both collapse to a list here; anything unparseable becomes
    ``[]`` rather than raising.
    """
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip():
        try:
            decoded = json.loads(value)
        except (ValueError, TypeError):
            return []
        return decoded if isinstance(decoded, list) else []
    return []


def to_float(value: Any) -> float | None:
    """Coerce a possibly-string numeric field to ``float``, or ``None``."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


class GammaClient:
    """Keyless, read-only access to Gamma ``/markets`` and ``/events``.

    Pass ``client`` to inject a preconfigured ``httpx.Client`` (tests use
    ``httpx.MockTransport`` this way). Usable as a context manager; it closes the
    underlying client only when it created it.
    """

    def __init__(
        self,
        base_url: str = GAMMA_BASE_URL,
        client: httpx.Client | None = None,
        timeout: float = 15.0,
    ) -> None:
        self._owns_client = client is None
        self._client = client or httpx.Client(
            timeout=timeout, headers={"User-Agent": _USER_AGENT}
        )
        self._base_url = base_url.rstrip("/")

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> GammaClient:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def _get(self, path: str, params: dict[str, Any]) -> Any:
        response = self._client.get(self._base_url + path, params=params)
        response.raise_for_status()
        return response.json()

    def tennis_markets(
        self,
        *,
        closed: bool | None = None,
        active: bool | None = True,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List tennis-tagged markets (``tag_id=864``), newest catalogue first."""
        params: dict[str, Any] = {
            "tag_id": TENNIS_TAG_ID,
            "limit": limit,
            "offset": offset,
        }
        if closed is not None:
            params["closed"] = str(closed).lower()
        if active is not None:
            params["active"] = str(active).lower()
        data = self._get("/markets", params)
        return [m for m in data if isinstance(m, dict)] if isinstance(data, list) else []

    def market_by_id(self, market_id: str) -> dict[str, Any] | None:
        try:
            data = self._get(f"/markets/{market_id}", {})
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return None
            raise
        return data if isinstance(data, dict) else None

    def market_by_slug(self, slug: str) -> dict[str, Any] | None:
        data = self._get("/markets", {"slug": slug})
        if isinstance(data, list) and data and isinstance(data[0], dict):
            return data[0]
        return None

    def market(self, id_or_slug: str) -> dict[str, Any] | None:
        """Look up one market by numeric id or by exact slug."""
        if id_or_slug.isdigit():
            return self.market_by_id(id_or_slug)
        return self.market_by_slug(id_or_slug)


class ClobClient:
    """Keyless, read-only access to the CLOB price-history endpoint."""

    def __init__(
        self,
        base_url: str = CLOB_BASE_URL,
        client: httpx.Client | None = None,
        timeout: float = 20.0,
    ) -> None:
        self._owns_client = client is None
        self._client = client or httpx.Client(
            timeout=timeout, headers={"User-Agent": _USER_AGENT}
        )
        self._base_url = base_url.rstrip("/")

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> ClobClient:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def prices_history(
        self,
        token_id: str,
        *,
        interval: str = "max",
        fidelity: int = 1440,
    ) -> list[dict[str, Any]]:
        """Return the ``[{"t": epoch_s, "p": price}]`` series for one token.

        ``interval`` must be one of :data:`HISTORY_INTERVALS`; ``fidelity`` is
        the bar width in minutes. Returns ``[]`` when the payload carries no
        usable history list.
        """
        if interval not in HISTORY_INTERVALS:
            raise ValueError(f"interval must be one of {list(HISTORY_INTERVALS)}")
        params = {"market": token_id, "interval": interval, "fidelity": fidelity}
        response = self._client.get(self._base_url + "/prices-history", params=params)
        response.raise_for_status()
        payload = response.json()
        history = payload.get("history") if isinstance(payload, dict) else None
        return [p for p in history if isinstance(p, dict)] if isinstance(history, list) else []
