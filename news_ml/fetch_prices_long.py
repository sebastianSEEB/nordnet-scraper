#!/usr/bin/env python3
"""
Lang kurshistorikk (Yahoo Finance) for watchlisten + OSEBX, til backtesten.

Output: nordnet_data/news_ml_prices/prices.csv
    date, ticker, open, high, low, close, adj_close, volume
        nordnet_data/news_ml_prices/shares.json   {ticker: antall aksjer}  (til markedsverdi)
"""

import argparse
import json
import os
import sys
from datetime import date, timedelta

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from news_ml.common import load_universe, PRICE_DIR, OUT_DIR, BENCHMARK  # noqa: E402

BENCH_CANDIDATES = ["OSEBX.OL", "^OSEAX", "OBX.OL"]


def download(tickers, start, end):
    import yfinance as yf
    frames = []
    for i in range(0, len(tickers), 40):
        chunk = tickers[i:i + 40]
        raw = yf.download(chunk, start=start, end=end, auto_adjust=False, group_by="ticker",
                          progress=False, threads=True)
        for t in chunk:
            if isinstance(raw.columns, pd.MultiIndex):
                if t not in raw.columns.get_level_values(0):
                    continue
                df = raw[t]
            else:
                df = raw
            df = df.dropna(subset=["Close"])
            if df.empty:
                continue
            frames.append(pd.DataFrame({
                "date": pd.to_datetime(df.index).date, "ticker": t,
                "open": df["Open"].to_numpy(), "high": df["High"].to_numpy(), "low": df["Low"].to_numpy(),
                "close": df["Close"].to_numpy(),
                "adj_close": (df["Adj Close"] if "Adj Close" in df else df["Close"]).to_numpy(),
                "volume": df["Volume"].to_numpy(),
            }))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2019-06-01")
    ap.add_argument("--end", default=(date.today() + timedelta(days=1)).isoformat())
    args = ap.parse_args()
    os.makedirs(PRICE_DIR, exist_ok=True)
    os.makedirs(OUT_DIR, exist_ok=True)

    uni = load_universe()
    tickers = sorted({u["ticker"] for u in uni})
    print(f"Henter {len(tickers)} aksjer {args.start} -> {args.end}")
    px = download(tickers, args.start, args.end)
    if px.empty:
        sys.exit("Ingen kurser fra Yahoo.")

    bench_used = None
    for cand in BENCH_CANDIDATES:
        b = download([cand], args.start, args.end)
        if not b.empty and len(b) > 200:
            px = pd.concat([px, b.assign(ticker=BENCHMARK)], ignore_index=True)
            bench_used = cand
            break

    import yfinance as yf
    shares = {}
    for t in tickers:
        try:
            fi = yf.Ticker(t).fast_info
            sh = fi.get("shares") if hasattr(fi, "get") else getattr(fi, "shares", None)
            if sh:
                shares[t] = float(sh)
        except Exception:
            pass

    px = px.sort_values(["ticker", "date"])
    px.to_csv(os.path.join(PRICE_DIR, "prices.csv"), index=False)
    with open(os.path.join(PRICE_DIR, "shares.json"), "w") as f:
        json.dump(shares, f, indent=1)
    got = set(px["ticker"])
    missing = [t for t in tickers if t not in got]
    status = {"tickers": len(tickers), "with_prices": len(got - {BENCHMARK}), "benchmark": bench_used,
              "missing": missing, "rows": len(px), "with_shares": len(shares),
              "last_date": str(px["date"].max())}
    with open(os.path.join(OUT_DIR, "fetch_prices_status.json"), "w") as f:
        json.dump(status, f, indent=2)
    print(json.dumps(status, indent=2))


if __name__ == "__main__":
    main()
