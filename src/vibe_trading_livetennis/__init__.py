"""vibe-trading-livetennis: a Polymarket tennis event-market data loader for
Vibe-Trading, with optional Live Tennis API live-state enrichment.

Maintained by the Live Tennis API team (https://livetennisapi.com). Observe-only:
public keyless Polymarket price history for the loader, and — when a
``LIVETENNIS_API_KEY`` is set — free-tier live score / server / break-point
enrichment. No order, wallet, position or account surface of any kind.
"""

from __future__ import annotations

from .gamma import TENNIS_TAG_ID, ClobClient, GammaClient
from .livetennis import LiveTennisClient, derive_break_point, enrichment_enabled
from .loader import DataLoader, points_to_ohlc, validate_ohlc
from .matching import MatchDecision, fold_name, match_players, name_similarity
from .register import register

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "DataLoader",
    "register",
    "points_to_ohlc",
    "validate_ohlc",
    "GammaClient",
    "ClobClient",
    "TENNIS_TAG_ID",
    "LiveTennisClient",
    "derive_break_point",
    "enrichment_enabled",
    "MatchDecision",
    "match_players",
    "fold_name",
    "name_similarity",
]
