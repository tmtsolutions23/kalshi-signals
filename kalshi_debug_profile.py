#!/usr/bin/env python3
"""Debug: exact own-profile call + raw responses."""
import json, urllib.request, urllib.error

cook = open('/root/.hermes/secrets/kalshi_cookies.txt').read()
waf = open('/root/.hermes/secrets/kalshi_waf_token.txt').read()
csrf = open('/root/.hermes/secrets/kalshi_csrf.txt').read()
BASE = "https://api.elections.kalshi.com/v1"
HD = {"accept":"application/json","x-csrf-token":csrf,"x-aws-waf-token":waf,
      "origin":"https://kalshi.com","referer":"https://kalshi.com/",
      "cookie":cook,"user-agent":"Mozilla/5.0"}

def raw(path):
    req = urllib.request.Request(BASE+path, headers=HD)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()

# Own profile
st, body = raw("/users/12418cb1-c900-4db8-b767-46ef48a44de0/social/profile")
print(f"own profile: HTTP {st}")
print(body[:800])
print("---")

# Leaderboard sanity (should still work with these tokens)
st, body = raw("/social/leaderboard?metric_name=projected_pnl&limit=3&time_period=weekly")
print(f"leaderboard sanity: HTTP {st}")
print(body[:300])