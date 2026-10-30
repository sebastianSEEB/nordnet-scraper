"""
Forumsentiment fra Nordnet-scraperen som ekstra signal i nyhets-ML
=================================================================
Bygger daglige forum-features per aksje fra
    nordnet_data/archive/posts_*.jsonl     (innleggene, med posted_at)
    nordnet_data/sentiment/scores.jsonl    (Claude Haiku: sentiment -1..1, relevans 0..1)

Tidsregel (samme som sentiment_analysis.py): et innlegg teller for handelsdag d bare
hvis det er skrevet før 16:00 Oslo-tid den dagen. posted_at er allerede satt til
SENESTE mulige tidspunkt, så et innlegg kan havne en dag for sent, aldri for tidlig.

Features (alle bruker bare dager t og bakover):
    f_n5          antall relevante innlegg siste 5 dager
    f_attn_z      oppmerksomhet: innlegg siste 5 d mot aksjens eget snitt hittil
    f_sent5       relevansvektet sentiment siste 5 dager (tom hvis < 3 innlegg)
    f_sent20      relevansvektet sentiment siste 20 dager (tom hvis < 5 innlegg)
    f_sent_chg    f_sent5 - f_sent20 (stemningen snur)
    f_div5        rang(sentiment 5 d) - rang(kursendring 5 d): forumet positivt mens kursen faller
    f_newsy5      andel innlegg som er nyhet/analyse siste 5 dager
"""

import glob
import json
import os
from datetime import datetime, time as dtime, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

OSLO = ZoneInfo("Europe/Oslo")
CUTOFF = dtime(16, 0)
MIN_RELEVANCE = 0.3
FORUM_FEATURES = ["f_n5", "f_attn_z", "f_sent5", "f_sent20", "f_sent_chg", "f_div5", "f_newsy5"]
FORUM_LABELS = {
    "f_n5": "Antall innlegg 5 d", "f_attn_z": "Forum-oppmerksomhet mot normalt",
    "f_sent5": "Sentiment 5 d", "f_sent20": "Sentiment 20 d", "f_sent_chg": "Stemningen snur (5 d mot 20 d)",
    "f_div5": "Forum positivt mens kursen faller", "f_newsy5": "Andel nyhet/analyse-innlegg",
}


def load_forum(data_dir, slug_to_ticker):
    posts = {}
    for p in sorted(glob.glob(os.path.join(data_dir, "archive", "posts_*.jsonl"))):
        with open(p, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                r = json.loads(line)
                t = slug_to_ticker.get(r.get("slug"))
                ts = r.get("posted_at")
                if t and ts:
                    posts[r["key"]] = (t, ts)
    scores = {}
    sp = os.path.join(data_dir, "sentiment", "scores.jsonl")
    if os.path.exists(sp):
        with open(sp, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    r = json.loads(line)
                    scores[r["key"]] = (float(r.get("sentiment") or 0), float(r.get("relevance") or 0),
                                        r.get("category") or "")
    rows = [(t, ts, *scores[k]) for k, (t, ts) in posts.items() if k in scores]
    df = pd.DataFrame(rows, columns=["ticker", "posted_at", "sent", "rel", "cat"])
    if df.empty:
        return df
    df["posted_at"] = pd.to_datetime(df["posted_at"], utc=True, format="ISO8601", errors="coerce")
    return df.dropna(subset=["posted_at"])


def signal_days(posted_at, cal):
    cut = pd.DatetimeIndex([datetime.combine(d.date(), CUTOFF, tzinfo=OSLO).astimezone(timezone.utc)
                            for d in cal]).as_unit("ns").asi8
    idx = np.searchsorted(cut, pd.DatetimeIndex(posted_at).as_unit("ns").asi8, side="right")
    return idx


def build_forum_features(data_dir, slug_to_ticker, cal, tickers, ret5):
    """Returnerer (features long-format date,ticker,f_*, info-dict). ret5: DataFrame dato x ticker."""
    df = load_forum(data_dir, slug_to_ticker)
    info = {"posts_scored": int(len(df)), "first_day": None, "last_day": None, "days": 0}
    if df.empty:
        return pd.DataFrame(columns=["date", "ticker"] + FORUM_FEATURES), info
    df["i"] = signal_days(df["posted_at"], cal)
    df = df[(df["i"] < len(cal)) & df["ticker"].isin(tickers)]
    df["date"] = cal[df["i"].to_numpy()]
    rel = df[df["rel"] >= MIN_RELEVANCE].copy()
    rel["ws"] = rel["sent"] * rel["rel"]
    rel["newsy"] = rel["cat"].isin(["nyhet", "analyse"]).astype(float)

    def piv(frame, col, agg="sum"):
        return frame.pivot_table(index="date", columns="ticker", values=col, aggfunc=agg)

    first = df["date"].min()
    span = cal[(cal >= first) & (cal <= cal[-1])]
    T = list(tickers)
    n = piv(rel.assign(one=1.0), "one").reindex(index=span, columns=T).fillna(0.0)
    w = piv(rel, "rel").reindex(index=span, columns=T).fillna(0.0)
    ws = piv(rel, "ws").reindex(index=span, columns=T).fillna(0.0)
    nw = piv(rel, "newsy").reindex(index=span, columns=T).fillna(0.0)

    n5, n20 = n.rolling(5, min_periods=1).sum(), n.rolling(20, min_periods=1).sum()
    sent5 = (ws.rolling(5, min_periods=1).sum() / w.rolling(5, min_periods=1).sum()).where(n5 >= 3)
    sent20 = (ws.rolling(20, min_periods=1).sum() / w.rolling(20, min_periods=1).sum()).where(n20 >= 5)
    # oppmerksomhet: siste 5 dager mot aksjens eget snitt HITTIL (ekspanderende, ingen fremtid)
    daily_avg = n.expanding(min_periods=10).mean().shift(5)
    attn = (n5 / 5 - daily_avg) / np.sqrt(daily_avg + 0.2)
    r5 = ret5.reindex(index=span, columns=T)
    div = sent5.rank(axis=1, pct=True) - r5.where(sent5.notna()).rank(axis=1, pct=True)

    feats = {"f_n5": n5, "f_attn_z": attn, "f_sent5": sent5, "f_sent20": sent20,
             "f_sent_chg": sent5 - sent20, "f_div5": div,
             "f_newsy5": nw.rolling(5, min_periods=1).sum() / n5.replace(0, np.nan)}
    long = pd.concat([m.stack(future_stack=True).rename(k) for k, m in feats.items()], axis=1)
    long.index.names = ["date", "ticker"]
    long = long.reset_index()
    # de første 20 dagene er oppvarming for rullende vinduer
    warm = span[min(19, len(span) - 1)]
    long = long[long["date"] >= warm]
    info.update({"first_day": str(first.date()), "warm_from": str(warm.date()), "last_day": str(span[-1].date()),
                 "days": int((span >= warm).sum()), "tickers_with_posts": int((n.sum() > 0).sum()),
                 "posts_relevant": int(len(rel))})
    return long, info
