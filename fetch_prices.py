#!/usr/bin/env python3
"""
Henter daglige kurser for alle aksjene i forum-arkivet + OSEBX
==============================================================
Kilde: Yahoo Finance via yfinance (gratis, Oslo Børs-tickere har ".OL").

Ticker utledes fra Nordnet-slugen: "frontline-fro-xosl" -> "FRO.OL".
Hvis Yahoo bruker et annet symbol, legg det inn i ticker_overrides.json:
    {"slug-fra-nordnet": "SYMBOL.OL"}
Aksjer som feiler listes i loggen, så du ser hva som må overstyres.

Output: nordnet_data/prices/prices.csv (lang tabell)
    date, slug, ticker, open, close, adj_close, volume
Referanseindeksen (OSEBX) lagres med slug "_benchmark".

Bruk:
    pip install yfinance pandas
    python fetch_prices.py               # fra 45 dager før første innlegg
    python fetch_prices.py --start 2026-06-01
"""

import argparse
import json
import os
import sys
from datetime import date, timedelta

import pandas as pd

from archive_posts import iter_archive

BENCHMARK_SLUG = "_benchmark"
BENCHMARK_CANDIDATES = ["OSEBX.OL", "^OSEAX"]  # OSEBX først, hovedindeksen som reserve


def slug_to_ticker(slug: str) -> str:
    parts = slug.split("-")
    base = parts[-2] if len(parts) > 2 else parts[0]
    return f"{base.upper()}.OL"


def load_overrides(path: str) -> dict:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return {k: v for k, v in json.load(f).items() if not k.startswith("_")}
    return {}


def build_ticker_map(data_dir: str, overrides_path: str) -> dict:
    slugs = sorted({p["slug"] for p in iter_archive(data_dir)})
    overrides = load_overrides(overrides_path)
    return {s: overrides.get(s, slug_to_ticker(s)) for s in slugs}


def default_start(data_dir: str) -> str:
    # scraped_at (ikke posted_at): noen få eldgamle innlegg fra første kjøring
    # skal ikke dra startdatoen flere år tilbake.
    first = min(p["scraped_at"] for p in iter_archive(data_dir))[:10]
    return (date.fromisoformat(first) - timedelta(days=45)).isoformat()


def download(tickers: list, start: str, end: str) -> pd.DataFrame:
    import yfinance as yf

    raw = yf.download(tickers, start=start, end=end, auto_adjust=False, group_by="ticker",
                      progress=False, threads=True)
    frames = []
    for t in tickers:
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
            "date": pd.to_datetime(df.index).date,
            "ticker": t,
            "open": df["Open"].to_numpy(),
            "close": df["Close"].to_numpy(),
            "adj_close": df["Adj Close"].to_numpy() if "Adj Close" in df else df["Close"].to_numpy(),
            "volume": df["Volume"].to_numpy(),
        }))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def main() -> None:
    ap = argparse.ArgumentParser(description="Hent daglige kurser for aksjene i forum-arkivet")
    ap.add_argument("--data-dir", default="nordnet_data")
    ap.add_argument("--overrides", default="ticker_overrides.json")
    ap.add_argument("--start", help="YYYY-MM-DD (standard: 45 dager før første scraping)")
    ap.add_argument("--end", default=(date.today() + timedelta(days=1)).isoformat())
    args = ap.parse_args()

    ticker_map = build_ticker_map(args.data_dir, args.overrides)
    start = args.start or default_start(args.data_dir)
    print(f"Henter {len(ticker_map)} aksjer + indeks, {start} -> {args.end}")

    prices = download(sorted(set(ticker_map.values())), start, args.end)
    if prices.empty:
        sys.exit("Fikk ingen kurser fra Yahoo - sjekk nettverk/yfinance-versjon.")
    rows = []
    for slug, ticker in ticker_map.items():
        sub = prices[prices["ticker"] == ticker]
        if not sub.empty:
            rows.append(sub.assign(slug=slug))
    out = pd.concat(rows, ignore_index=True)

    bench = pd.DataFrame()
    for cand in BENCHMARK_CANDIDATES:
        bench = download([cand], start, args.end)
        if not bench.empty:
            print(f"Referanseindeks: {cand}")
            break
    if bench.empty:
        print("ADVARSEL: fant ingen indeks - analysen bruker likevektet snitt av aksjene som marked.")
    else:
        out = pd.concat([out, bench.assign(slug=BENCHMARK_SLUG)], ignore_index=True)

    missing = sorted(s for s, t in ticker_map.items() if t not in set(prices["ticker"]))
    if missing:
        print(f"\nIngen kurser for {len(missing)} aksjer (legg riktig symbol i {args.overrides}):")
        for s in missing:
            print(f"  {s}  (prøvde {ticker_map[s]})")

    out_dir = os.path.join(args.data_dir, "prices")
    os.makedirs(out_dir, exist_ok=True)
    out = out[["date", "slug", "ticker", "open", "close", "adj_close", "volume"]].sort_values(["slug", "date"])
    out.to_csv(os.path.join(out_dir, "prices.csv"), index=False)
    with open(os.path.join(out_dir, "ticker_map.json"), "w", encoding="utf-8") as f:
        json.dump({"tickers": ticker_map, "missing": missing}, f, ensure_ascii=False, indent=2)
    print(f"\nLagret {len(out)} rader for {out['slug'].nunique()} serier -> {out_dir}/prices.csv")


if __name__ == "__main__":
    main()
