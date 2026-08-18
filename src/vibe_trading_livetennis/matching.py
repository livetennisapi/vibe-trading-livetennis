"""Match a Polymarket tennis market to a Live Tennis API match, conservatively.

A minimal reimplementation of the player-name matcher from
``livetennisapi/polymarket-tennis`` (https://github.com/livetennisapi/polymarket-tennis),
kept deliberately cautious: fold names, score the two sides, and return ``None``
instead of guessing when the evidence is ambiguous. Doubles markets are not
matched here. This matcher exists only so the *optional* live-state enrichment
can find the right match for a market — the price loader never needs it.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

__all__ = [
    "MatchDecision",
    "fold_name",
    "name_similarity",
    "match_players",
]

MATCH_THRESHOLD = 0.70
AMBIGUITY_MARGIN = 0.10

_STATUS_RE = re.compile(
    r"\s*[\(\[]?\b(retired|walk[\s-]?over|walkover|ret\.?|w/o|withdrew)\b\.?[\)\]]?\s*$",
    re.IGNORECASE,
)


def _strip_status_wording(name: str) -> str:
    """Drop trailing retirement/walkover wording ("Paul (Retired)")."""
    previous = None
    while previous != name:
        previous = name
        name = _STATUS_RE.sub("", name).strip()
    return name


def fold_name(name: str) -> str:
    """Lowercase, strip diacritics, collapse punctuation to single spaces."""
    decomposed = unicodedata.normalize("NFKD", name or "")
    ascii_only = "".join(c for c in decomposed if not unicodedata.combining(c))
    ascii_only = re.sub(r"[-'.]", " ", ascii_only.lower())
    return " ".join(ascii_only.split())


def name_similarity(market_name: str, api_name: str) -> float:
    """Similarity in ``[0, 1]`` between one market-side and one feed-side name."""
    a = fold_name(_strip_status_wording(market_name))
    b = fold_name(_strip_status_wording(api_name))
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    ta, tb = a.split(), b.split()
    # one name is a token-subset of the other ("J. Lehecka" vs "Jiri Lehecka")
    if set(ta) <= set(tb) or set(tb) <= set(ta):
        return 0.9
    # surname-only agreement (last token, the market's usual short form)
    if ta[-1] == tb[-1]:
        return 0.75
    return 0.0


@dataclass(frozen=True)
class MatchDecision:
    """A confident market-to-match pairing, or the reason there is none."""

    match: dict[str, Any] | None
    confidence: float
    reversed_order: bool
    note: str


def _is_doubles(*names: str) -> bool:
    return any("/" in (n or "") for n in names)


def _candidate_names(candidate: dict[str, Any]) -> tuple[str, str] | None:
    """Pull ``(p1, p2)`` from a Live Tennis API match/fixture object."""
    players = candidate.get("players")
    if isinstance(players, dict):
        p1 = (players.get("p1") or {}).get("name")
        p2 = (players.get("p2") or {}).get("name")
        if p1 and p2:
            return str(p1), str(p2)
    p1 = candidate.get("player1_name")
    p2 = candidate.get("player2_name")
    if p1 and p2:
        return str(p1), str(p2)
    return None


def _pair_score(
    market_p1: str, market_p2: str, candidate: dict[str, Any]
) -> tuple[float, bool]:
    names = _candidate_names(candidate)
    if names is None:
        return 0.0, False
    direct = min(
        name_similarity(market_p1, names[0]),
        name_similarity(market_p2, names[1]),
    )
    reversed_ = min(
        name_similarity(market_p1, names[1]),
        name_similarity(market_p2, names[0]),
    )
    if reversed_ > direct:
        return reversed_, True
    return direct, False


def match_players(
    market_p1: str,
    market_p2: str,
    candidates: list[dict[str, Any]],
    *,
    threshold: float = MATCH_THRESHOLD,
    ambiguity_margin: float = AMBIGUITY_MARGIN,
) -> MatchDecision:
    """Pick the Live Tennis API match for a market's two named sides.

    Returns a ``MatchDecision`` whose ``match`` is ``None`` (never a guess) when:
    either side is a doubles pairing, no candidate clears ``threshold``, or the
    top two candidates are within ``ambiguity_margin`` of each other.
    """
    if _is_doubles(market_p1, market_p2):
        return MatchDecision(None, 0.0, False, "doubles market not matched")

    scored: list[tuple[dict[str, Any], float, bool]] = []
    for candidate in candidates:
        names = _candidate_names(candidate)
        if names is None or _is_doubles(*names):
            continue
        score, is_reversed = _pair_score(market_p1, market_p2, candidate)
        if score > 0.0:
            scored.append((candidate, score, is_reversed))
    scored.sort(key=lambda item: item[1], reverse=True)

    if not scored:
        return MatchDecision(None, 0.0, False, "no candidate names agree")
    best, best_score, best_reversed = scored[0]
    if best_score < threshold:
        return MatchDecision(None, round(best_score, 3), best_reversed, "below threshold")
    if len(scored) > 1 and (best_score - scored[1][1]) < ambiguity_margin:
        return MatchDecision(
            None, round(best_score, 3), best_reversed, "ambiguous: two close candidates"
        )
    note = "names+order-reversed" if best_reversed else "names"
    return MatchDecision(best, round(best_score, 3), best_reversed, note)
