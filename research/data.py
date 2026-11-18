"""
Kursdata for testbenken
=======================
Én felles innlesing av kurser, med samme handelskalender som copytrade/paper.py
(dager der minst 30 % av aksjene handlet) og samme utbyttejustering
(justeringsfaktor = adj_close / close, brukt på åpning, høy, lav og slutt).

Kilder, i prioritert rekkefølge per aksje:
  1. nordnet_data/news_ml_prices/prices.csv  - full historikk hentet fra Yahoo hver dag
  2. nordnet_data/price_archive/             - vårt eget arkiv (research/archive_prices.py).
     Brukes for aksjer som ikke lenger finnes i dagens Yahoo-uttrekk, f.eks. etter
     avnotering, slik at de ikke forsvinner fra backtestene (overlevelsesskjevhet).
"""

import glob
import json
import os
import sys
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from news_ml.common import BENCHMARK  # noqa: E402

DATA_DIR = os.environ.get("NEWS_ML_DATA", os.path.join(ROOT, "nordnet_data"))
PRICE_CSV = os.path.join(DATA_DIR, "news_ml_prices", "prices.csv")
ARCHIVE_DIR = os.path.join(DATA_DIR, "price_archive")
CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

COLS = ["open", "high", "low", "close"]


def load_config(path=None):
    with open(path or CONFIG, encoding="utf-8") as f:
        return json.load(f)


@dataclass
class Panel:
    cal: pd.DatetimeIndex
    open: pd.DataFrame          # justert åpning (dato x ticker)
    close: pd.DataFrame         # justert slutt
    high: pd.DataFrame          # justert høy
    low: pd.DataFrame           # justert lav
    bench_open: pd.Series
    bench_close: pd.Series
    source: dict = field(default_factory=dict)   # ticker -> "yahoo" / "arkiv"
    _hs: pd.DataFrame = None

    @property
    def tickers(self):
        return list(self.open.columns)

    def half_spread(self, costs):
        if self._hs is None:
            from research.costs import abdi_ranaldo_half_spread
            self._hs = abdi_ranaldo_half_spread(
                self.close, self.high, self.low, window=costs["spread_window"], min_obs=costs["spread_min_obs"],
                floor=costs["half_spread_floor"], cap=costs["half_spread_cap"])
        return self._hs


def _read_prices(path):
    px = pd.read_csv(path, parse_dates=["date"])
    for c in ("high", "low"):
        if c not in px:
            px[c] = np.nan
    if "adj_close" not in px:
        px["adj_close"] = px["close"]
    return px


def _read_archive(archive_dir, tickers):
    """Arkivrader for gitte tickere, med utbyttejustering bygd opp fra kolonnen tr.

    tr = totalavkastningsfaktor fra forrige handelsdag, regnet ut fra ett og samme
    Yahoo-uttrekk da raden ble arkivert. Kjedet sammen gir det en konsistent justert serie
    selv om radene ble arkivert på ulike dager.
    """
    files = sorted(glob.glob(os.path.join(archive_dir, "prices_*.csv")))
    if not files or not tickers:
        return pd.DataFrame()
    parts = []
    for f in files:
        d = pd.read_csv(f, parse_dates=["date"])
        parts.append(d[d["ticker"].isin(tickers)])
    a = pd.concat(parts, ignore_index=True)
    if a.empty:
        return a
    a = a.sort_values(["ticker", "date"]).drop_duplicates(["ticker", "date"], keep="first")
    out = []
    for _, g in a.groupby("ticker", sort=False):
        g = g.copy()
        tr = g["tr"].where(np.isfinite(g["tr"]) & (g["tr"] > 0))
        raw = g["close"] / g["close"].shift(1)
        step = tr.fillna(raw).fillna(1.0)
        step.iloc[0] = 1.0
        lvl = step.cumprod()
        g["adj_close"] = lvl * (g["close"].iloc[-1] / lvl.iloc[-1])
        out.append(g)
    return pd.concat(out, ignore_index=True)


def load_panel(price_csv=None, archive_dir=None, use_archive=True):
    px = _read_prices(price_csv or PRICE_CSV)
    px["source"] = "yahoo"
    if use_archive:
        adir = archive_dir or ARCHIVE_DIR
        if os.path.isdir(adir):
            have = set(px["ticker"].unique())
            arch_tickers = set()
            for f in glob.glob(os.path.join(adir, "prices_*.csv")):
                arch_tickers |= set(pd.read_csv(f, usecols=["ticker"])["ticker"].unique())
            missing = sorted(arch_tickers - have - {BENCHMARK})
            if missing:
                a = _read_archive(adir, missing)
                if not a.empty:
                    a["source"] = "arkiv"
                    px = pd.concat([px, a[[c for c in px.columns if c in a.columns]]], ignore_index=True)

    px = px.dropna(subset=["open", "close"])
    px = px[(px["close"] > 0) & (px["open"] > 0)].copy()
    px["adj_close"] = px["adj_close"].fillna(px["close"])
    f = px["adj_close"] / px["close"]
    for c in COLS:
        px[f"adj_{c}"] = px[c] * f
    source = px.groupby("ticker")["source"].last().to_dict()

    def piv(col):
        return px.pivot_table(index="date", columns="ticker", values=col, aggfunc="last").sort_index()

    opn, cls, hi, lo = piv("adj_open"), piv("adj_close"), piv("adj_high"), piv("adj_low")
    stocks = cls.drop(columns=[BENCHMARK], errors="ignore")
    cal = stocks.index[stocks.notna().sum(axis=1) >= max(1, 0.3 * stocks.shape[1])]

    def stock_part(df):
        return df.reindex(cal).drop(columns=[BENCHMARK], errors="ignore")

    if BENCHMARK in opn:
        bo = opn[BENCHMARK].reindex(cal).ffill(limit=3)
        bc = cls[BENCHMARK].reindex(cal).ffill(limit=3)
    else:
        bo = bc = pd.Series(np.nan, index=cal)
    source.pop(BENCHMARK, None)
    return Panel(cal=cal, open=stock_part(opn), close=stock_part(cls), high=stock_part(hi), low=stock_part(lo),
                 bench_open=bo, bench_close=bc, source=source)
