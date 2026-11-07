"""
Innsidesignal 2.0 (Fase 1)
==========================
Tar de rene innsidekjøpene (copytrade/insiders.py, etter det strengere støyfilteret)
og merker hvert kjøp med fire "opportunistisk"-flagg. Alle bruker bare informasjon
som var kjent da meldingen ble publisert:

    forste_paa_aar  ingen andre rene innsidekjøp i selskapet de siste 365 dagene
    klynge          minst 2 ulike innsidere har kjøpt i selskapet siste 10 dager (inkl. denne)
    etter_fall      aksjen har falt minst 10 % mer enn OSEBX de siste 20 handelsdagene
                    før publisering (sluttkurser som var kjent)
    utenfor_rutine  personen har IKKE kjøpt i samme kalendermåned i minst 2 av de 3 foregående
                    årene (Cohen, Malloy og Pomorski 2012: "rutinehandlere" sier lite).
                    Ukjent (None) hvis personen ikke kunne leses ut, eller det mangler 3 års historikk.

    score = antall flagg som er sanne (ukjent teller som 0)
"""

import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from research.harness import reaction_index  # noqa: E402

FLAGS = ["forste_paa_aar", "klynge", "etter_fall", "utenfor_rutine"]
FALL_DAYS, FALL_LIMIT = 20, -0.10
CLUSTER_DAYS, YEAR_DAYS = 10, 365


def clean_buys(trades, issuer_to_ticker):
    rows = []
    for t in trades:
        if t["direction"] != 1 or t["noise"]:
            continue
        tk = issuer_to_ticker.get(t["issuer"])
        if not tk or not t.get("published"):
            continue
        rows.append({**t, "ticker": tk})
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["ts"] = pd.to_datetime(df["published"], utc=True, format="ISO8601")
    return df.sort_values("ts").reset_index(drop=True)


def add_flags(df, panel=None):
    """Legg til flaggene og score. panel trengs for etter_fall (ellers None)."""
    df = df.copy()
    first_seen = df["ts"].min()
    pkey = df["person"].fillna("").str.lower().str.strip() if "person" in df else pd.Series("", index=df.index)
    df["person_key"] = pkey
    first_year, cluster, routine = [], [], []
    by_ticker = {t: g for t, g in df.groupby("ticker")}
    for r in df.itertuples():
        g = by_ticker[r.ticker]
        prev = g[(g["ts"] < r.ts) & (g["ts"] >= r.ts - pd.Timedelta(days=YEAR_DAYS))]
        first_year.append(bool(len(prev) == 0 and r.ts - first_seen >= pd.Timedelta(days=YEAR_DAYS)))
        win = g[(g["ts"] <= r.ts) & (g["ts"] > r.ts - pd.Timedelta(days=CLUSTER_DAYS))]
        keys = {(k or f"id:{i}") for k, i in zip(win["person_key"], win["id"])}
        cluster.append(len(keys) >= 2)
        if not r.person_key or r.ts - first_seen < pd.Timedelta(days=3 * YEAR_DAYS):
            routine.append(None)
            continue
        mine = g[(g["person_key"] == r.person_key) & (g["ts"] < r.ts)]
        years = {d.year for d in mine["ts"] if d.month == r.ts.month and r.ts.year - 3 <= d.year < r.ts.year}
        routine.append(len(years) >= 2)
    # forste_paa_aar er bare meningsfylt når vi har et helt år med historikk før kjøpet
    df["forste_paa_aar"] = first_year
    df["klynge"] = cluster
    df["utenfor_rutine"] = [None if x is None else (not x) for x in routine]
    df["etter_fall"] = None
    if panel is not None:
        Cl, Bc = panel.close.to_numpy(dtype=float), panel.bench_close.to_numpy(dtype=float)
        col = {t: k for k, t in enumerate(panel.close.columns)}
        out = []
        for r in df.itertuples():
            c = col.get(r.ticker)
            e = reaction_index(panel.cal, r.published) - 1   # siste sluttkurs kjent før/ved publisering
            s = e - FALL_DAYS
            if c is None or s < 0 or e >= len(panel.cal):
                out.append(None)
                continue
            ex = (Cl[e, c] / Cl[s, c] - 1) - (Bc[e] / Bc[s] - 1)
            out.append(bool(ex <= FALL_LIMIT) if np.isfinite(ex) else None)
        df["etter_fall"] = out
    df["score"] = sum(as_bool(df[f]).astype(int) for f in FLAGS)
    return df


def as_bool(s):
    """True bare for sanne verdier; None/NaN (ukjent) blir False."""
    return s.map(lambda v: bool(v) if isinstance(v, (bool, np.bool_)) else False).astype(bool)


def flag_summary(df):
    out = {"n": int(len(df))}
    for f in FLAGS:
        known = df[f].notna()
        out[f] = {"kjent": int(known.sum()), "sann": int(df.loc[known, f].astype(bool).sum())}
    out["score_fordeling"] = {int(k): int(v) for k, v in df["score"].value_counts().sort_index().items()}
    out["med_person"] = int((df["person_key"] != "").sum())
    return out
