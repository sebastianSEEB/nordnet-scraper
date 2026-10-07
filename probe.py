import json, time, requests
def show(tag, r):
    print(tag, r.status_code, r.headers.get("content-type"), len(r.text), r.text[:600].replace("\n"," "), flush=True)
H = {"User-Agent": "Mozilla/5.0", "Accept": "application/json", "Origin": "https://newsweb.oslobors.no",
     "Referer": "https://newsweb.oslobors.no/"}
base = "https://api3.oslo.oslobors.no/v1/newsreader/list"
qs = dict(category="", issuer="", fromDate="2024-02-05", toDate="2024-02-07", market="", messageTitle="")
for m in ["post", "get"]:
    try:
        r = getattr(requests, m)(base, params=qs, headers=H, timeout=30); show("NEWSWEB " + m, r)
    except Exception as e: print("NEWSWEB", m, e)
for url in ["https://newsweb.oslobors.no/search?category=&issuer=EQNR&fromDate=2024-02-01&toDate=2024-02-10",
            "https://api3.oslo.oslobors.no/v1/newsreader/list?issuer=EQNR&fromDate=2024-02-01&toDate=2024-02-10"]:
    try:
        r = requests.post(url, headers=H, timeout=30); show("TRY " + url, r)
    except Exception as e: print("TRY", url, e)
G = "https://api.gdeltproject.org/api/v2/doc/doc"
def g(**p):
    p["format"] = "json"
    for i in range(12):
        r = requests.get(G, params=p, timeout=90)
        if r.ok and r.text.strip().startswith("{"):
            print("  ok after", i + 1, "tries", flush=True); return r.json()
        time.sleep(15)
    print("  gave up"); return {}
for span in [("20220101000000", "20261007000000"), ("20250101000000", "20260101000000")]:
    d = g(query='"Equinor"', mode="TimelineVolRaw", startdatetime=span[0], enddatetime=span[1])
    for s in d.get("timeline", []):
        print("GDELT", span, "points", len(s["data"]), s["data"][:2], s["data"][-1:], flush=True)
    time.sleep(15)
d = g(query='"Equinor"', mode="TimelineTone", startdatetime="20220101000000", enddatetime="20261007000000")
for s in d.get("timeline", []):
    print("TONE points", len(s["data"]), s["data"][:2])
time.sleep(15)
d = g(query='"Equinor"', mode="ArtList", maxrecords=5, sort="DateAsc", startdatetime="20240207000000", enddatetime="20240208000000")
print(json.dumps(d.get("articles", [])[:3]))
