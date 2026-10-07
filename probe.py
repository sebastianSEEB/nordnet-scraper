import json, time, requests, yfinance as yf
G = "https://api.gdeltproject.org/api/v2/doc/doc"
def g(**p):
    p.setdefault("format", "json")
    for i in range(4):
        r = requests.get(G, params=p, timeout=60)
        print("HTTP", r.status_code, r.headers.get("content-type"), "len", len(r.text))
        if r.ok and r.text.strip().startswith("{"):
            return r.json()
        print("BODY:", r.text[:300]); time.sleep(8)
    return {}
for mode in ["TimelineVolRaw", "TimelineTone"]:
    d = g(query='"Equinor"', mode=mode, startdatetime="20230101000000", enddatetime="20261007000000")
    for s in d.get("timeline", []):
        pts = s["data"]
        print(mode, s.get("series"), "points", len(pts), pts[:3], pts[-2:])
    time.sleep(6)
d = g(query='"Equinor"', mode="TimelineVolRaw", startdatetime="20240101000000", enddatetime="20240301000000")
for s in d.get("timeline", []):
    print("2-month span points", len(s["data"]), s["data"][:2])
time.sleep(6)
d = g(query='"Equinor"', mode="ArtList", maxrecords=10, sort="DateAsc",
      startdatetime="20240207000000", enddatetime="20240209000000")
print(json.dumps(d.get("articles", [])[:4], indent=1))
time.sleep(6)
for q in ['"Frontline" (tanker OR tankers OR shipping)', '"Eni" (oil OR gas)', '"SEB"', '"Mowi"']:
    d = g(query=q, mode="TimelineVolRaw", startdatetime="20250101000000", enddatetime="20250201000000")
    print(q, [len(s["data"]) for s in d.get("timeline", [])], sum(p["value"] for s in d.get("timeline", []) for p in s["data"]))
    time.sleep(6)
df = yf.download(["EQNR.OL", "SAP.DE"], start="2024-02-01", end="2024-02-12", auto_adjust=True, progress=False)
print(df[["Open", "Close"]])
