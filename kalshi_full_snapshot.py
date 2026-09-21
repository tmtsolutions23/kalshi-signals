#!/usr/bin/env python3
"""Extract fresh Kalshi session tokens from cURL, run full leaderboard snapshot."""
import json, os, re, urllib.request

doc = open('/root/.hermes/cache/documents/doc_b91e1c060b19_message.txt').read()

# Extract cookies, WAF token, CSRF
m = re.search(r'-b\s*\^?"([^"]+)\^?"', doc)
cookies = m.group(1) if m else ""
m2 = re.search(r'x-aws-waf-token:\s*([^\s^"]+)', doc)
waf = m2.group(1) if m2 else ""
m3 = re.search(r'x-csrf-token:\s*([^\s^"]+)', doc)
csrf = m3.group(1) if m3 else ""

open('/root/.hermes/secrets/kalshi_cookies.txt', 'w').write(cookies)
open('/root/.hermes/secrets/kalshi_waf_token.txt', 'w').write(waf)
open('/root/.hermes/secrets/kalshi_csrf.txt', 'w').write(csrf)
print(f"Cookies: {len(cookies)} chars\nWAF: {waf[:50]}...\nCSRF: {csrf[:40]}...")

BASE = "https://api.elections.kalshi.com/v1"
hdrs = {"accept": "application/json", "x-csrf-token": csrf, "x-aws-waf-token": waf,
        "origin": "https://kalshi.com", "referer": "https://kalshi.com/",
        "cookie": cookies, "user-agent": "Mozilla/5.0"}

def api(path):
    req = urllib.request.Request(BASE + path, headers=hdrs)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())

# Snapshot all three metrics, weekly + monthly
metrics = ["volume", "num_markets_traded", "projected_pnl"]
periods = ["weekly", "monthly"]
all_data = {}

for m in metrics:
    for p in periods:
        key = f"{m}_{p}"
        data = api(f"/social/leaderboard?metric_name={m}&limit=100&time_period={p}")
        rl = data.get("data", {}).get("rank_list", [])
        all_data[key] = rl
        top = rl[0] if rl else None
        print(f"\n📊 {m} ({p}): {len(rl)} traders")
        if top:
            print(f"  #1 {top['nickname'][:25]:25s} value={top['value']:,} {'👤' if not top.get('is_anonymous') else '🔒'}")
        for u in rl[:5]:
            print(f"  #{u['rank']:3d} {u['nickname'][:25]:25s} {u['value']:,}")

# Save full dump
json.dump(all_data, open("/tmp/kalshi_lb_full.json", "w"), indent=1)
print(f"\nSaved to /tmp/kalshi_lb_full.json ({len(json.dumps(all_data))} chars)")