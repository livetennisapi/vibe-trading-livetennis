"""Market <-> match player-name matcher: folding, subsets, ambiguity, doubles."""

from __future__ import annotations

from vibe_trading_livetennis.matching import fold_name, match_players, name_similarity


def _match(name):
    return {"player1_name": name[0], "player2_name": name[1], "id": name[2]}


def test_fold_name_strips_diacritics_and_punctuation():
    assert fold_name("Marin Čilić") == "marin cilic"
    assert fold_name("J.-L. Struff") == "j l struff"


def test_exact_and_subset_similarity():
    assert name_similarity("Jannik Sinner", "Jannik Sinner") == 1.0
    assert name_similarity("Jannik Sinner", "Sinner") == 0.9  # token subset
    assert name_similarity("Sinner", "Jannik Sinner") == 0.9
    # an initial + surname is not a token subset, so it falls to surname match
    assert name_similarity("J. Sinner", "Jannik Sinner") == 0.75


def test_surname_only_agreement():
    assert name_similarity("Carlos Alcaraz", "Juan Alcaraz") == 0.75


def test_no_agreement_is_zero():
    assert name_similarity("Carlos Alcaraz", "Jannik Sinner") == 0.0


def test_confident_direct_match():
    candidates = [_match(("Jannik Sinner", "Carlos Alcaraz", 42))]
    decision = match_players("Jannik Sinner", "Carlos Alcaraz", candidates)
    assert decision.match is not None
    assert decision.match["id"] == 42
    assert decision.reversed_order is False
    assert decision.confidence >= 0.70


def test_reversed_order_still_matches():
    candidates = [_match(("Carlos Alcaraz", "Jannik Sinner", 7))]
    decision = match_players("Jannik Sinner", "Carlos Alcaraz", candidates)
    assert decision.match is not None
    assert decision.reversed_order is True


def test_ambiguous_pair_returns_none():
    candidates = [
        _match(("Jannik Sinner", "Carlos Alcaraz", 1)),
        _match(("Jannik Sinner", "Carlos Alcaraz", 2)),
    ]
    decision = match_players("Jannik Sinner", "Carlos Alcaraz", candidates)
    assert decision.match is None
    assert "ambiguous" in decision.note


def test_below_threshold_returns_none():
    candidates = [_match(("Roger Federer", "Rafael Nadal", 9))]
    decision = match_players("Jannik Sinner", "Carlos Alcaraz", candidates)
    assert decision.match is None


def test_doubles_market_is_not_matched():
    candidates = [_match(("Sinner/Alcaraz", "Federer/Nadal", 5))]
    decision = match_players("Sinner/Alcaraz", "Federer/Nadal", candidates)
    assert decision.match is None
    assert "doubles" in decision.note


def test_nested_players_object_shape():
    candidate = {
        "players": {"p1": {"name": "Jannik Sinner"}, "p2": {"name": "Carlos Alcaraz"}},
        "id": 99,
    }
    decision = match_players("Jannik Sinner", "Carlos Alcaraz", [candidate])
    assert decision.match is not None and decision.match["id"] == 99
