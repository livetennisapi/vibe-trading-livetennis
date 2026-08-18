---
name: polymarket-tennis-loader
category: data-source
description: A custom Vibe-Trading data loader for tennis event-market price series from Polymarket's public keyless CLOB history, with optional Live Tennis API live-state enrichment (score / server / break-point). Observe-only. Vendor-authored by the Live Tennis API team — register it yourself; it is not bundled into Vibe-Trading.
---

## Disclosure

This loader is maintained by the **Live Tennis API team** (https://livetennisapi.com),
so it is vendor-authored — judge accordingly. It follows the exact path
Vibe-Trading's maintainer pointed at on
[HKUDS/Vibe-Trading#1133](https://github.com/HKUDS/Vibe-Trading/issues/1133): a
custom loader plus this skill, living in its **own** package, that you register
into your install — nothing is bundled into the Vibe-Trading tree.

## Overview

`vibe-trading-livetennis` adds one data source, `polymarket_tennis`, that returns
an OHLC frame for a **tennis event market**. The price series comes from
Polymarket's **public, keyless CLOB price history** — each outcome share settles
at $1 if the outcome happens and $0 otherwise, so the price *is* the market's
implied probability (0-1), and that recorded series is the tradeable market
observation. This is the same kind of read the built-in `prediction_market` tool
performs, exposed through the loader interface so `backtest` / `get_market_data`
can consume it.

Optionally, when a `LIVETENNIS_API_KEY` is set, the package can enrich a market
with **live match state** from the Live Tennis API free tier — live score, which
player is serving, and a derived break-point flag — the "live tennis state
alongside event contracts" named in #1133. The loader itself needs no key.

- Loader source name: `polymarket_tennis`
- Market type: `prediction_market` (its own type — never in an equity/crypto fallback chain)
- Auth: none for the price loader; the enrichment is gated on `LIVETENNIS_API_KEY`
- Stance: **observe-only** — GET requests to public data endpoints; no order, wallet, position or account surface

## Install

```bash
pip install vibe-trading-livetennis
# or from source:
pip install "git+https://github.com/livetennisapi/vibe-trading-livetennis"
```

## Register the loader (the custom-loader wiring)

Vibe-Trading loaders self-register through a `@register` decorator into
`backtest.loaders.registry.LOADER_REGISTRY`, and accepted source names live in
`backtest.loaders.registry.VALID_SOURCES`. Because this loader ships in a
separate package, the host does not import it for you — call `register()` once at
startup, before the first `backtest` / `get_market_data` call:

```python
import vibe_trading_livetennis

vibe_trading_livetennis.register()   # adds `polymarket_tennis` to the registry + VALID_SOURCES
```

Then request it explicitly:

```python
from vibe_trading_livetennis import DataLoader

loader = DataLoader()
frames = loader.fetch(
    ["will-jannik-sinner-win-the-2026-mens-us-open#Yes"],
    "2026-02-01", "2026-02-13", interval="1D",
)
# {symbol: DataFrame(trade_date index; open/high/low/close/volume)}
```

A symbol is a Polymarket market **slug**, a numeric **market id**, a `0x`
**condition id**, or a raw **CLOB token id** — optionally suffixed `#<outcome>`
(e.g. `#Yes`) to pick an outcome; the default is the market's first outcome.

## Optional live-state enrichment

```python
from vibe_trading_livetennis import LiveTennisClient

client = LiveTennisClient()          # reads LIVETENNIS_API_KEY
if client.is_enabled():
    state = client.enrich(match_id)  # {status, server, break_point, score}
```

Match a market's two named players to a live match with `match_players(...)`,
which returns `None` rather than guessing when the evidence is ambiguous
(doubles markets are not matched).

## Environment variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `LIVETENNIS_API_KEY` | No | Enables live-state enrichment (score / server / break-point). Absent → enrichment is disabled and the price loader still works. Free keys: https://livetennisapi.com/subscribe/free |

## Honest coverage

- The series is a **genuine recorded history** of the outcome's implied
  probability from CLOB `/prices-history` — not fabricated, not a live snapshot
  relabelled as history.
- It is **implied probability in [0, 1]**, not a conventional asset price. High
  and low are the max/min probability within each bar.
- CLOB history carries **no per-bar volume**, so `volume` is `0.0` on every bar.
  Do not use this source for volume-based sizing.
- Coverage is only as deep as the market's own lifetime — a tennis market lives
  days to weeks, so `interval="max"` covers roughly its whole life. **There is no
  multi-year OHLC here**; deep historical backtests need your own recorded
  series. The loader serves the market's real recorded window, live/recent
  included.
- A market must exist on Polymarket and resolve to one outcome token; when it
  cannot, that symbol is omitted (one bad symbol never aborts the batch).

## Live Tennis API tiers (enrichment)

- **Free keyed tier**: 30 requests/minute, 100 requests/day — live scores
  (score / server / break-point state), players (including current ranking),
  fixtures, usage. 100/day is a develop-and-test or ~15-minute-cadence budget,
  **not** continuous fast polling.
- **Paid**: completed-match history and point-by-point (Basic), match events and
  the market-prices feed (Pro), model **win-probability** and in-play stats
  (Ultra). This package does **not** require any paid capability — market prices
  come from Polymarket's public API, and live state uses only free-tier
  endpoints.

## Break-point derivation

A break point is on when the **receiver** is at AD, or the receiver is at 40
while the server is at 0/15/30. It is never on in a tiebreak, and it is `None`
(UNDEF — never asserted) whenever the server or the points are absent. A plain
40-40 (deuce) is a determinable *non*-break-point (`False`), not an assertion
that the game is at 40-40.

## Links

- Live Tennis API: https://livetennisapi.com
- Docs: https://docs.livetennisapi.com
- Free tier: https://livetennisapi.com/subscribe/free
- Source: https://github.com/livetennisapi/vibe-trading-livetennis
