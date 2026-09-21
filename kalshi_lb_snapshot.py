#!/usr/bin/env python3
"""Full Kalshi leaderboard snapshots + trader profile discovery."""
import json, os, urllib.request

COOKIES = open("/root/.hermes/secrets/kalshi_cookies.txt").read().strip()
CSRF = "yc9EHMAR1YBgJhUu42eYckfZSNhefCuaQIB1Qoc7G0s="
BASE = "https://api.elections.kalshi.com/v1"

headers = {"accept": "application/json", "x-csrf-token": CSRF,
           "origin": "https://kalshi.com", "referer": "https://kalshi.com/",
           "cookie": COOKIES, "user-agent": "HermesKalshiProbe/1.0"}

def api(path):
    req = urllib.request.Request(BASE + path, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())

# 1. Full leaderboard: volume monthly (top 100)
print("=== VOLUME LEADERBOARD (monthly, top 100) ===")
data = api("/social/leaderboard?metric_name=volume&limit=100&time_period=monthly")
rank_list = data.get("data", {}).get("rank_list", [])
print(f"Total entries: {len(rank_list)}")
for u in rank_list[:20]:
    anon = "🔒" if u.get("is_anonymous") else "👤"
    print(f"  {anon} #{u['rank']:3d} {u['nickname']:30s} volume=${u['value']:,}")
if len(rank_list) > 20:
    print(f"  ... and {len(rank_list)-20} more")

# Save full dump
json.dump(data, open("/tmp/kalshi_volume_lb.json", "w"), indent=1)
print(f"\nSaved to /tmp/kalshi_volume_lb.json")

# 2. Markets traded leaderboard (monthly)
print("\n=== MARKETS TRADED LEADERBOARD (monthly, top 100) ===")
data2 = api("/social/leaderboard?metric_name=num_markets_traded&limit=100&time_period=monthly")
rank_list2 = data2.get("data", {}).get("rank_list", [])
for u in rank_list2[:10]:
    anon = "🔒" if u.get("is_anonymous") else "👤"
    print(f"  {anon} #{u['rank']:3d} {u['nickname']:30s} markets={u['value']:,}")

# 3. Look for trader profile endpoint
print("\n=== SOCIAL PROFILE PROBE ===")
for path in [f"/social/profile/{rank_list[0]['social_id']}" if rank_list and rank_list[0].get('social_id') else "",
             "/social/profile", "/social/positions", "/social/following"]:
    try:
        url = BASE + path
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
            print(f"  GET {path}: HTTP 200 | keys={list(data.keys())[:8]}")
    except urllib.error.HTTPError as e:
        if e.code == 404: pass
        else:
            try: body = json.loads(e.read())
            except: body = {}
            print(f"  GET {path}: HTTP {e.code} | {body.get('error',{}).get('message','?')[:80]}")

# 4. Check what the volume_top1 profile page returns (by nickname)
print("\n=== PROFILE BY NICKNAME ===")
top = rank_list[0]['nickname'] if rank_list else "yummy.koala8920"
for path in [f"/social/user/{top}", f"/social/profile/{top}",
             f"/users/{top}/profile", f"/users/{top}/positions"]:
    try:
        url = BASE + path
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
            print(f"  GET {path}: HTTP 200 | {json.dumps(data)[:400]}")
    except urllib.error.HTTPError as e:
        pass