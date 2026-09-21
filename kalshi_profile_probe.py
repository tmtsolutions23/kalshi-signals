#!/usr/bin/env python3
"""Probe Kalshi social profile & positions API with fresh tokens."""
import json, os, re, urllib.request, urllib.error

doc = open('/root/.hermes/cache/documents/doc_6973c86daba5_message.txt').read()
cook = re.search(r'-b\s*\^?"([^"]+)\^?"', doc).group(1)
waf = re.search(r'x-aws-waf-token:\s*([^\s^"]+)', doc).group(1)
csrf = re.search(r'x-csrf-token:\s*([^\s^"]+)', doc).group(1)

open('/root/.hermes/secrets/kalshi_cookies.txt','w').write(cook)
open('/root/.hermes/secrets/kalshi_waf_token.txt','w').write(waf)
open('/root/.hermes/secrets/kalshi_csrf.txt','w').write(csrf)

BASE = "https://api.elections.kalshi.com/v1"
HD = {"accept":"application/json","x-csrf-token":csrf,"x-aws-waf-token":waf,
      "origin":"https://kalshi.com","referer":"https://kalshi.com/",
      "cookie":cook,"user-agent":"Mozilla/5.0"}

def api(path):
    try:
        req = urllib.request.Request(BASE+path, headers=HD)
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read()
        try: return e.code, json.loads(body) if body else {}
        except: return e.code, {"raw": str(body[:100])}

# 1. Our own profile (known-good endpoint) - see what data is available
st, profile = api("/users/12418cb1-c900-4db8-b767-46ef48a44de0/social/profile")
if st == 200:
    print("✅ OWN PROFILE:")
    print(f"   keys: {list(profile.keys())}")
    print(f"   data: {json.dumps(profile)[:600]}")

# 2. Try other user profiles by various ID formats
users = ["lebronthanos", "no1pylonfan", "yummy.koala8920", "REAKT", "penny.jumper"]
for u in users:
    for fmt in [f"/users/{u}/social/profile", f"/social/user/{u}/profile",
                f"/social/profile/{u}", f"/social/user/{u}"]:
        st, data = api(fmt)
        if st == 200:
            print(f"\n✅ {fmt}: HTTP {st}")
            print(f"   {json.dumps(data)[:800]}")
        elif st == 401:
            print(f"  {fmt}: HTTP {st} (unauthorized)")
        elif st not in (404,400):
            print(f"  {fmt}: HTTP {st}")

# 3. Try positions endpoint
print("\n=== POSITIONS ===")
for path in ["/social/positions", "/users/positions",
             "/portfolio/positions", "/social/feed",
             "/users/12418cb1-c900-4db8-b767-46ef48a44de0/social/positions"]:
    st, data = api(path)
    if st == 200:
        print(f"✅ {path}: {json.dumps(data)[:500]}")
    elif st not in (404,400):
        print(f"  {path}: HTTP {st}")