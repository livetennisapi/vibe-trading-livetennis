"""Break-point derivation: AD / 40-vs-low true, deuce false, UNDEF when unknown."""

from __future__ import annotations

from vibe_trading_livetennis.livetennis import derive_break_point


def _score(server, points, **extra):
    return {"server": server, "points": points, **extra}


def test_receiver_at_ad_is_break_point():
    # server 1, receiver (p2) at AD
    assert derive_break_point(_score(1, ["40", "AD"])) is True


def test_receiver_40_vs_server_30_is_break_point():
    # server 1 at 30, receiver (p2) at 40
    assert derive_break_point(_score(1, ["30", "40"])) is True


def test_receiver_40_vs_server_0_is_break_point():
    assert derive_break_point(_score(2, ["40", "0"])) is True  # server 2 at 0


def test_deuce_40_40_is_not_a_break_point_and_not_asserted():
    # 40-40: determinable, and it is NOT a break point (server not at 0/15/30).
    # We must never assert an advantage/40-40 as a break point.
    assert derive_break_point(_score(1, ["40", "40"])) is False


def test_server_ahead_is_not_a_break_point():
    assert derive_break_point(_score(1, ["40", "30"])) is False


def test_undef_when_server_unknown():
    assert derive_break_point(_score(None, ["40", "AD"])) is None
    assert derive_break_point(_score(0, ["40", "AD"])) is None


def test_undef_when_points_missing():
    assert derive_break_point(_score(1, None)) is None
    assert derive_break_point(_score(1, ["40"])) is None
    assert derive_break_point(_score(1, [None, None])) is None


def test_undef_in_tiebreak():
    assert derive_break_point(_score(1, ["6", "5"], is_tiebreak=True)) is None


def test_undef_on_none_score():
    assert derive_break_point(None) is None
