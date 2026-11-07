"""
Oppmerksomhets-features fra børsmeldingene (Fase 1)
==================================================
Investorer har begrenset oppmerksomhet. Forskningen finner at nyheter som kommer når
markedet er distrahert, prises inn tregere (DellaVigna og Pollet 2009: fredag;
Hirshleifer, Lim og Teoh 2009: mange rapporter samme dag), og at aksjer stiger i
måneder der man venter utbytte (Hartzmark og Solomon 2013).

Hendelser (alle med tidspunkt som var kjent da de skjedde):
    report_events      kvartals-/årsrapporter per aksje, t0 = første handelsdag der 16:20 kommer etter
                       publisering, med flaggene travel_morgen og fredag_etter_stengning
    dividend_months    aksje-måneder der aksjen gikk eks utbytte samme måned i fjor
    placement_events   rettede emisjoner, med flagg for om det er varslet en reparasjonsemisjon
                       (nevnt i meldinger fra selskapet fra 2 dager før til slutten av t0)

NB: meldingene dekker bare selskapene i watchlisten (~120), så "travel morgen" betyr mange
rapporter blant disse, ikke på hele Oslo Børs.

daily_features() gir de samme tingene som daglige matriser til nyhetsmodellen. De brukes
bare hvis research/config.json -> phase1.attention_in_model er true, og det skal den først
være når testene i research/phase1.py har bestått.
"""

import glob
import json
import os
import re
import sys
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from news_ml.common import NEWS_DIR, classify  # noqa: E402

OSLO = ZoneInfo("Europe/Oslo")
CLOSE_MIN = 16 * 60 + 20
BUSY_Q, BUSY_WINDOW, BUSY_MIN_OBS = 0.90, 250, 20
DIV_RE = re.compile(r"dividend|utbytte|distribution|return of (?:paid[- ]in )?capital|tilbakebetaling", re.I)
NOT_DIV_RE = re.compile(r"repair|rights|tegningsrett|subscription|emisjon|issue", re.I)
PLACEMENT_RE = re.compile(r"private placement|rettet emisjon|rettede emisjon|directed (?:share )?issue", re.I)
REPAIR_RE = re.compile(r"subsequent offering|repair offering|reparasjonsemisjon|etterfølgende emisjon|"
                       r"subsequent repair", re.I)

ATTENTION_FEATURES = ["att_reports_today", "att_busy_report", "att_fri_report", "att_div_month",
                      "att_placement_norepair_90", "att_placement_repair_90"]
ATTENTION_LABELS = {
    "att_reports_today": "Antall rapporter i dag (watchlisten)", "att_busy_report": "Rapport på travel morgen",
    "att_fri_report": "Rapport fredag etter stengning", "att_div_month": "Ventet utbyttemåned",
    "att_placement_norepair_90": "Rettet emisjon uten reparasjon (90 d)",
    "att_placement_repair_90": "Rettet emisjon med reparasjon (90 d)",
}


def load_messages(news_dir=NEWS_DIR):
    rows = []
    for p in sorted(glob.glob(os.path.join(news_dir, "messages_*.jsonl"))):
        with open(p, encoding="utf-8") as f:
            rows += [json.loads(line) for line in f if line.strip()]
    if not rows:
        return pd.DataFrame(columns=["issuer", "published", "title", "category", "body"])
    df = pd.DataFrame(rows)
    for c in ("title", "category", "body"):
        if c not in df:
            df[c] = ""
        df[c] = df[c].fillna("")
    df["ts"] = pd.to_datetime(df["published"], utc=True, errors="coerce", format="ISO8601")
    return df[df["ts"].notna()].copy()


def _t0(ts, cal):
    """Første handelsdag der børsslutt (16:20) kommer etter publisering."""
    local = ts.dt.tz_convert(OSLO)
    d = local.dt.tz_localize(None).dt.normalize().to_numpy()
    pos = cal.searchsorted(d)
    on = (pos < len(cal)) & (cal[np.minimum(pos, len(cal) - 1)] == d)
    after = (local.dt.hour * 60 + local.dt.minute).to_numpy() >= CLOSE_MIN
    return np.where(on & after, pos + 1, pos)


def report_events(msgs, issuer_to_ticker, cal):
    df = msgs.copy()
    df["ticker"] = df["issuer"].map(issuer_to_ticker)
    df = df[df["ticker"].notna()].copy()
    kind = [classify(t, c) for t, c in zip(df["title"], df["category"])]
    unclear = [k == "other" and len(b) > 0 for k, b in zip(kind, df["body"])]
    df["kind"] = [classify(t + " " + b[:400], c) if u else k
                  for k, u, t, b, c in zip(kind, unclear, df["title"], df["body"], df["category"])]
    df = df[df["kind"] == "report"].copy()
    if df.empty:
        return pd.DataFrame(columns=["ticker", "published", "t0", "fredag_etter_stengning", "travel_morgen"])
    df["t0"] = _t0(df["ts"], cal)
    df = df[df["t0"] < len(cal)].sort_values("ts").drop_duplicates(["ticker", "t0"], keep="first")
    local = df["ts"].dt.tz_convert(OSLO)
    wd, mins = local.dt.weekday, local.dt.hour * 60 + local.dt.minute
    df["fredag_etter_stengning"] = ((wd == 4) & (mins >= CLOSE_MIN)) | (wd >= 5)
    busy = busy_days(df, cal)
    df["travel_morgen"] = busy.to_numpy()[df["t0"].to_numpy()]
    df["published"] = df["ts"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return df[["ticker", "published", "t0", "fredag_etter_stengning", "travel_morgen"]].reset_index(drop=True)


def report_counts(rep, cal):
    return pd.Series(np.bincount(rep["t0"].to_numpy(), minlength=len(cal))[:len(cal)].astype(float), index=cal)


def busy_days(rep, cal):
    """Dag t er travel hvis antall rapporter >= 90-persentilen av de 250 foregående dagene med rapporter."""
    n = report_counts(rep, cal)
    nz = n.where(n > 0)
    thr = nz.shift(1).rolling(BUSY_WINDOW, min_periods=BUSY_MIN_OBS).quantile(BUSY_Q)
    return (n > 0) & thr.notna() & (n >= thr)


def dividend_months(msgs, issuer_to_ticker):
    """{(ticker, 'YYYY-MM')} der aksjen gikk eks utbytte (meldingsmåned i kategorien EX DATE)."""
    df = msgs[(msgs["category"].str.upper() == "EX DATE") & msgs["title"].str.contains(DIV_RE)
              & ~msgs["title"].str.contains(NOT_DIV_RE)].copy()
    df["ticker"] = df["issuer"].map(issuer_to_ticker)
    df = df[df["ticker"].notna()]
    months = df["ts"].dt.tz_convert(OSLO).dt.strftime("%Y-%m")
    return set(zip(df["ticker"], months))


def predicted_dividend_signals(div_months, last_month):
    """Signal ved starten av måneden M for aksjer som gikk eks utbytte i M - 12.

    published = siste kalenderdag før M (bare dato -> regnes som etter børsslutt -> kjøp første åpning i M).
    """
    rows = []
    for t, ym in sorted(div_months):
        m = pd.Period(ym, "M") + 12
        if str(m) > last_month:
            continue
        rows.append({"ticker": t, "published": str((m.start_time - pd.Timedelta(days=1)).date()),
                     "direction": 1, "id": f"div:{t}:{m}", "month": str(m)})
    return pd.DataFrame(rows, columns=["ticker", "published", "direction", "id", "month"])


def placement_events(msgs, issuer_to_ticker, cal):
    df = msgs.copy()
    df["ticker"] = df["issuer"].map(issuer_to_ticker)
    df = df[df["ticker"].notna()].copy()
    pl = df[df["title"].str.contains(PLACEMENT_RE)].copy()
    if pl.empty:
        return pd.DataFrame(columns=["ticker", "published", "t0", "reparasjon"])
    pl["t0"] = _t0(pl["ts"], cal)
    pl = pl[pl["t0"] < len(cal)].sort_values("ts").drop_duplicates(["ticker", "t0"], keep="first")
    rep_msgs = df[(df["title"] + " " + df["body"]).str.contains(REPAIR_RE)]
    by_t = {t: g["ts"] for t, g in rep_msgs.groupby("ticker")}
    flags = []
    for r in pl.itertuples():
        end = pd.Timestamp(cal[r.t0]).tz_localize(OSLO) + pd.Timedelta(hours=16, minutes=20)
        s = by_t.get(r.ticker)
        flags.append(bool(s is not None and ((s >= r.ts - pd.Timedelta(days=2)) & (s <= end)).any()))
    pl["reparasjon"] = flags
    pl["published"] = [str(cal[i].date()) for i in pl["t0"]]   # bare dato: handel først dagen etter t0
    return pl[["ticker", "published", "t0", "reparasjon"]].reset_index(drop=True)


def daily_features(cal, tickers, issuer_to_ticker, msgs=None):
    """Daglige matriser (dato x ticker) for nyhetsmodellen. Alt er kjent ved slutt av dag t."""
    msgs = load_messages() if msgs is None else msgs
    T = list(tickers)
    zero = pd.DataFrame(0.0, index=cal, columns=T)
    f = {}
    rep = report_events(msgs, issuer_to_ticker, cal)
    n = report_counts(rep, cal) if len(rep) else pd.Series(0.0, index=cal)
    f["att_reports_today"] = pd.DataFrame({t: n for t in T}, index=cal)
    busy_rep, fri_rep = zero.copy(), zero.copy()
    for r in rep[rep["ticker"].isin(T)].itertuples():
        if r.travel_morgen:
            busy_rep.iat[r.t0, T.index(r.ticker)] = 1.0
        if r.fredag_etter_stengning:
            fri_rep.iat[r.t0, T.index(r.ticker)] = 1.0
    f["att_busy_report"], f["att_fri_report"] = busy_rep, fri_rep
    divm = dividend_months(msgs, issuer_to_ticker)
    ym = pd.Series([d.strftime("%Y-%m") for d in cal], index=cal)
    prev = {(t, str(pd.Period(m, "M") + 12)) for t, m in divm}
    f["att_div_month"] = pd.DataFrame({t: [1.0 if (t, m) in prev else 0.0 for m in ym] for t in T}, index=cal)
    pl = placement_events(msgs, issuer_to_ticker, cal)
    for key, flag in (("att_placement_norepair_90", False), ("att_placement_repair_90", True)):
        m = zero.copy()
        for r in pl[(pl["reparasjon"] == flag) & pl["ticker"].isin(T)].itertuples():
            m.iat[r.t0, T.index(r.ticker)] += 1.0
        f[key] = m.rolling(90, min_periods=1).sum()
    return f
