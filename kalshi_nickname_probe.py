#!/usr/bin/env python3
"""Probe Kalshi social endpoints keyed by NICKNAME."""
import json, urllib.request, urllib.error

cook = open('/root/.hermes/secrets/kalshi_cookies.txt').read()
waf = open('/root/.hermes/secrets/kalshi_waf_token.txt').read()
csrf = open('/root/.hermes/secrets/kalshi_csrf.txt').read()
BASE = "https://api.elections.kalshi.com/v1"
HD = {"accept":"application/json","x-csrf-token":csrf,"x-aws-waf-token":waf,
      "origin":"https://kalshi.com","referer":"https://kalshi.com/",
      "cookie":cook,"user-agent":"Mozilla/5.0"}

def api(path):
    req = urllib.request.Request(BASE+path, headers=HD)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        b = e.read()
        try: return e.code, json.loads(b) if b else {}
        except: return e.code, {"raw": str(b[:150])}

# The /social/following endpoint requires nickname - probe keyed variants
nick = "lebronthanos"
probes = [
    f"/social/following?nickname={nick}",
    f"/social/followers?nickname={nick}",
    f"/social/profile?nickname={nick}",
    f"/social/profile/{nick}",
    f"/social/user?nickname={nick}",
    f"/social/feed?nickname={nick}",
    f"/social/positions?nickname={nick}",
    f"/social/stats?nickname={nick}",
    f"/social/trader?nickname={nick}",
    f"/social/markets?nickname={nick}",
    f"/social/bets?nickname={nick}",
    f"/social/history?nickname={nick}",
    f"/social/portfolio?nickname={nick}",
]

print(f"=== PROBES for nickname={nick} ===")
for p in probes:
    st, d = api(p)
    if st == 200:
        s = json.dumps(d)
        print(f"\n✅ {p}: HTTP {st}")
        print(f"   {s[:600]}")
    elif st != 404:
        msg = d.get("error",{}).get("details") or d.get("error",{}).get("message") or d.get("message","")
        print(f"  {p}: HTTP {st} {str(msg)[:100]}")