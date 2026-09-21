#!/usr/bin/env python3
"""Probe Kalshi API with authenticated calls. Tests auth and searches for leaderboard/social endpoints."""
import base64, json, os, time, urllib.request, urllib.error
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

KEY_ID = "20e46f68-4916-4738-bbe8-8ee7b4019a36"
PEM = "/root/.hermes/secrets/kalshi_private_key.pem"
BASE = "https://external-api.kalshi.com/trade-api/v2"

with open(PEM, "rb") as f:
    private_key = serialization.load_pem_private_key(f.read(), password=None)

def sign(method, path):
    ts = str(int(time.time() * 1000))
    sign_path = urllib.request.urlparse(BASE + path).path.split("?")[0]
    msg = f"{ts}{method.upper()}{sign_path}".encode("utf-8")
    sig = base64.b64encode(
        private_key.sign(msg, padding.PSS(mgf=padding.MGF1(hashes.SHA256()),
                                           salt_length=padding.PSS.DIGEST_LENGTH), hashes.SHA256())
    ).decode()
    return KEY_ID, ts, sig

def api(method, path):
    key_id, ts, sig = sign(method, path)
    headers = {"KALSHI-ACCESS-KEY": key_id, "KALSHI-ACCESS-TIMESTAMP": ts,
               "KALSHI-ACCESS-SIGNATURE": sig, "Content-Type": "application/json",
               "User-Agent": "HermesKalshiProbe/1.0"}
    req = urllib.request.Request(BASE + path, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read()
        try:
            return e.code, json.loads(body.decode()) if body else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            return e.code, {"message": "non-json response"}

# 1. Test auth with portfolio/balance
print("=== AUTH TEST ===")
for p in ["portfolio/balance", "portfolio/orders?limit=1"]:
    st, data = api("GET", f"/{p}")
    print(f"  GET /{p}: HTTP {st} {'OK' if st==200 else data.get('message','?')}")

# 2. Probe leaderboard/social endpoints
print("\n=== LEADERBOARD/SOCIAL PROBE ===")
paths = [
    "leaderboard", "social/leaderboard", "exposed/leaderboard",
    "social/feed", "social/profiles", "social/following",
    "users/leaderboard", "top-traders", "prediction/leaderboard",
    "scores/leaderboard", "stats/leaderboard",
]
for p in paths:
    # try multiple base prefixes
    for prefix in ["", "social/", "exposed/"]:
        full = f"{prefix}{p}".replace("//", "/")
        st, data = api("GET", f"/{full}")
        if st == 200:
            print(f"  GET /{full}: HTTP 200 FOUND! keys={list(data.keys())[:5]}")
        else:
            msg = data.get("message", "") if isinstance(data, dict) else ""
            if st == 404: pass  # expected for most
            else: print(f"  GET /{full}: HTTP {st} {msg[:80]}")

# 3. Check what trade data we can get
print("\n=== TRADE DATA ===")
st, data = api("GET", "/markets/trades?limit=3")
if st == 200:
    trades = data.get("trades", [])
    if trades:
        print(f"  Sample trade keys: {list(trades[0].keys())}")
        print(f"  Sample: {json.dumps(trades[0], indent=1)[:500]}")
    else:
        print("  No trades")
else:
    print(f"  /markets/trades: HTTP {st}")

# 4. Also try public endpoint (no auth needed)
print("\n=== PUBLIC ===")
req = urllib.request.Request(BASE + "/markets?limit=2", headers={"User-Agent": "HermesProbe/1.0"})
with urllib.request.urlopen(req, timeout=15) as r:
    data = json.loads(r.read().decode())
    markets = data.get("markets", [])
    if markets:
        print(f"  Sample market keys: {list(markets[0].keys())}")
        print(f"  Has yes_bid/ask, volume_fp, ticker")

print("\n=== DONE ===")