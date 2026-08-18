"""Optional live-match-state enrichment from the Live Tennis API (free tier).

Disclosure: the Live Tennis API is our own product (https://livetennisapi.com).
This module is the *optional* half of the package: it adds live score / server /
break-point / lifecycle state alongside a Polymarket event-market price series.
It is gated entirely on the ``LIVETENNIS_API_KEY`` environment variable — with
no key the loader still works on the public Polymarket data, and every function
here degrades to ``None`` rather than raising.

Everything called here is on the **free keyed tier** (30 requests/minute,
100 requests/day): ``GET /matches?status=live`` and ``GET /matches/{id}/score``.
100/day is a develop-and-test or ~15-minute-cadence budget, not continuous fast
polling — say so honestly when cadence matters. Historical prices and model
win-probability are paid tiers and are NOT used by this package.

Break-point derivation (rule of the house, matching the feed's own score
object): a break point is on when the RECEIVER is at AD, or the receiver is at
40 while the server is at 0/15/30. It is never on in a tiebreak. It is
``None`` (UNDEF) — never asserted — whenever the server or the points are
absent; a plain 40-40 (deuce) is a determinable *non*-break-point (``False``),
not an assertion that the game is at 40-40.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

__all__ = [
    "LIVETENNIS_BASE_URL",
    "API_KEY_ENV",
    "LiveTennisClient",
    "derive_break_point",
    "enrichment_enabled",
]

LIVETENNIS_BASE_URL = "https://api.livetennisapi.com/api/public/v1"
API_KEY_ENV = "LIVETENNIS_API_KEY"
_USER_AGENT = (
    "vibe-trading-livetennis/0.1 "
    "(+https://github.com/livetennisapi/vibe-trading-livetennis)"
)

_SERVER_LOSABLE = {"0", "15", "30"}


def enrichment_enabled(api_key: str | None = None) -> bool:
    """Return whether a Live Tennis API key is configured (enrichment usable)."""
    return bool(api_key or os.environ.get(API_KEY_ENV))


def derive_break_point(score: dict[str, Any] | None) -> bool | None:
    """Derive break-point state from a score object.

    Returns:
        ``True``  — the receiver holds a break point (receiver AD, or receiver
                    40 while server at 0/15/30).
        ``False`` — a determinable state that is not a break point (e.g. 40-40).
        ``None``  — UNDEF: server or points are absent, or the game is a
                    tiebreak, so break-point state cannot be asserted.
    """
    if not isinstance(score, dict):
        return None
    if score.get("is_tiebreak") or score.get("tiebreak"):
        return None
    server = score.get("server")
    if server not in (1, 2):
        return None
    points = score.get("points")
    if not isinstance(points, (list, tuple)) or len(points) < 2:
        return None
    p1, p2 = points[0], points[1]
    if p1 is None or p2 is None:
        return None
    receiver_points = str(p2 if server == 1 else p1)
    server_points = str(p1 if server == 1 else p2)
    if receiver_points == "AD":
        return True
    return receiver_points == "40" and server_points in _SERVER_LOSABLE


class LiveTennisClient:
    """Free-tier live-state access: live matches and per-match score.

    Authenticates with the ``X-API-Key`` header. Pass ``client`` to inject a
    preconfigured ``httpx.Client`` (tests use ``httpx.MockTransport``). When no
    key is configured, :meth:`is_enabled` is ``False`` and the fetch helpers
    return ``None`` instead of calling the network.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = LIVETENNIS_BASE_URL,
        client: httpx.Client | None = None,
        timeout: float = 15.0,
    ) -> None:
        self._api_key = api_key or os.environ.get(API_KEY_ENV) or ""
        self._owns_client = client is None
        self._client = client or httpx.Client(
            timeout=timeout, headers={"User-Agent": _USER_AGENT}
        )
        self._base_url = base_url.rstrip("/")

    def is_enabled(self) -> bool:
        """Return whether a key is present, so enrichment can run."""
        return bool(self._api_key)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> LiveTennisClient:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        response = self._client.get(
            self._base_url + path,
            params=params or {},
            headers={"X-API-Key": self._api_key},
        )
        if response.status_code == 429:
            raise RuntimeError(
                "Live Tennis API rate limit hit (free tier: 30 req/min, "
                "100 req/day). Slow the polling cadence."
            )
        response.raise_for_status()
        return response.json()

    def live_matches(self) -> list[dict[str, Any]]:
        """List currently live matches; ``[]`` when enrichment is disabled."""
        if not self._api_key:
            return []
        data = self._get("/matches", {"status": "live"})
        if isinstance(data, dict):
            rows = data.get("data", [])
            return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []
        return [r for r in data if isinstance(r, dict)] if isinstance(data, list) else []

    def match_score(self, match_id: int | str) -> dict[str, Any] | None:
        """Fetch one match's score object; ``None`` when disabled or missing."""
        if not self._api_key:
            return None
        try:
            data = self._get(f"/matches/{match_id}/score")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return None
            raise
        if isinstance(data, dict):
            return data.get("data", data)
        return None

    def enrich(self, match_id: int | str) -> dict[str, Any] | None:
        """Return a compact live-state record for a match, or ``None``.

        The record carries ``status`` (live/completed/retired/walkover as the
        feed reports it), ``server`` (1/2 or ``None``), ``break_point``
        (``True``/``False``/``None`` per :func:`derive_break_point`) and the raw
        ``score`` object. ``None`` when enrichment is disabled or the match is
        unknown.
        """
        score = self.match_score(match_id)
        if score is None:
            return None
        server = score.get("server")
        return {
            "match_id": match_id,
            "status": score.get("status"),
            "server": server if server in (1, 2) else None,
            "break_point": derive_break_point(score),
            "score": score,
        }
