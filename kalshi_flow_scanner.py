#!/usr/bin/env python3
"""Kalshi Flow Scanner v4. 
Phase 1: ALL block trades since last scan (paginated, rare).
Phase 2: sample the latest 1000 standard trades, emit only the very largest.
Fast: < 2 seconds total. No auth needed."""
import json, os, sys, urllib.request, urllib.error
from datetime import datetime, timezone

TICKER_HOME = os.path.expanduser("~/.hermes/scripts")
if TICKER_HOME not in sys.path: sys.path.insert(0, TICKER_HOME)
from kalshi_ticker_decode import ticker_to_readable

BASE = "https://external-api.kalshi.com/trade-api/v2/markets/trades"
STATE = os.path.expanduser("~/.hermes/scripts/.kalshi_flow_state.json")
headers = {"User-Agent": "HermesKalshiProbe/1.0", "accept": "application/json"}
NOW_S = int(datetime.now(timezone.utc).timestamp())

state = {"last_ts": NOW_S - 3600, "alerts_24h": 0, "last_reset": NOW_S}
try:
    s = json.load(open(STATE))
    state["last_ts"] = s.get("last_ts", NOW_S - 3600)
    state["alerts_24h"] = s.get("alerts_24h", 0)
    state["last_reset"] = s.get("last_reset", 0)
except Exception: pass
if NOW_S - state["last_reset"] > 86400:
    state["alerts_24h"] = 0; state["last_reset"] = NOW_S

MAX_ALERTS = 15
alerts = []

def fetch(url):
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode())

def premium_of(t):
    count = float(t.get("count_fp", 0) or 0)
    side = t.get("taker_side", "?")
    if side == "no":
        # NO contract: actual premium = count * no_price
        p = float(t.get("no_price_dollars", 0))
    else:
        # YES contract: actual premium = count * yes_price
        p = float(t.get("yes_price_dollars", 0)) or float(t.get("yes_price_fp", 0))
    return count * p

def alert(t, is_block):
    if state["alerts_24h"] >= MAX_ALERTS: return
    p = premium_of(t)
    ticker = t.get("ticker", "?")
    taker = t.get("taker_side", "?")
    alerts.append({"ticker": ticker, "premium": round(p),
                  "side": taker, "is_block": is_block,
                  "ts": t["created_time"],
                  "count": int(float(t.get("count_fp",0)))})
    state["alerts_24h"] += 1

# Phase 1: Block trades — full pagination from last_ts
last_ts = state["last_ts"]
new_last_ts = last_ts
pages = 0
block_total = 0
cursor = None
while pages < 200:
    params = f"limit=1000&min_ts={last_ts}&is_block_trade=true"
    if cursor: params += f"&cursor={urllib.request.quote(cursor)}"
    try:
        data = fetch(f"{BASE}?{params}")
    except Exception as e:
        break
    trades = data.get("trades", [])
    if not trades: break
    pages += 1
    for t in trades:
        block_total += 1
        ts = int(datetime.fromisoformat(t["created_time"].replace("Z","+00:00")).timestamp())
        if ts <= last_ts: break
        if ts > new_last_ts: new_last_ts = ts
        if premium_of(t) >= 10000:
            alert(t, True)
    cursor = data.get("cursor", "")
    if not cursor: break

# Phase 2: Standard trades — 1-page sample, alert the single biggest (if >$2k)
best = None
try:
    data = fetch(f"{BASE}?limit=1000")
    best = max(data.get("trades",[]), key=lambda t: premium_of(t)) if data.get("trades") else None
    if best:
        ts = int(datetime.fromisoformat(best["created_time"].replace("Z","+00:00")).timestamp())
        if ts > new_last_ts: new_last_ts = ts
        p = premium_of(best)
        if p >= 2000 and not best.get("is_block_trade"):
            alert(best, False)
except Exception: pass

state["last_ts"] = max(new_last_ts, last_ts + 1)
json.dump(state, open(STATE, "w"))

print(f"[KALSHI FLOW] {block_total} block trades ({pages} pages), top standard=${round(max([premium_of(t) for t in ([] if not best else [best])], default=0)):,}: {len(alerts)} alert(s)" if best else f"[KALSHI FLOW] {block_total} block trades ({pages} pages), top standard: N/A: {len(alerts)} alert(s)")
for a in alerts[:8]:
    flag = "🟦 BLOCK" if a["is_block"] else "🟡 LARGE"
    readable = ticker_to_readable(a["ticker"])
    direction = {"yes": "BUYING", "no": "SELLING/AGAINST"}.get(a["side"], "BETTING ON")
    print(f"  {flag} ${a['premium']:,} {direction} {readable[:60]}")
if len(alerts) > 8: print(f"  ... and {len(alerts)-8} more")
if not alerts: print("  (no alerts — standard trades are small in this window)")