"""Extra data for the strategy tests (runs on GitHub Actions; needs internet).

  data/insider_bodies.csv.gz : full text of every Oslo Børs MANAGERS' TRANSACTION message
  data/freight.csv.gz        : daily prices of freight-rate ETFs (dry bulk BDRY, tankers BWET)
"""
import json
import re
import time
from pathlib import Path

import pandas as pd
import requests

DATA = Path("data")
MSG = "https://api3.oslo.oslobors.no/v1/newsreader/message"
H = {"User-Agent": "Mozilla/5.0"}


def strings(obj, out):
    if isinstance(obj, dict):
        for v in obj.values():
            strings(v, out)
    elif isinstance(obj, list):
        for v in obj:
            strings(v, out)
    elif isinstance(obj, str) and len(obj) > 40:
        out.append(obj)


def body(mid):
    for attempt in range(3):
        try:
            r = requests.get(MSG, params={"messageId": mid}, headers=H, timeout=30)
            if r.ok and r.text.strip().startswith("{"):
                parts = []
                strings(r.json(), parts)
                txt = re.sub(r"<[^>]+>", " ", " ".join(parts))
                return re.sub(r"\s+", " ", txt)[:6000], r.text[:3000]
        except requests.RequestException:
            pass
        time.sleep(2)
    return "", ""


def insider_bodies():
    path = DATA / "insider_bodies.csv.gz"
    nw = pd.read_csv(DATA / "newsweb.csv.gz")
    mt = nw[nw.category.fillna("").str.contains("MANAGERS")]
    done = set(pd.read_csv(path).id) if path.exists() else set()
    rows = [pd.read_csv(path)] if path.exists() else []
    new = []
    sample_raw = None
    for i, mid in enumerate(mt.id):
        if mid in done:
            continue
        txt, raw = body(mid)
        sample_raw = sample_raw or raw
        new.append(dict(id=mid, body=txt))
        if len(new) % 500 == 0:
            print(f"  {len(new)} bodies", flush=True)
            pd.concat(rows + [pd.DataFrame(new)]).to_csv(path, index=False)
        time.sleep(0.15)
    if new:
        pd.concat(rows + [pd.DataFrame(new)]).to_csv(path, index=False)
    print("insider bodies:", len(done) + len(new), "| sample raw:", (sample_raw or "")[:600], flush=True)


def freight():
    import yfinance as yf
    df = yf.download(["BDRY", "BWET", "SPY"], start="2018-01-01", auto_adjust=True, progress=False)["Close"]
    df.index = pd.to_datetime(df.index).strftime("%Y-%m-%d")
    df.to_csv(DATA / "freight.csv.gz")
    print("freight:", df.notna().sum().to_dict(), df.index.min(), df.index.max())


if __name__ == "__main__":
    freight()
    insider_bodies()
