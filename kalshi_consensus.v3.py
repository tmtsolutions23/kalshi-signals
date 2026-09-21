#!/usr/bin/env python3
"""Kalshi Smart-Money Scanner v3 (HERMES-011) — live 2026-09-20.

Pipeline: monthly leaderboards -> visible traders -> canonical fill analysis ->
  FRESH BUYS  (<=48h, aggressive taker fills only, normalized to long side)
  HOLDINGS    (7-day net book reconstruction, all fills incl. passive)
Whale styles: arb / scalper / directional (only directional whales emit signals).
Signals:
  [KALSHI CONSENSUS]   >=2 directional whales, same (ticker, long-side), 48h
  [KALSHI WHALE MOVES] single directional whale fresh buy >= $2,000
  [KALSHI HOLD CONSENSUS]  >=2 whales now net-long the same side (live markets)
  [KALSHI BIG HOLDS]   single whale position >= $5,000
Markets enriched via PUBLIC api (title/event); settled ("finalized") dropped.
Fresh + holds outputs deduped across runs (state file, 48h slide).
Auth: CEO session cookies+WAF+CSRF. AUTH_FAIL -> paste fresh cURL.

Fill semantics (verified live against /social/trades, 2026-09-20):
- count_fp / price_dollars are STRINGS; price_dollars is the YES price even for
  NO-side trades. Eff entry price: YES-side = p, NO-side = 1-p.
- Each row describes the TAKER. Whale is TAKER when taker_nickname==whale;
  whale is MAKER (opposite action) when maker_nickname==whale; taker_nickname
  may be "" (anonymous taker): those rows are PASSIVE for the whale.
- sell NO == buy YES, sell YES == buy NO (normalized to the side the whale
  becomes LONG).
- limit param is clamped to 100 fills/page; paginate with cursor, newest-first.
"""
import json, os, urllib.request, urllib.error
from datetime import datetime, timezone, timedelta
from collections import defaultdict

SE = "/root/.hermes/secrets/"
SOCIAL = "https://api.elections.kalshi.com/v1"
PUBLIC = "https://external-api.kalshi.com/trade-api/v2"
STATE = os.path.expanduser("~/.hermes/scripts/.kalshi_consensus_state.json")
OUT = "/tmp/kalshi_consensus.json"

FRESH_H = 48
HOLD_H = 168                              # 7-day holdings window
VIS_CAP = 120
MAX_PAGES = 40                            # 100 fills/page, early-break at window edge
MIN_MOVE_USD = 2000.0
MIN_CONSENSUS_USD = 100.0
MIN_HOLD_USD = 5000.0
LIVE_STATUS = {"active", "closed"}

MANUAL = os.environ.get("MANUAL") == "1"


def load_tokens():
    cook = open(SE + "kalshi_cookies.txt").read().strip()
    waf = open(SE + "kalshi_waf_token.txt").read().strip()
    csrf = open(SE + "kalshi_csrf.txt").read().strip()
    return cook, waf, csrf


cook, waf, csrf = load_tokens()
HD = {"accept": "application/json", "x-csrf-token": csrf, "x-aws-waf-token": waf,
      "origin": "https://kalshi.com", "referer": "https://kalshi.com/",
      "cookie": cook, "user-agent": "Mozilla/5.0"}


def api(path):
    req = urllib.request.Request(SOCIAL + path, headers=HD)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())


def safe_api(path):
    try:
        return api(path)
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise SystemExit("AUTH_FAIL: Kalshi session expired - paste a fresh cURL from the leaderboard page (kalshi.com/social/leaderboard -> F5 -> first 'leaderboard' request)")
        return {}
    except Exception:
        return {}


def leaderboard(metric, period="monthly", limit=60):
    d = safe_api(f"/social/leaderboard?metric_name={metric}&limit={limit}&time_period={period}")
    return d.get("rank_list", [])


def opp(side):
    return "no" if side == "yes" else "yes"


def fill_rows(nickname, cutoff):
    """All raw fills newer than cutoff (ISO string compare; both emit %fZ)."""
    out, cursor = [], None
    for _ in range(MAX_PAGES):
        path = f"/social/trades?nickname={nickname}&limit=100"
        if cursor:
            path += f"&cursor={urllib.request.quote(cursor)}"
        d = safe_api(path)
        if not d:
            break
        if d.get("visibility_state") != "visible":
            break
        trades = d.get("trades", [])
        if not trades:
            break
        done = False
        for t in trades:
            if t.get("create_date", "") < cutoff:   # newest-first: window passed
                done = True
                break
            out.append(t)
        cursor = d.get("cursor", "")
        if done or not cursor:
            break
    return out


def whale_fill(nick, t):
    """Canonical transform from whale nick's perspective.
    Returns {ticker, side(long), count, cost, price, ts, aggressive} or None.
    cost = count*eff where eff = YES-equivalent entry price (p for long YES, 1-p for long NO)."""
    if t.get("taker_nickname") == nick:
        whale_action = t.get("taker_action", "")
        traded_side = t.get("taker_side", "")
        aggressive = True
    elif t.get("maker_nickname") == nick:
        whale_action = opp(t.get("taker_action", ""))
        traded_side = t.get("taker_side", "")
        aggressive = False
    else:
        return None
    if whale_action not in ("buy", "sell") or traded_side not in ("yes", "no"):
        return None
    long_side = traded_side if whale_action == "buy" else opp(traded_side)
    count = float(t.get("count_fp", 0) or 0)
    yes_price = float(t.get("price_dollars", 0) or 0)
    eff = yes_price if long_side == "yes" else (1.0 - yes_price)
    if count <= 0 or eff <= 0:
        return None
    return {"ticker": t.get("ticker", ""), "side": long_side, "count": count,
            "cost": count * eff, "price": eff, "ts": t.get("create_date", ""),
            "aggressive": aggressive}


_mkt_cache = {}


def enrich(ticker):
    if ticker in _mkt_cache:
        return _mkt_cache[ticker]
    rec = {"status": None, "title": ticker, "event": ""}
    try:
        hd = {"accept": "application/json", "user-agent": "Mozilla/5.0"}
        req = urllib.request.Request(PUBLIC + f"/markets/{ticker}", headers=hd)
        with urllib.request.urlopen(req, timeout=10) as r:
            m = json.loads(r.read().decode()).get("market", {})
        rec["status"] = m.get("status")
        rec["title"] = m.get("title") or ticker
        ev = m.get("event_ticker")
        if ev:
            try:
                req = urllib.request.Request(PUBLIC + f"/events/{ev}", headers=hd)
                with urllib.request.urlopen(req, timeout=10) as r:
                    e = json.loads(r.read().decode()).get("event", {})
                rec["event"] = e.get("title") or ""
            except Exception:
                pass
    except Exception:
        pass
    _mkt_cache[ticker] = rec
    return rec


def load_state():
    try:
        return json.load(open(STATE))
    except Exception:
        return {}


def save_state(st):
    json.dump(st, open(STATE, "w"))


# ---- 1+2. pool & visibility ----
pool = {}
for metric in ["volume", "num_markets_traded", "projected_pnl"]:
    for u in leaderboard(metric, "monthly", 60):
        pool.setdefault(u["nickname"], u["rank"])
ordered = sorted(pool.items(), key=lambda kv: kv[1])

visible = {}
for nick, rank in ordered[:VIS_CAP]:
    d = safe_api(f"/social/trades?nickname={nick}&limit=1")
    if d.get("visibility_state") == "visible":
        visible[nick] = rank
if MANUAL:
    print(f"pool={len(pool)} visible={len(visible)}")

# ---- 3. histories (canonical) ----
now_utc = datetime.now(timezone.utc)
fresh_cut = (now_utc - timedelta(hours=FRESH_H)).isoformat().replace("+00:00", "Z")
hold_cut = (now_utc - timedelta(hours=HOLD_H)).isoformat().replace("+00:00", "Z")

histories = {}        # nick -> [canonical fill]
fresh = defaultdict(list)   # (ticker, side) -> [canonical aggressive fill]
holds_by_nick = {}    # nick -> {(ticker, side): {net, vwap, first_ts, last_ts}}

for nick in visible:
    fills = []
    for t in fill_rows(nick, hold_cut):
        f = whale_fill(nick, t)
        if f:
            fills.append(f)
    histories[nick] = fills

    # holdings reconstruction (net long counts per (ticker, side), all fills)
    pos = defaultdict(lambda: {"net": 0.0, "cost": 0.0, "first": "", "last": ""})
    for f in fills:
        key = (f["ticker"], f["side"])
        p = pos[key]
        p["net"] += f["count"]
        p["cost"] += f["cost"]
        if not p["first"] or f["ts"] < p["first"]:
            p["first"] = f["ts"]
        if f["ts"] > p["last"]:
            p["last"] = f["ts"]
    hh = {}
    for key, p in pos.items():
        if abs(p["net"]) < 0.5:
            continue
        vwap = p["cost"] / p["net"] if p["net"] > 0 else 0.0
        hh[key] = {"net": round(p["net"]), "vwap": round(vwap, 4),
                   "first": p["first"], "last": p["last"]}
    holds_by_nick[nick] = hh

# ---- 3b. whale style classification (canonical sides fix the raw-side bug) ----
classification = {}
for nick, fills in histories.items():
    if not fills:
        classification[nick] = {"label": "directional", "mixed": 0.0, "avg_hold_h": 0.0,
                                "markets": 0, "trades": 0}
        continue
    sides_by_ticker = defaultdict(set)
    span_open = {}        # (ticker, side) -> first ts
    span_closed = {}      # (ticker, side) -> last ts
    for f in fills:
        key = (f["ticker"], f["side"])
        sides_by_ticker[f["ticker"]].add(f["side"])
        if key not in span_open or f["ts"] < span_open[key]:
            span_open[key] = f["ts"]
        if key not in span_closed or f["ts"] > span_closed[key]:
            span_closed[key] = f["ts"]
    mixed = sum(1 for s in sides_by_ticker.values() if len(s) >= 2) / len(sides_by_ticker)
    hh = holds_by_nick[nick]
    spans = []
    for key, ft in span_open.items():
        try:
            f0 = datetime.fromisoformat(ft.replace("Z", "+00:00"))
        except Exception:
            continue
        if abs(hh.get(key, {}).get("net", 0)) > 0.5:
            span = (now_utc - f0).total_seconds() / 3600      # still open -> held to now
        else:
            try:
                l0 = datetime.fromisoformat(span_closed[key].replace("Z", "+00:00"))
            except Exception:
                continue
            span = max((l0 - f0).total_seconds() / 3600, 0.0)
        spans.append(span)
    avg_h = sum(spans) / len(spans) if spans else 0.0
    n_trades = len(fills)
    if mixed >= 0.25:
        label = "arb"
    elif n_trades >= 20 and avg_h < 1.0:
        label = "scalper"
    else:
        label = "directional"
    classification[nick] = {"label": label, "mixed": round(mixed, 2), "avg_hold_h": round(avg_h, 1),
                            "markets": len(sides_by_ticker), "trades": n_trades}
if MANUAL:
    for n, c in sorted(classification.items()):
        print(f"   {n:24s} {c['label']:10s} mixed={c['mixed']:.0%} avg_hold={c['avg_hold_h']}h mkts={c['markets']} trades={c['trades']}")

directional = {n for n, c in classification.items() if c["label"] == "directional"}

# ---- 4. signals (directional whales only) ----
fresh_named = defaultdict(list)
for nick in directional:
    for t in fill_rows(nick, fresh_cut):
        f = whale_fill(nick, t)
        if f and f["aggressive"]:
            fresh_named[(f["ticker"], f["side"])].append({**f, "nick": nick})

consensus, moves = [], []
for (ticker, side), fills in fresh_named.items():
    per_w = defaultdict(list)
    for f in fills:
        per_w[f["nick"]].append(f)
    entries = [(n, sum(x["cost"] for x in fs), fs) for n, fs in per_w.items()]
    total = sum(p for _, p, _ in entries)
    if len(entries) >= 2 and total >= MIN_CONSENSUS_USD:
        consensus.append((ticker, side, entries, total))
    elif total >= MIN_MOVE_USD:
        moves.append((ticker, side, entries, total))
consensus.sort(key=lambda x: -x[3])
moves.sort(key=lambda x: -x[3])

hold_pos = defaultdict(list)
for nick in directional:
    for (ticker, side), h in holds_by_nick[nick].items():
        hold_pos[(ticker, side)].append((nick, h["net"], h["vwap"]))

# ---- 5. enrich / settled filter / dedupe ----
state = load_state()
state = {sig: ts for sig, ts in state.items()
         if now_utc - datetime.fromisoformat(ts) < timedelta(hours=FRESH_H)}
fired_c, fired_m = [], []
for ticker, side, entries, total in consensus:
    m = enrich(ticker)
    if m["status"] not in LIVE_STATUS:
        continue
    sig = f"C|{ticker}|{side}|{'|'.join(sorted(n for n, _, _ in entries))}"
    if sig in state:
        continue
    fired_c.append((ticker, side, entries, total, m))
    state[sig] = now_utc.isoformat()
for ticker, side, entries, total in moves:
    m = enrich(ticker)
    if m["status"] not in LIVE_STATUS:
        continue
    sig = f"S|{ticker}|{side}|{'|'.join(sorted(n for n, _, _ in entries))}"
    if sig in state:
        continue
    fired_m.append((ticker, side, entries, total, m))
    state[sig] = now_utc.isoformat()

hold_consensus, big_holds = [], []
for (ticker, side), entries in hold_pos.items():
    m = enrich(ticker)
    if m["status"] not in LIVE_STATUS:
        continue
    if len(entries) >= 2:
        tot_usd = sum(e[1] * e[2] for e in entries if e[1] > 0)
        if tot_usd > 0:
            sig = f"H|{ticker}|{side}|{','.join(f'{n}:{int(net)}' for n, net, _ in sorted(entries))}"
            if sig not in state:
                hold_consensus.append((ticker, side, entries, tot_usd, m))
                state[sig] = now_utc.isoformat()
    for whale, net, vwap in entries:
        usd = net * vwap
        if net > 0 and usd >= MIN_HOLD_USD:
            sig = f"B|{ticker}|{side}|{whale}|{int(net)}"
            if sig not in state:
                big_holds.append((ticker, side, whale, net, vwap, usd, m))
                state[sig] = now_utc.isoformat()
hold_consensus.sort(key=lambda x: -x[3])
big_holds.sort(key=lambda x: -x[5])
save_state(state)

# ---- 6. output ----
def fmt(m):
    t = m["title"] if len(m["title"]) <= 70 else m["title"][:67] + "..."
    ev = f" — {m['event'][:45]}" if m["event"] else ""
    return f"{t}{ev} [{m['status']}]"


out = []
wl_items = sorted(classification.items())
wl = " · ".join(f"{n}={c['label']}({c['mixed']:.0%}m,{c['avg_hold_h']:.0f}h)" for n, c in wl_items)
if len(wl) > 1500:
    wl = wl[:1497] + "..."
out.append(f"*Watchlist: {wl}*")
if fired_c:
    out.append(f"**[KALSHI CONSENSUS]** {len(fired_c)} multi-whale fresh-buy signal(s) · {FRESH_H}h")
    for ticker, side, entries, total, m in fired_c[:6]:
        names = " + ".join(n for n, _, _ in entries)
        out.append(f"🐋 {side.upper()} {fmt(m)}")
        out.append(f"   {len(entries)} whales · ${total:,.0f} combined · {names}")
if fired_m:
    out.append(f"**[KALSHI WHALE MOVES]** {len(fired_m)} fresh buy(s) ≥${MIN_MOVE_USD:,.0f}")
    for ticker, side, entries, total, m in fired_m[:6]:
        n, prem, fs = entries[0]
        out.append(f"🐋 {side.upper()} {fmt(m)}")
        out.append(f"   {n}: ${prem:,.0f} ({len(fs)} fills, last {fs[-1]['ts'][:16]}Z)")
if hold_consensus:
    out.append(f"**[KALSHI HOLD CONSENSUS]** {len(hold_consensus)} market(s) ≥2 whales same side")
    for ticker, side, entries, tot, m in hold_consensus[:5]:
        names = " + ".join(sorted({e[0] for e in entries}))
        out.append(f"📦 {side.upper()} {fmt(m)} — ≈${tot:,.0f} ({names})")
if big_holds:
    out.append(f"**[KALSHI BIG HOLDS]** {len(big_holds)} position(s) ≥${MIN_HOLD_USD:,.0f}")
    for ticker, side, whale, net, vwap, usd, m in big_holds[:6]:
        out.append(f"📦 {whale}: {net:,.0f} {side.upper()} {fmt(m)} @ ${vwap:.3f} ≈${usd:,.0f}")
print("\n".join(out))

json.dump({
    "visible": list(visible),
    "classification": classification,
    "fresh": [{"ticker": k[0], "side": k[1],
               "fills": [[f["nick"], round(f["cost"], 2), f["count"], f["ts"]] for f in v]}
              for k, v in fresh_named.items()],
    "holds": [{"ticker": k[0], "side": k[1], "holders": [[e[0], e[1], e[2]] for e in v]}
              for k, v in hold_pos.items()],
}, open(OUT, "w"), indent=1)

if MANUAL:
    print("\n=== FRESH (aggressive, directional whales) ===")
    for (ticker, side), fills in sorted(fresh_named.items(), key=lambda kv: -sum(f["cost"] for f in kv[1]))[:15]:
        tot = sum(f["cost"] for f in fills)
        print(f"  {side.upper():3s} ${tot:>10,.0f}  {ticker[:45]}")
        for f in fills:
            print(f"      {f['nick']}: {f['count']:,.0f} @ ${f['price']:.3f} = ${f['cost']:,.0f}  {f['ts'][:16]}")
    print("\n=== HOLDS (directional, by value) ===")
    seen = set()
    rows = []
    for (ticker, side), entries in hold_pos.items():
        for whale, net, vwap in entries:
            if net * vwap >= 100:
                rows.append((ticker, side, whale, net, vwap))
    for ticker, side, whale, net, vwap in sorted(rows, key=lambda r: -(r[3] * r[4]))[:25]:
        print(f"  {whale:22s} {net:>9,.0f} {side.upper():3s} {ticker[:40]:40s} @ ${vwap:.3f} = ${net*vwap:,.0f}")