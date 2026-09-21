#!/usr/bin/env python3
"""Decode Kalshi tickers into human-readable market descriptions."""
import re

MONTHS = {"JAN":"Jan","FEB":"Feb","MAR":"Mar","APR":"Apr","MAY":"May","JUN":"Jun",
          "JUL":"Jul","AUG":"Aug","SEP":"Sep","OCT":"Oct","NOV":"Nov","DEC":"Dec"}

TEAMS = {
    "BAL":"Ravens","PIT":"Steelers","CIN":"Bengals","CLE":"Browns",
    "BUF":"Bills","MIA":"Dolphins","NE":"Patriots","NYJ":"Jets",
    "HOU":"Texans","IND":"Colts","JAX":"Jaguars","TEN":"Titans",
    "DEN":"Broncos","KC":"Chiefs","LV":"Raiders","LAC":"Chargers",
    "DAL":"Cowboys","NYG":"Giants","PHI":"Eagles","WAS":"Commanders",
    "CHI":"Bears","DET":"Lions","GB":"Packers","MIN":"Vikings",
    "ATL":"Falcons","CAR":"Panthers","NO":"Saints","TB":"Buccaneers",
    "SEA":"Seahawks","LAR":"Rams","ARI":"Cardinals","SF":"49ers",
    "LSU":"LSU","MICH":"Michigan","OSU":"Ohio St","ALA":"Alabama","UGA":"Georgia",
    "TEX":"Texas","OU":"Oklahoma","CLEM":"Clemson","FSU":"Florida St",
    "ND":"Notre Dame","USC":"USC","MISS":"Mississippi","FLA":"Florida",
    "AUB":"Auburn","ORE":"Oregon","WASH":"Washington","PSU":"Penn St",
    "PSG":"PSG","MIL":"AC Milan","INT":"Inter","JUV":"Juventus",
    "BAR":"Barcelona","RMA":"Real Madrid","ATM":"Atletico",
    "MCI":"Man City","MUN":"Man Utd","LIV":"Liverpool","ARS":"Arsenal",
    "CHE":"Chelsea","BAY":"Bayern",
}
LONG = {"BAL":"Baltimore","PIT":"Pittsburgh","CIN":"Cincinnati","CLE":"Cleveland",
        "BUF":"Buffalo","NE":"New England","NYJ":"NY Jets","LA":"LA","SD":"San Diego",
        "SF":"San Francisco","TB":"Tampa Bay","NO":"New Orleans","LV":"Las Vegas",
        "KC":"Kansas City","GB":"Green Bay","NYG":"NY Giants",
        "CHI":"Chicago","MIN":"Minnesota","PHI":"Philadelphia","DAL":"Dallas",
        "SEA":"Seattle","ARI":"Arizona","DEN":"Denver","MIA":"Miami",
        "ATL":"Atlanta","HOU":"Houston","IND":"Indianapolis","JAX":"Jacksonville",
        "TEN":"Tennessee","CAR":"Carolina","DET":"Detroit","WAS":"Washington",
            "STL":"St. Louis","COL":"Colorado",
            "LSU":"LSU","USC":"USC","MICH":"Michigan","OSU":"Ohio St","ND":"Notre Dame",
            "PSG":"PSG","MISS":"Mississippi","SCAR":"South Carolina","MSST":"Mississippi St",
            "ARK":"Arkansas","VAN":"Vanderbilt","MSS":"Mississippi St",
            "CWS":"White Sox"}  # CWS = Chi White Sox (MLB)

def dy(yy, mon, dd):
    m = MONTHS.get(mon, mon)
    return f"{m} {dd}, 20{yy}"

def split_teams(s):
    for i in range(3, min(6, len(s))):
        t1 = s[:i]; t2 = s[i:]
        if t1 in TEAMS: return (t1, t2)
    return (s[:3], s[3:])

def place(t1, t2):
    n1 = LONG.get(t1, TEAMS.get(t1, t1))
    n2 = LONG.get(t2, TEAMS.get(t2, t2))
    return f"{n1} {TEAMS.get(t1,'')} vs {n2} {TEAMS.get(t2,'')}"

def ticker_to_readable(t):
    # BTC 15m
    m = re.match(r'KXBTC(\d+)M-(\d{2})([A-Z]{3})(\d{2})(\d{2})(\d{2})-(\d+)', t)
    if m:
        return f"BTC > ${m.group(7)}k? ({m.group(1)}-min window at {dy(m.group(2),m.group(3),m.group(4))} {m.group(5)}:{m.group(6)})"

    # ATP tennis: KX{ATP/EET}-{YY}{EVENT}-{PLAYER}
    m = re.match(r'KX(\w+)-(\d{2})([A-Z]{3})-([A-Z]+)', t)
    if m and m.group(1).startswith("ATP"):
        return f"ATP {m.group(3)} - {m.group(4)}"

    # Sports: KX{SPORT}{TYPE}-{DATE}{TEAMS}-{SUFFIX}
    m = re.match(r'KX(\w+)-(\d{2})([A-Z]{3})(\d{2})([A-Z]{3,7})-([A-Z]+)(\d*)$', t)
    if m:
        sport=m.group(1); yy=m.group(2); mon=m.group(3); dd=m.group(4)
        ms=m.group(5); suf=m.group(6); sp=m.group(7)
        date=dy(yy,mon,dd)
        t1,t2=split_teams(ms)
        n1=LONG.get(t1,TEAMS.get(t1,t1)); n2=LONG.get(t2,TEAMS.get(t2,t2))
        m1=TEAMS.get(t1,t1); m2=TEAMS.get(t2,t2)
        if "SPREAD" in sport.upper():
            return f"{n1} {m1} -{sp} vs {n2} {m2} (NFL spread, {date})"
        elif suf == t1:
            return f"Will {n1} win? ({n1} vs {n2}, {date})"
        elif suf == t2:
            return f"Will {n2} win? ({n1} @ {n2}, {date})"
        return f"Game: {n1} vs {n2} — {suf} side ({date})"
    
    # NCAAF
    m = re.match(r'KX(\w+)-(\d{2})([A-Z]{3})(\d{2})([A-Z]{4,7})-([A-Z]+)', t)
    if m:
        t1,t2=split_teams(m.group(5))
        return f"NCAAF: {place(t1,t2)} ({dy(m.group(2),m.group(3),m.group(4))})"
    
    return t

if __name__ == "__main__":
    for t in ["KXNFLSPREAD-26SEP13BALIND-BAL10","KXNFLGAME-26SEP13ATLPIT-PIT",
              "KXATP-26USO-SHE","KXBTC15M-26SEP192330-30",
              "KXNFLGAME-26SEP17DETBUF-DET","KXNCAAFGAME-26SEP19LSUMISS-LSU",
              "KXNFLGAME-26SEP19USCRUTG-USC"]:
        print(f"{t:50s} → {ticker_to_readable(t)}")