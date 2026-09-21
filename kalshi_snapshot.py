#!/usr/bin/env python3
"""Kalshi leaderboard snapshot with fresh WAF token from the cURL."""
import json, os, urllib.request

COOKIES = open("/root/.hermes/secrets/kalshi_cookies.txt").read().strip()
CSRF = "yc9EHMAR1YBgJhUu42eYckfZSNhefCuaQIB1Qoc7G0s="
WAF = open("/root/.hermes/secrets/kalshi_waf_token.txt").read().strip()
BASE = "https://api.elections.kalshi.com/v1"

headers = {"accept": "application/json", "x-csrf-token": CSRF,
           "x-aws-waf-token": WAF,
           "origin": "https://kalshi.com", "referer": "https://kalshi.com/",
           "cookie": COOKIES, "user-agent": "Mozilla/5.0"}

def api(path):
    req = urllib.request.Request(BASE + path, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())

try:
    data = api("/social/leaderboard?metric_name=volume&limit=20&time_period=monthly")
    rl = data.get("data", {}).get("rank_list", [])
    print(f"Volume monthly: {len(rl)} traders")
    for u in rl[:5]:
        print(f"  #{u['rank']:3d} {u['nickname']:30s} ${u['value']:,}")
except Exception as e:
    print(f"WAF probably expired: {e}")
    print("Need fresh session tokens")