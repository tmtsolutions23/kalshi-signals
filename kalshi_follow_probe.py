#!/usr/bin/env python3
"""Probe Kalshi social follow/feed API."""
import json, urllib.request, urllib.error

cook = open('/root/.hermes/secrets/kalshi_cookies.txt').read()
waf = open('/root/.hermes/secrets/kalshi_waf_token.txt').read()
csrf = open('/root/.hermes/secrets/kalshi_csrf.txt').read()
BASE = "https://api.elections.kalshi.com/v1"
HD = {"accept":"application/json","x-csrf-token":csrf,"x-aws-waf-token":waf,
      "origin":"https://kalshi.com","referer":"https://kalshi.com/",
      "cookie":cook,"user-agent":"Mozilla/5.0"}
ME = "12418cb1-c900-4db8-b767-46ef48a44de0"

def api(method, path, body=None):
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(BASE+path, headers=HD, data=data, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        b = e.read()
        try: return e.code, json.loads(b) if b else {}
        except: return e.code, {"raw": str(b[:200])}

# 1. What does the profile response look like when authorized as me?
st, d = api("GET", f"/users/{ME}/social/profile")
print(f"own profile: HTTP {st}")
if st == 200: print(json.dumps(d)[:800])

# 2. Follow/unfollow API candidates
print("\n=== FOLLOW API PROBES ===")
for path in ["/social/follow", "/users/follow", f"/users/{ME}/social/follow",
             "/social/following/follow", "/social/follows"]:
    st, d = api("GET", path)
    if st != 404: print(f"GET {path}: HTTP {st} {json.dumps(d)[:200]}")

# Try POST follow with a target
print("\n=== POST FOLLOW ===")
for path, body in [(f"/users/lebronthanos/social/follow", None),
                   (f"/social/follow", {"user_id": "lebronthanos"}),
                   (f"/social/follow", {"nickname": "lebronthanos"}),
                   (f"/social/follow", {"target": "lebronthanos"}),
                   (f"/users/{ME}/social/following", {"target": "lebronthanos"})]:
    st, d = api("POST", path, body)
    print(f"POST {path} {json.dumps(body)}: HTTP {st} {json.dumps(d)[:120]}")

# 3. Feed / following list
print("\n=== FEED PROBES ===")
for path in [f"/users/{ME}/social/feed", "/social/feed", f"/users/{ME}/social/following",
             "/social/following", "/users/{ME}/social/network"]:
    st, d = api("GET", path)
    if st != 404: print(f"GET {path}: HTTP {st} {json.dumps(d)[:200]}")