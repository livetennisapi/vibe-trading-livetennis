# vibe-trading-livetennis

A custom [Vibe-Trading](https://github.com/HKUDS/Vibe-Trading) data loader for
**tennis event-market price series**, with optional live match-state enrichment.
Observe-only, MIT-licensed.

> **Disclosure:** this package is maintained by the **Live Tennis API team**
> (https://livetennisapi.com). It is vendor-authored — judge accordingly. The
> price series it loads comes from Polymarket's own public, keyless API; the
> optional enrichment uses our free tier.

## Why this is a separate package (not a PR into Vibe-Trading)

We first proposed a live-tennis tool for the Vibe-Trading repo in
[HKUDS/Vibe-Trading#1133](https://github.com/HKUDS/Vibe-Trading/issues/1133).
The maintainer declined bundling it — correctly, because a tool bundled into the
package must run on free public sources, and a keyed API is a dependency the
project can't own for its users. In the same breath they pointed at the honest
path:

> *"a skill plus a custom loader. The project supports registering your own data
> source and writing a skill that documents its interface, so anyone who wants
> live tennis state alongside event contracts can wire yours up without it being
> part of the package."*

This repo is exactly that: a standalone loader + [`SKILL.md`](./SKILL.md) you
register into your own install. Nothing is added to the Vibe-Trading tree.

## What it does

- Registers one data source, **`polymarket_tennis`**, implementing Vibe-Trading's
  `DataLoaderProtocol`. `fetch(...)` returns
  `{symbol: DataFrame(trade_date index; open/high/low/close/volume)}`.
- The OHLC series is built from **Polymarket's public keyless CLOB price
  history** — the recorded implied-probability series for a tennis event-market
  outcome (each share settles $1/$0, so the price *is* the market's implied
  probability). This mirrors Vibe-Trading's own `prediction_market` tool, exposed
  through the loader interface.
- **Optional** live match-state enrichment from the Live Tennis API free tier —
  live score, which player is serving, and a derived break-point flag — gated on
  `LIVETENNIS_API_KEY`. No key → enrichment off, loader still works.
- A conservative market↔match player-name matcher (reusing the ideas in
  [`livetennisapi/polymarket-tennis`](https://github.com/livetennisapi/polymarket-tennis))
  that returns `None` rather than guessing when names are ambiguous.

## Quickstart

```bash
pip install vibe-trading-livetennis
```

```python
import vibe_trading_livetennis
from vibe_trading_livetennis import DataLoader

vibe_trading_livetennis.register()   # wire `polymarket_tennis` into your install

loader = DataLoader()
frames = loader.fetch(
    ["will-jannik-sinner-win-the-2026-mens-us-open#Yes"],
    "2026-02-01", "2026-02-13", interval="1D",
)
print(frames["will-jannik-sinner-win-the-2026-mens-us-open#Yes"].tail())
```

A symbol is a Polymarket market **slug**, numeric **market id**, `0x` **condition
id**, or raw **CLOB token id**, optionally suffixed `#<outcome>` (default: first
outcome). See [`SKILL.md`](./SKILL.md) for the full interface and registration
notes.

## Honest coverage (read before backtesting)

- The series is a **genuine recorded history** of implied probability from CLOB
  `/prices-history` — not fabricated, not a live snapshot relabelled as history.
- It is **implied probability in [0, 1]**, not a conventional asset price.
- CLOB history has **no per-bar volume**, so `volume` is `0.0` on every bar.
- Coverage is only as deep as the market's own lifetime (a tennis market lives
  days to weeks). **There is no multi-year OHLC**; deep historical backtests need
  your own recorded series. The loader serves the market's real recorded window,
  live/recent included.
- A market must exist on Polymarket and resolve to one outcome token; otherwise
  that symbol is omitted (one bad symbol never aborts the batch).

## Tiers (enrichment only)

The price loader needs **no key**. The optional live-state enrichment uses the
Live Tennis API **free keyed tier**: 30 req/min, 100 req/day — live scores
(score / server / break-point), players (including current ranking), fixtures,
usage. 100/day is a develop-and-test or ~15-minute-cadence budget, not continuous
fast polling. Completed-match history and point-by-point are Basic; the
market-prices feed is Pro; model win-probability and in-play stats are Ultra.
This package requires none of them — market prices come from Polymarket's public
API and enrichment uses only free-tier endpoints. Free keys:
https://livetennisapi.com/subscribe/free

## Observe-only

Every request this package makes is a `GET` to a public data endpoint. It has no
order, position, wallet or account surface, and it computes no trading signal —
it is a data source, not a strategy or an executor.

## Development

```bash
pip install -e ".[dev]"
ruff check .
pytest
```

## License

MIT — see [LICENSE](./LICENSE).
