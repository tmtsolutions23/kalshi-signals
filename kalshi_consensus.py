#!/usr/bin/env python3
"""Kalshi Smart-Money Scanner v2 (HERMES-011):
- Fresh-buy consensus (>=2 whales same market+side, 48h)
- Single-whale fresh moves (>= $2k)
- CURRENT HOLDINGS per visible whale (net buy/sell over 7-day window)
- HOLD consensus: >=2 whales holding same market+side
Auth: CEO session. AUTH_FAIL => tell user to paste a fresh cURL."""
import json, os, sys, urllib.request, urllib.error
from datetime import datetime, timezone, timedelta
from collections import defaultdict

TICKER_HOME = os.path.expanduser("~/.hermes/scripts")
if TICKER_HOME not in sys.path: sys.path.insert(0, TICKER_HOME)
from kalshi_ticker_decode import ticker_to_readable

SE = "/root/.hermes/secrets/"
BASE = "https://api.elections.kalshi.com/v1"
FRESH_WINDOW_H = 48
HOLD_WINDOW_H = 168          # 7 days of history for holdings reconstruction
MAX_PAGES = 20               # per trader
MIN_MOVE_USD = 2000
MIN_HOLD_USD = 5000

MONTHS = {"JAN":1,"FEB":2,"MAR":3,"APR":4,"MAY":5,"JUN":6,
          "JUL":7,"AUG":8,"SEP":9,"OCT":10,"NOV":11,"DEC":12}

def market_is_alive(ticker):
    """Check if the event date encoded in a Kalshi ticker is still current.
    Returns True if likely still open (within 36h), False if event passed (settled).
    Unknown-format tickers default to True."""
    import re
    m = re.search(r'-(\d{2})([A-Z]{3})(\d{2})', ticker)
    if not m:
        return True
    yy = 2000 + int(m.group(1))
    mon = MONTHS.get(m.group(2))
    if mon is None:
        return True
    dd = int(m.group(3))
    try:
        event_date = datetime(yy, mon, dd, tzinfo=timezone.utc)
    except ValueError:
        return True
    return datetime.now(timezone.utc) - event_date < timedelta(hours=36)

def load_tokens():
    cook = open(SE+"kalshi_cookies.txt").read()
    waf = open(SE+"kalshi_waf_token.txt").read()
    csrf = open(SE+"kalshi_csrf.txt").read()
    return cook, waf, csrf

cook, waf, csrf = load_tokens()
HD = {"accept":"application/json","x-csrf-token":csrf,"x-aws-waf-token":waf,
      "origin":"https://kalshi.com","referer":"https://kalshi.com/",
      "cookie":cook,"user-agent":"HermesKalshiProbe/1.0"}

def api(path):
    req = urllib.request.Request(BASE+path, headers=HD)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())

def safe_api(path):
    try:
        return api(path)
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise SystemExit("AUTH_FAIL: Kalshi session expired - paste a fresh cURL from the leaderboard page into #ceo-office")
        return {}
    except Exception:
        return {}

def leaderboard(metric, period="monthly", limit=60):
    d = safe_api(f"/social/leaderboard?metric_name={metric}&limit={limit}&time_period={period}")
    return d.get("rank_list", [])

def trade_history(nickname, hours=HOLD_WINDOW_H):
    """All trades within window (newest-first pagination)."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    out, cursor = [], None
    for _ in range(MAX_PAGES):
        path = f"/social/trades?nickname={nickname}&limit=1000"
        if cursor: path += f"&cursor={urllib.request.quote(cursor)}"
        d = safe_api(path)
        if not d: break
        if d.get("visibility_state") != "visible": break
        trades = d.get("trades", [])
        for t in trades:
            try:
                dt = datetime.fromisoformat(t["create_date"].replace("Z","+00:00"))
            except Exception:
                continue
            if dt < cutoff:
                return out  # passed window (newest-first)
            out.append({
                "ticker": t.get("ticker",""),
                "side": t.get("taker_side","?"),
                "count": float(t.get("count_fp",0) or 0),
                "price": float(t.get("price_dollars",0) or 0),
                "ts": t["create_date"],
                "who": t.get("taker_nickname","") or t.get("maker_nickname",""),
                "action": t.get("taker_action","?"),
            })
        cursor = d.get("cursor","")
        if not cursor: break
    return out

def position_delta(t, whale):
    """Net contract delta for the whale from this trade (maker = opposite of taker).
    Kalshi reports price_dollars = YES price even on NO-side trades; effective cost
    of a NO contract is (1 - yes_price)."""
    if t.get("who") != whale:
        return None
    d = t["count"] if t["action"] == "buy" else -t["count"]
    eff = t["price"] if t["side"] == "yes" else (1 - t["price"])
    return {"ticker": t["ticker"], "side": t["side"], "delta": d,
            "price": t["price"], "eff": eff, "ts": t["ts"]}

def holdings_for(history, whale):
    """Net per (ticker, side) + vwap. Returns {(ticker,side): {net, vwap, last_ts}}."""
    pos = defaultdict(lambda: {"net": 0.0, "cost": 0.0, "last_ts": ""})
    for t in history:
        pd = position_delta(t, whale)
        if not pd: continue
        key = (pd["ticker"], pd["side"])
        p = pos[key]
        if pd["delta"] > 0:
            p["cost"] += pd["delta"] * pd["eff"]
        p["net"] += pd["delta"]
        if pd["ts"] > p["last_ts"]: p["last_ts"] = pd["ts"]
    res = {}
    for key, p in pos.items():
        if abs(p["net"]) < 0.5: continue
        vwap = p["cost"] / p["net"] if p["net"] > 0 else 0.0
        res[key] = {"net": round(p["net"]), "vwap": round(vwap, 4), "last_ts": p["last_ts"]}
    return res

# 1. Trader pool
pool = {}
for metric in ["volume","num_markets_traded","projected_pnl"]:
    for u in leaderboard(metric, "monthly", 60):
        pool.setdefault(u["nickname"], u["rank"])

# 2. Visibility scan (top 120)
ordered = sorted(pool.items(), key=lambda kv: kv[1])
visible = {}
for nick, rank in ordered[:120]:
    d = safe_api(f"/social/trades?nickname={nick}&limit=1")
    if d.get("visibility_state") == "visible":
        visible[nick] = rank

def classify_whales(histories, holdings_map):
    """Classify style from trade history.
    - arb: trades BOTH sides of the same ticker >= 25% of markets (arb/hedge signature)
    - scalper: very short holds (< 1h avg) with >= 20 trades (market-maker / noise flow)
    - directional: holds positions (open spans count from entry to NOW, not 0)
    Only 'directional' whales produce signals."""
    now = datetime.now(timezone.utc)
    out = {}
    for nick, hist in histories.items():
        sides_by_ticker = defaultdict(set)
        first_ts, last_ts = {}, {}
        net = defaultdict(float)
        n_trades = len(hist)
        for t in hist:
            pd = position_delta(t, nick)
            if not pd: continue
            key = (pd["ticker"], pd["side"])
            sides_by_ticker[pd["ticker"]].add(pd["side"])
            net[key] += pd["delta"]
            if key not in first_ts or t["ts"] < first_ts[key]: first_ts[key] = t["ts"]
            if key not in last_ts or t["ts"] > last_ts[key]: last_ts[key] = t["ts"]
        if not first_ts:
            out[nick] = {"label": "directional", "mixed": 0.0, "avg_hold_h": 0.0, "markets": 0, "trades": 0}
            continue
        mixed = sum(1 for s in sides_by_ticker.values() if len(s) >= 2) / len(sides_by_ticker)
        spans = []
        for key, ft in first_ts.items():
            try:
                f = datetime.fromisoformat(ft.replace("Z","+00:00"))
            except Exception:
                continue
            if abs(net[key]) > 0.5 and key in holdings_map.get(nick, {}):
                # OPEN position: held since entry until NOW
                span = (now - f).total_seconds() / 3600
            else:
                l = last_ts.get(key, ft)
                try:
                    e = datetime.fromisoformat(l.replace("Z","+00:00"))
                except Exception:
                    continue
                span = max((e - f).total_seconds() / 3600, 0.0)
            spans.append(span)
        avg_h = sum(spans) / len(spans) if spans else 0.0
        if mixed >= 0.25:
            label = "arb"
        elif n_trades >= 20 and avg_h < 1.0:
            label = "scalper"
        else:
            label = "directional"
        out[nick] = {"label": label, "mixed": round(mixed, 2), "avg_hold_h": round(avg_h, 1),
                     "markets": len(sides_by_ticker), "trades": n_trades}
    return out


fresh_consensus = defaultdict(list)   # (ticker,side) -> [(whale, count, price, ts)]
hold_positions = defaultdict(list)    # (ticker,side) -> [(whale, net, vwap)]
now_utc = datetime.now(timezone.utc)
fresh_cutoff = (now_utc - timedelta(hours=FRESH_WINDOW_H)).isoformat().replace("+00:00","Z")[:19]

histories = {}
holdings_map = {}
for nick in visible:
    hist = trade_history(nick)
    histories[nick] = hist
    holdings = holdings_for(hist, nick)
    holdings_map[nick] = holdings
    for t in hist:
        pd = position_delta(t, nick)
        if pd and pd["delta"] > 0 and t["ts"][:19] >= fresh_cutoff:
            fresh_consensus[(t["ticker"], t["side"])].append((nick, pd["delta"], t["price"], t["ts"]))
    for key, h in holdings.items():
        hold_positions[key].append((nick, h["net"], h["vwap"]))

# 3b. Whale classification — only DIRECTIONAL whales count as signal
classification = classify_whales(histories, holdings_map)
directional = {n for n, c in classification.items() if c["label"] == "directional"}
watch = classification

# 4. Signals — filtered to DIRECTIONAL whales only
dir_positions = defaultdict(list)
for k, v in hold_positions.items():
    dir_positions[k] = [e for e in v if e[0] in directional]
hold_positions = dir_positions

fired = sum(1 for k, v in fresh_consensus.items() if len({e[0] for e in v if e[0] in directional}) >= 2)
moves = []
for (tick, side), entries in fresh_consensus.items():
    de = [e for e in entries if e[0] in directional]
    if not de: continue
    tot = sum(e[1] * (e[2] if side == "yes" else (1 - e[2])) for e in de)
    if tot >= MIN_MOVE_USD:
        moves.append((tick, side, de, tot))
moves.sort(key=lambda x: -x[3])

hold_consensus = []
for (tick, side), entries in hold_positions.items():
    whales = {e[0] for e in entries}
    if len(whales) >= 2:
        tot_usd = sum(e[1] * e[2] for e in entries if e[1] > 0)
        hold_consensus.append((tick, side, entries, tot_usd))
hold_consensus.sort(key=lambda x: -x[3])

big_holds = []
for (tick, side), entries in hold_positions.items():
    for whale, net, vwap in entries:
        usd = net * vwap
        if net > 0 and usd >= MIN_HOLD_USD:
            big_holds.append((tick, side, whale, net, vwap, usd))
big_holds.sort(key=lambda x: -x[5])

# 3c. Filter settled markets — only show markets whose event is still active
moves = [(t, s, e, tot) for (t, s, e, tot) in moves if market_is_alive(t)]
hold_consensus = [(t, s, e, tot) for (t, s, e, tot) in hold_consensus if market_is_alive(t)]
big_holds = [(t, s, w, n, v, u) for (t, s, w, n, v, u) in big_holds if market_is_alive(t)]
# Recompute fired — consensus requires at least 2 directional whales on same live market+side
fired = sum(1 for (tick, side), entries in fresh_consensus.items()
            if len({e[0] for e in entries if e[0] in directional}) >= 2 and market_is_alive(tick))

# 5. Output — ONLY if there are copy-trade signals
out = []
if fired:
    out.append(f"**[KALSHI CONSENSUS]** {fired} multi-whale fresh-buy signal(s)")
if moves:
    out.append(f"**[KALSHI WHALE MOVES]** {len(moves)} notable fresh buy(s) ≥${MIN_MOVE_USD:,}")
    for tick, side, entries, tot in moves[:6]:
        names = " + ".join(sorted({e[0] for e in entries}))
        out.append(f"🐋 {side.upper()} {ticker_to_readable(tick)} — ${tot:,.0f} ({names})")
if hold_consensus:
    out.append(f"**[KALSHI HOLD CONSENSUS]** {len(hold_consensus)} market(s) where ≥2 whales currently hold the same side")
    for tick, side, entries, tot in hold_consensus[:5]:
        names = " + ".join(sorted({e[0] for e in entries}))
        out.append(f"📦 {side.upper()} {ticker_to_readable(tick)} — ~${tot:,.0f} combined ({names})")
if big_holds:
    out.append(f"**[KALSHI BIG HOLDS]** {len(big_holds)} position(s) ≥${MIN_HOLD_USD:,}")
    for tick, side, whale, net, vwap, usd in big_holds[:6]:
        out.append(f"📦 {whale}: {'YES' if side=='yes' else 'NO'} {ticker_to_readable(tick)} @ ${vwap:.3f} ≈ ${usd:,.0f}")
if out:
    print("\n".join(out))

if os.environ.get("MANUAL") == "1":
    json.dump({"visible": list(visible), "holdings": [
        {"ticker": k[0], "side": k[1], "holders": [[e[0], e[1], e[2]] for e in v]}
        for k, v in hold_positions.items()]}, open("/tmp/kalshi_state.json","w"), indent=1)
    print(f"\n(manual) visible whales: {list(visible)}")