#!/usr/bin/env python3
"""
Kursarkiv og universlogg (mot overlevelsesskjevhet)
===================================================
Yahoo gir bare historikk for aksjer som fortsatt finnes. Når en aksje blir
avnotert, kjøpt opp eller bytter ticker, forsvinner den fra uttrekket - og en
backtest som bare ser dagens aksjer blir for pen. Derfor arkiverer vi selv:

    nordnet_data/price_archive/prices_YYYY-MM.csv
        date, ticker, open, high, low, close, adj_close, volume, tr
        Bare nye (date, ticker)-rader legges til. Eksisterende rader endres ALDRI.
        tr = totalavkastningsfaktor fra forrige handelsdag (adj_close / forrige adj_close),
        regnet ut i samme uttrekk. Da kan research/data.py bygge en riktig utbyttejustert
        serie for en aksje som bare finnes i arkivet.
        Første kjøring legger inn hele historikken Yahoo har i dag (fra 2019).

    nordnet_data/price_archive/universe_log.jsonl
        Én linje per endring: aksje lagt til / fjernet fra watchlisten, mangler hos Yahoo,
        har sluttet å få nye kurser (> 10 dager gammel) eller er tilbake.

    nordnet_data/price_archive/universe_state.json   forrige tilstand (for å finne endringer)
"""

import argparse
import glob
import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from news_ml.common import BENCHMARK, load_universe  # noqa: E402
from research.data import ARCHIVE_DIR, PRICE_CSV  # noqa: E402

COLS = ["date", "ticker", "open", "high", "low", "close", "adj_close", "volume", "tr"]
STALE_DAYS = 10


def _prepare(px):
    px = px.copy()
    for c in COLS:
        if c not in px:
            px[c] = np.nan
    px["date"] = pd.to_datetime(px["date"]).dt.strftime("%Y-%m-%d")
    px = px.dropna(subset=["close"]).sort_values(["ticker", "date"])
    px = px.drop_duplicates(["ticker", "date"], keep="last")
    adj = px["adj_close"].fillna(px["close"])
    px["tr"] = adj / adj.groupby(px["ticker"]).shift(1)
    return px[COLS]


def archive_prices(px, archive_dir):
    """Legg nye rader inn i månedsfilene. Returnerer antall nye rader."""
    os.makedirs(archive_dir, exist_ok=True)
    px = _prepare(px)
    added = 0
    for month, g in px.groupby(px["date"].str[:7]):
        path = os.path.join(archive_dir, f"prices_{month}.csv")
        if os.path.exists(path):
            old = pd.read_csv(path, dtype={"date": str, "ticker": str})
            have = set(zip(old["date"], old["ticker"]))
            new = g[[(d, t) not in have for d, t in zip(g["date"], g["ticker"])]]
            if new.empty:
                continue
            out = pd.concat([old, new], ignore_index=True)
        else:
            new = out = g
        out = out.sort_values(["date", "ticker"]).copy()
        out["volume"] = pd.to_numeric(out["volume"], errors="coerce").round().astype("Int64")
        out.to_csv(path, index=False, float_format="%.6g")
        added += len(new)
    return added


def update_universe_log(px, archive_dir, universe=None, today=None):
    """Sammenlign med forrige kjøring og skriv endringer til universe_log.jsonl."""
    uni = universe if universe is not None else load_universe()
    watch = sorted({u["ticker"] for u in uni})
    px = px[px["ticker"] != BENCHMARK]
    last = pd.to_datetime(px.groupby("ticker")["date"].max())
    newest = last.max() if len(last) else None
    fresh = {t for t, d in last.items() if newest is not None and (newest - d).days <= STALE_DAYS}
    state_path = os.path.join(archive_dir, "universe_state.json")
    prev = None
    if os.path.exists(state_path):
        with open(state_path, encoding="utf-8") as f:
            prev = json.load(f)
    today = today or datetime.now(timezone.utc).date().isoformat()
    events = []

    def ev(ticker, kind):
        d = last.get(ticker)
        events.append({"date": today, "ticker": ticker, "event": kind,
                       "last_price_date": None if d is None or pd.isna(d) else str(d.date())})

    missing = [t for t in watch if t not in last.index]
    stale = [t for t in watch if t in last.index and t not in fresh]
    if prev is None:
        events.append({"date": today, "event": "start", "n_watchlist": len(watch), "n_with_prices": int(len(last)),
                       "missing_from_yahoo": missing, "stale": stale})
    else:
        pw, pm, ps = set(prev["watchlist"]), set(prev["missing"]), set(prev["stale"])
        for t in sorted(set(watch) - pw):
            ev(t, "lagt_til_watchlist")
        for t in sorted(pw - set(watch)):
            ev(t, "fjernet_fra_watchlist")
        for t in missing:
            if t not in pm:
                ev(t, "mangler_hos_yahoo")
        for t in stale:
            if t not in ps:
                ev(t, "ingen_nye_kurser")
        for t in sorted((pm | ps) & fresh):
            ev(t, "tilbake")
    if events:
        with open(os.path.join(archive_dir, "universe_log.jsonl"), "a", encoding="utf-8") as f:
            for e in events:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump({"updated": today, "newest_price_date": None if newest is None else str(newest.date()),
                   "watchlist": watch, "missing": missing, "stale": stale}, f, ensure_ascii=False, indent=1)
    return events


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--price-csv", default=PRICE_CSV)
    ap.add_argument("--archive-dir", default=ARCHIVE_DIR)
    args = ap.parse_args(argv)
    px = pd.read_csv(args.price_csv)
    n = archive_prices(px, args.archive_dir)
    ev = update_universe_log(px, args.archive_dir)
    files = glob.glob(os.path.join(args.archive_dir, "prices_*.csv"))
    print(f"Kursarkiv: {n} nye rader, {len(files)} månedsfiler. Universendringer: {len(ev)}")
    for e in ev[:30]:
        print("  ", e)


if __name__ == "__main__":
    main()
