"""
Flokk-filteret (Fase 1)
=======================
Forumet koker og kursen har steget kraftig samme dag -> ikke kjøp nå, og stram inn salget.

Topp (spike), bestemt på forhånd:
    innlegg i aksjen dag d  >= max(MIN_POSTS, MULT x snittet de 20 foregående handelsdagene)
    og kursen steg minst RISE fra slutt d-1 til slutt d.
Bare dager etter at forumarkivet har full dekning telles (minst COVERAGE_POSTS innlegg totalt
per dag i 20 handelsdager), ellers ser alt ut som en topp.

Regler i paper-modus (endrer ikke den låste hovedstrategien, de vises ved siden av):
    blokker   et nytt kjøp hoppes over hvis aksjen hadde en topp de siste BLOCK_DAYS handelsdagene
              før inngang
    stram inn en åpen posisjon selges på neste åpning etter en topp i aksjen

Innlegg teller for kalenderdagen de ble skrevet (Oslo-tid). posted_at er seneste mulige
tidspunkt (se news_ml/forum.py), så et innlegg kan havne en dag for sent, aldri for tidlig.
"""

import glob
import json
import os
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

OSLO = ZoneInfo("Europe/Oslo")
MIN_POSTS, MULT, RISE = 10, 4.0, 0.05
BASE_DAYS, BLOCK_DAYS = 20, 5
COVERAGE_POSTS = 50


def load_post_counts(data_dir, slug_to_ticker, cal):
    """Antall innlegg per handelsdag og ticker (dato x ticker). Helgeinnlegg teller på neste handelsdag."""
    rows = []
    for p in sorted(glob.glob(os.path.join(data_dir, "archive", "posts_*.jsonl"))):
        with open(p, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                r = json.loads(line)
                t, ts = slug_to_ticker.get(r.get("slug")), r.get("posted_at")
                if t and ts:
                    rows.append((r.get("key"), t, ts))
    if not rows:
        return pd.DataFrame(index=cal, dtype=float)
    df = pd.DataFrame(rows, columns=["key", "ticker", "ts"]).drop_duplicates("key")
    ts = pd.to_datetime(df["ts"], utc=True, errors="coerce", format="ISO8601")
    df = df[ts.notna()].copy()
    day = ts[ts.notna()].dt.tz_convert(OSLO).dt.tz_localize(None).dt.normalize().to_numpy()
    pos = cal.searchsorted(day)
    df = df[pos < len(cal)].copy()
    df["d"] = cal[pos[pos < len(cal)]]
    return df.pivot_table(index="d", columns="ticker", values="key", aggfunc="count").reindex(cal).fillna(0.0)


def find_spikes(counts, panel):
    """Toppene som DataFrame: ticker, date, i (kalenderindeks), posts, baseline, ret."""
    if counts.empty or counts.shape[1] == 0:
        return pd.DataFrame(columns=["ticker", "date", "i", "posts", "baseline", "ret"])
    cal = panel.cal
    total = counts.sum(axis=1)
    covered = (total >= COVERAGE_POSTS).astype(int).rolling(BASE_DAYS, min_periods=BASE_DAYS).sum() >= BASE_DAYS
    base = counts.shift(1).rolling(BASE_DAYS, min_periods=BASE_DAYS).mean()
    tick = [t for t in counts.columns if t in panel.close.columns]
    C = panel.close[tick]
    ret = C / C.shift(1) - 1
    cnt = counts[tick]
    thr = np.maximum(MIN_POSTS, MULT * base[tick])
    hit = (cnt >= thr) & (ret >= RISE) & covered.to_numpy()[:, None]
    out = []
    for i, j in zip(*np.where(hit.to_numpy())):
        t = tick[j]
        out.append({"ticker": t, "date": str(cal[i].date()), "i": int(i), "posts": int(cnt.iat[i, j]),
                    "baseline": float(base[t].iat[i]), "ret": float(ret.iat[i, j])})
    return pd.DataFrame(out, columns=["ticker", "date", "i", "posts", "baseline", "ret"])


def coverage_start(counts):
    total = counts.sum(axis=1)
    ok = (total >= COVERAGE_POSTS).astype(int).rolling(BASE_DAYS, min_periods=BASE_DAYS).sum() >= BASE_DAYS
    return int(np.argmax(ok.to_numpy())) if ok.any() else None


def forward_excess(spikes, panel, h):
    """Meravkastning fra åpning dagen etter toppen til åpning h dager senere (None hvis ikke ferdig)."""
    O, B = panel.open.to_numpy(dtype=float), panel.bench_open.to_numpy(dtype=float)
    col = {t: k for k, t in enumerate(panel.open.columns)}
    out = []
    for r in spikes.itertuples():
        i, j, c = r.i + 1, r.i + 1 + h, col[r.ticker]
        if j >= len(panel.cal) or not (np.isfinite(O[i, c]) and np.isfinite(O[j, c])):
            out.append(None)
            continue
        out.append(float((O[j, c] / O[i, c] - 1) - (B[j] / B[i] - 1)))
    return out


def shadow_filter(trades, spikes, panel):
    """Bruk blokker/stram inn på handler fra harness.tradable_returns (dict med i, j, row, net ...).

    Returnerer DataFrame per handel med blocked (bool) og net_tight (netto hvis solgt neste åpning
    etter en topp i holdeperioden, ellers lik net).
    """
    O, B = panel.open.to_numpy(dtype=float), panel.bench_open.to_numpy(dtype=float)
    col = {t: k for k, t in enumerate(panel.open.columns)}
    by_t = {t: g["i"].to_numpy() for t, g in spikes.groupby("ticker")} if len(spikes) else {}
    rows = []
    for k in range(len(trades["i"])):
        t, i, j = trades["ticker"][k], int(trades["i"][k]), int(trades["j"][k])
        s = by_t.get(t, np.array([], dtype=int))
        blocked = bool(((s >= i - BLOCK_DAYS) & (s < i)).any())
        during = s[(s >= i) & (s < j - 1)]
        net_tight = trades["net"][k]
        if len(during):
            x = during.min() + 1
            c = col[t]
            if np.isfinite(O[x, c]) and np.isfinite(O[i, c]):
                gross = O[x, c] / O[i, c] - 1
                bret = B[x] / B[i] - 1
                net_tight = trades["direction"][k] * (gross - bret) - trades["cost"][k]
        rows.append({"ticker": t, "i": i, "blocked": blocked, "tightened": bool(len(during)),
                     "net": float(trades["net"][k]), "net_tight": float(net_tight)})
    return pd.DataFrame(rows)
