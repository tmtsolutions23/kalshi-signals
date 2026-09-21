#!/usr/bin/env python3
"""Check visibility_state + public trades for all top leaders."""
import json, urllib.request, urllib.error

cook = open('/root/.hermes/secrets/kalshi_cookies.txt').read()
waf = open('/root/.hermes/secrets/kalshi_waf_token.txt').read()
csrf = open('/root/.hermes/secrets/kalshi_csrf.txt').read()
BASE = "https://api.elections.kalshi.com/v1"
HD = {"accept":"application/json","x-csrf-token":csrf,"x-aws-waf-token":waf,
      "origin":"https://kalshi.com","referer":"https://kalshi.com/",
      "cookie":cook,"user-agent":"Mozilla/5.0"}

def api(path):
    try:
        req = urllib.request.Request(BASE+path, headers=HD)
        with urllib.request.urlopen(req, timeout=10) as r: return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        b=e.read()
        try: return e.code, json.loads(b) if b else {}
        except: return e.code, {}

# Get top 20 by projected PnL (weekly)
st, d = api("/social/leaderboard?metric_name=projected_pnl&limit=20&time_period=weekly")
rl = d.get("rank_list", [])
print(f"Top {len(rl)} traders by weekly projected PnL — visibility check:")
for u in rl[:15]:
    nick = u["nickname"]
    st2, t = api(f"/social/trades?nickname={nick}")
    vis = t.get("visibility_state", "?")
    n = len(t.get("trades", []))
    print(f"  #{u['rank']:2d} {nick:28s} PnL=${u['value']:>10,.0f} | visibility={vis:6s} | trades={n}")

# Save top names for later
json.dump([{"nickname": u["nickname"], "rank": u["rank"], "value": u["value"]} for u in rl[:50]],
          open("/tmp/kalshi_top50.json","w"))