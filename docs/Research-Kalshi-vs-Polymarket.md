# Research — Kalshi vs Polymarket for the copy-trading strategy

**Date:** 2026-09-18 | **Requested by:** CEO ("is Kalshi even better volume and signal wise for this than Polymarket?") | **Method:** live API probing + OpenAPI spec review + 2026 volume data (The Block / MetaMask / Pew)

## Verdict

**Stay on Polymarket.** Kalshi wins on raw volume but **loses decisively on signal access** — and signal access is the entire premise of this strategy. You cannot build "copy the top traders" on Kalshi's public data, full stop. Fees are a wash (both US exchanges use the same taker curve).

## Volume — Kalshi wins (~10x the market you trade)

- June 2026: **Kalshi $31.5B** vs Polymarket $13.3B ($10.3B intl + **$3.04B US**) — Kalshi overtook Polymarket in April 2026 (per The Block / MetaMask News).
- The CEO trades the US-legal exchange → relevant comparison is Kalshi $31.5B vs **Polymarket US $3.04B** (~10x).
- Mix: sports ≈ 80% of Kalshi volume (39% on Polymarket) — Kalshi is game-day heavy; Polymarket skews politics/crypto/rates.

## Signal access — Polymarket wins decisively (the hinge)

- **Polymarket (what our scanner uses):** free public data API with a top-trader **leaderboard by PnL** + **full per-wallet trade history** (proxy wallets). This is the raw material of the whole consensus strategy.
- **Kalshi:** OpenAPI spec reviewed end-to-end (98 endpoints): **zero leaderboard endpoints, zero per-user trade history, zero user identity on trades**. `/markets/trades` = anonymous prints (ticker, price, qty, ts, is_block_trade). `/portfolio/*`, `/historical/*`, `/fcm/positions` are auth-only and show *your own* data only. The website leaderboard is login-gated and not API-accessible.
- Third-party "whale trackers" for Kalshi (Stand.trade, predite.io) are paid and work off the **anonymous** feed + size heuristics — they cannot identify "the winning wallet" the way Polymarket's proxy wallets do.

## Fees — wash

- Kalshi taker: `round_up(0.07 × C × P × (1−P))` → ~$1.75 / 100 contracts at $0.50.
- Polymarket US taker: same curve (0.0695 theta, max $1.74 @ p=0.50) per docs.polymarket.us/fees.
- (Polymarket intl is zero-fee, but that's not the venue the CEO trades.)

## What this means

1. The current strategy (top-trader consensus → fresh-BUY copy) **cannot transfer to Kalshi** — the signal source doesn't exist publicly.
2. Kalshi would force a different, weaker strategy: anonymous large-fill/flow following (block-trade alerts via `/markets/trades` `is_block_trade`), with no identity, no consistency tracking, and the same fees.
3. Polymarket US volume is growing fast (+72% MoM June) — the venue isn't dying; Kalshi's lead is mostly sports where the US product is newer.

## Recommendation

- **No migration, no new build.** Keep Polymarket; let the Sep 24 scorecard verdict drive gate tuning (the real profit lever).
- Optional future ticket (P3): a Kalshi **block-trade flow scanner** as a supplementary signal only — never a replacement — using the public anonymous feed. Cost: ~1 day Atlas work, no hire.
- **Hiring: not needed.** This was a bounded research task (done, no hire); a Kalshi prototype would be ticket work for Atlas. Org stays lean per charter §10.

## Sources

- The Block: Polymarket & Kalshi monthly volume; MetaMask News "Kalshi vs Polymarket 2026" (June 2026: $31.5B vs $13.3B); defirate (Feb 2026: $9.9B vs $7.9B); Pew Research May 2026.
- Kalshi API docs (docs.kalshi.com) + `openapi.yaml` (98 endpoints, no leaderboard/user-trades).
- Polymarket docs (docs.polymarket.com/trading/fees) + docs.polymarket.us/fees (taker curve).
