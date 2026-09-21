#!/usr/bin/env python3
"""Broader Kalshi leaderboard probe - try all metric names and look at response structure."""
import json, os, urllib.request

COOKIES = open("/root/.hermes/secrets/kalshi_cookies.txt").read().strip()
CSRF = "yc9EHMAR1YBgJhUu42eYckfZSNhefCuaQIB1Qoc7G0s="
BASE = "https://api.elections.kalshi.com/v1/social/leaderboard"

# Try all plausible metric names
metrics = ["num_markets_traded", "markets_traded", "traded_markets",
           "volume", "total_volume", "volume_traded",
           "profit", "pnl", "profit_loss", "net_profit", "returns",
           "trades", "total_trades", "num_trades", "count_trades",
           "win_rate", "winrate", "accuracy", "score",
           "rank", "rating", "elo", "points",
           "num_markets", "market_count"]
periods = ["weekly", "monthly"]

headers = {"accept": "application/json", "x-csrf-token": CSRF,
           "origin": "https://kalshi.com", "referer": "https://kalshi.com/",
           "cookie": COOKIES, "user-agent": "Mozilla/5.0"}

for metric in metrics:
    for period in periods:
        url = f"{BASE}?metric_name={metric}&limit=5&time_period={period}"
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read().decode())
            items = data.get("data") or data.get("leaderboard") or data.get("results") or []
            n = len(items) if isinstance(items, list) else 0
            if n > 0 or data.get("data") is not None:
                print(f"✅ {metric} ({period}): HTTP 200 | items={n}")
                if n > 0:
                    print(f"   first item: {json.dumps(items[0], indent=1)[:300]}")
            else:
                print(f"✅ {metric} ({period}): HTTP 200 | empty (data={repr(data)[:200]})")
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            msg = json.loads(body).get("error", {}).get("message", body[:60]) if body else "?"
            if "oneof" not in msg and e.code != 400:
                print(f"❌ {metric} ({period}): HTTP {e.code} | {msg}")

# Also check if there's a different social endpoint for profiles/positions
print("\n=== Profile/position endpoints ===")
for path in ["social/profile", "social/positions", "social/following",
             "portfolio/positions", "profile/top-traders"]:
    url = f"https://api.elections.kalshi.com/v1/{path}?limit=3"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            code, body = r.status, r.read().decode()
            print(f"  GET /v1/{path}: HTTP {code} | {repr(body[:200])}")
    except urllib.error.HTTPError as e:
        pass  # expected for most