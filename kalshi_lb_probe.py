#!/usr/bin/env python3
"""Kalshi leaderboard probe: test the social endpoint with CEO's session cookies."""
import json, os, urllib.request

COOKIES = open("/root/.hermes/secrets/kalshi_cookies.txt").read().strip()
CSRF = "yc9EHMAR1YBgJhUu42eYckfZSNhefCuaQIB1Qoc7G0s="
BASE = "https://api.elections.kalshi.com/v1/social/leaderboard"

metrics = ["num_markets_traded", "total_volume", "profit_loss", "total_trades"]
periods = ["weekly", "monthly", "all"]

headers = {
    "accept": "application/json",
    "x-csrf-token": CSRF,
    "origin": "https://kalshi.com",
    "referer": "https://kalshi.com/",
    "cookie": COOKIES,
    "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
}

for metric in metrics:
    for period in periods:
        url = f"{BASE}?metric_name={metric}&limit=20&time_period={period}"
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.loads(r.read().decode())
            users = data.get("data", data.get("leaderboard", data.get("users", [])))
            print(f"\n🍀 {metric} / {period}: HTTP {r.status} | {len(users)} traders")
            if users:
                # Show keys of first user
                print(f"   user keys: {list(users[0].keys())[:12]}")
                for u in users[:4]:
                    username = u.get("username", u.get("name", "?"))
                    rank = u.get("rank", u.get("position", "?"))
                    val = u.get("metric_value", u.get("value", u.get("score", "?")))
                    print(f"   #{rank} {username} -> {metric}={val}")
        except urllib.error.HTTPError as e:
            body = e.read()
            print(f"\n❌ {metric} / {period}: HTTP {e.code}")
            if body:
                try: print(f"   {json.dumps(json.loads(body))[:200]}")
                except: print(f"   raw: {str(body[:100])}")
        except Exception as e:
            print(f"\n❌ {metric} / {period}: {e}")