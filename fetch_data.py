"""Downloads everything the backtest needs into data/. Re-running skips what exists.

  python fetch_data.py base          prices (Yahoo) + Oslo Børs NewsWeb announcements
  python fetch_data.py gdelt i n     GDELT news volume + tone for part i of n (non-Oslo names)
"""
import json
import sys
import time
from pathlib import Path

import pandas as pd
import requests

import nordnet

DATA = Path("data")
START = "2022-01-01"
END = pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%d")
G = "https://api.gdeltproject.org/api/v2/doc/doc"
NEWSWEB = "https://api3.oslo.oslobors.no/v1/newsreader/list"

# GDELT queries for the non-Oslo names (phrases must be 4+ characters).
QUERY = {
    "VOLV-B.ST": '("AB Volvo" OR "Volvo Group" OR "Volvo trucks")', "SAND.ST": '"Sandvik"',
    "SKF-B.ST": '("SKF AB" OR "bearing maker SKF" OR "SKF shares")', "ATCO-A.ST": '"Atlas Copco"',
    "SEB-A.ST": '("SEB bank" OR "Skandinaviska Enskilda")', "SHB-A.ST": '"Handelsbanken"',
    "SWED-A.ST": '"Swedbank"', "ERIC-B.ST": '"Ericsson"', "MAERSK-B.CO": '"Maersk"',
    "DSV.CO": '("DSV A/S" OR "logistics group DSV" OR "DSV shares")', "NOVO-B.CO": '"Novo Nordisk"',
    "NOKIA.HE": '"Nokia"', "NDA-FI.HE": '"Nordea"', "HLAG.DE": '"Hapag-Lloyd"',
    "BMW.DE": '("BMW Group" OR "BMW AG" OR "BMW shares")', "MBG.DE": '"Mercedes-Benz"',
    "VOW3.DE": '"Volkswagen"', "SAP.DE": '("SAP SE" OR "SAP shares" OR "SAP CEO")',
    "SIE.DE": '"Siemens"', "ASML.AS": '"ASML"', "ASM.AS": '"ASM International"',
    "TTE.PA": '"TotalEnergies"', "ENI.MI": '("Eni SpA" OR "Italy\'s Eni" OR "Eni CEO")',
    "BNP.PA": '"BNP Paribas"', "GLE.PA": '"Societe Generale"', "SAN.MC": '"Santander"',
    "BBVA.MC": '"BBVA"',
}


def query_for(tk, name=""):
    return QUERY.get(tk, f'"{name}"')


# ------------------------------------------------------------------ prices
def fetch_prices(universe):
    import yfinance as yf
    path = DATA / "prices.csv.gz"
    if path.exists():
        print("prices: cached"); return
    df = yf.download(list(universe), start=START, auto_adjust=True, progress=False, threads=True)
    parts = []
    for f in ["Open", "Close", "Volume"]:
        x = df[f].copy()
        x.index = pd.to_datetime(x.index).strftime("%Y-%m-%d")
        parts.append(x.stack().rename(f.lower()))
    out = pd.concat(parts, axis=1).reset_index()
    out.columns = ["date", "ticker", "open", "close", "volume"]
    out = out.dropna(subset=["close"])
    out.to_csv(path, index=False)
    print("prices:", out.ticker.nunique(), "of", len(universe), "tickers,", out.date.min(), "to", out.date.max())


# ------------------------------------------------------------------ Oslo Børs NewsWeb
def fetch_newsweb():
    path = DATA / "newsweb.csv.gz"
    if path.exists():
        print("newsweb: cached"); return
    rows, sizes = [], []
    day = pd.Timestamp(START)
    while day <= pd.Timestamp(END):
        to = day + pd.Timedelta(days=2)
        for attempt in range(5):
            try:
                r = requests.get(NEWSWEB, timeout=60, headers={"User-Agent": "Mozilla/5.0"},
                                 params=dict(category="", issuer="", fromDate=day.strftime("%Y-%m-%d"),
                                             toDate=to.strftime("%Y-%m-%d"), market="", messageTitle=""))
                msgs = r.json()["data"]["messages"]
                break
            except Exception as e:
                print("  newsweb retry", day.date(), type(e).__name__); time.sleep(5)
        else:
            msgs = []
        sizes.append(len(msgs))
        for m in msgs:
            rows.append(dict(id=m["messageId"], published_utc=m["publishedTime"], issuer=m["issuerSign"],
                             issuer_name=m.get("issuerName", ""), title=m.get("title", ""),
                             category="; ".join(c.get("category_en", "") for c in m.get("category", [])),
                             markets=",".join(m.get("markets", []))))
        day = to + pd.Timedelta(days=1)
        time.sleep(0.2)
    df = pd.DataFrame(rows).drop_duplicates("id")
    df.to_csv(path, index=False)
    print(f"newsweb: {len(df)} messages, {df.issuer.nunique()} issuers; per 3-day window "
          f"max={max(sizes)} median={int(pd.Series(sizes).median())} (a flat max would mean truncation)")


# ------------------------------------------------------------------ GDELT
def gdelt(**p):
    p["format"] = "json"
    for i in range(40):
        try:
            r = requests.get(G, params=p, timeout=90)
            t = r.text.strip()
            if r.ok and t.startswith("{"):
                return json.loads(t)
            if "too short" in t or "invalid" in t.lower():
                print("  GDELT rejected query:", t[:100]); return None
        except (requests.RequestException, ValueError):
            pass
        time.sleep(12)
    return None


def series(q, mode):
    d = gdelt(query=q, mode=mode, startdatetime=START.replace("-", "") + "000000",
              enddatetime=END.replace("-", "") + "000000")
    pts = [(p["date"], p["value"]) for s in (d or {}).get("timeline", []) for p in s.get("data", [])]
    if not pts:
        return pd.Series(dtype=float)
    s = pd.Series(dict(pts))
    s.index = pd.to_datetime(s.index, format="%Y%m%dT%H%M%SZ").strftime("%Y-%m-%d")
    return s


def fetch_gdelt(part, nparts):
    path = DATA / f"gdelt_{part}.csv.gz"
    names = sorted(t for t in QUERY)[part::nparts]
    done = set(pd.read_csv(path).ticker) if path.exists() else set()
    frames = [pd.read_csv(path)] if path.exists() else []
    for tk in names:
        if tk in done:
            continue
        t0 = time.time()
        vol, tone = series(QUERY[tk], "TimelineVolRaw"), series(QUERY[tk], "TimelineTone")
        df = pd.DataFrame({"articles": vol, "tone": tone}).rename_axis("date_utc").reset_index()
        df["ticker"], df["query"] = tk, QUERY[tk]
        frames.append(df)
        pd.concat(frames).to_csv(path, index=False)
        print(f"  {tk:12s} days={len(df):5d} articles={int(df.articles.fillna(0).sum()):7d} "
              f"({time.time() - t0:.0f}s)", flush=True)


if __name__ == "__main__":
    DATA.mkdir(exist_ok=True)
    what = sys.argv[1] if len(sys.argv) > 1 else "base"
    if what == "base":
        universe, links, _ = nordnet.load()
        (DATA / "universe.json").write_text(json.dumps({"universe": universe, "links": links},
                                                       ensure_ascii=False))
        print("universe:", len(universe), "companies,", len(links), "links")
        fetch_prices(universe)
        fetch_newsweb()
    else:
        fetch_gdelt(int(sys.argv[2]), int(sys.argv[3]))
