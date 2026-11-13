#!/usr/bin/env python3
"""
Backtest of forum posts by star users (written and fixed BEFORE looking at any result).

Tests (8, all reported, none added afterwards):
  T1-T2  positive post (sentiment >= 0.3) by a 3-star user -> buy next open, hold 5 / 20 trading days
  T3-T4  same for 2-star users
  T5-T6  same for 0-1 star users (control group)
  T7-T8  negative post (sentiment <= -0.3) by a 3-star user -> buy next open, hold 5 / 20 (expect NEGATIVE excess)
Measure: excess return vs OSEBX over the same days, per trade. One open position per stock per test
(same rule as paper.py). Posts from 2026-08-01 (archive is thin before that); prices 2026-07-13 .. 2026-11-12.
Significance: naive t, and t on weekly averages (entry week) to handle overlapping trades.
Hurdle: t >= 3 on the weekly t (Harvey/Liu/Zhu); Bonferroni for 8 one-sided tests would be about 2.5.
Known bias: stars are TODAY's. Stars reward recent portfolio returns, so 3-star users' positive posts
about stocks they own will look good partly by construction. Results are an upper bound.
The same 8 tests run forward without this bias in paper.py (strategy 4, see FORUM.md).

Usage: python copytrade/backtest_forum.py [prices.csv] [out.csv]
"""
import json, math, os, sys, collections
import numpy as np, pandas as pd
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from copytrade.paper import load_prices, run_trades
from archive_posts import iter_archive
from news_ml.common import load_universe

price_csv = sys.argv[1] if len(sys.argv) > 1 else None
opn, cls = load_prices(price_csv)
cal = opn.index
uni = {u["slug"]: u["ticker"] for u in load_universe()}
prof = json.load(open(f"{REPO}/nordnet_data/copytrade/profiles.json", encoding="utf-8"))
stars = {u: v["stars"] for u, v in prof.items() if v.get("stars") is not None}
scores = {}
for line in open(f"{REPO}/nordnet_data/sentiment/scores.jsonl", encoding="utf-8"):
    if line.strip():
        s = json.loads(line)
        if s.get("model", "regel") != "regel" and s.get("sentiment") is not None:
            scores[s["key"]] = s["sentiment"]

posts, seen = [], set()
for x in iter_archive(f"{REPO}/nordnet_data"):
    if x["key"] in seen: continue
    seen.add(x["key"])
    u = (x.get("profile_url") or "").rstrip("/").rsplit("/", 1)[-1]
    t = x.get("posted_at") or x.get("scraped_at")
    tk = uni.get(x.get("slug"))
    if u not in stars or not t or t < "2026-08-01" or tk not in opn or x["key"] not in scores: continue
    posts.append({"id": x["key"], "published": t, "ticker": tk, "issuer_name": x.get("slug"), "role": "@" + u,
                  "value_nok": 0, "title": "", "stars": stars[u], "sent": scores[x["key"]]})
P = pd.DataFrame(posts).sort_values("published").reset_index(drop=True)
print(f"posts usable: {len(P)}  by stars: {P.stars.value_counts().sort_index().to_dict()}  "
      f"from {P.published.min()[:10]} to {P.published.max()[:10]}; prices to {cal[-1].date()}")

def weekly_t(tr):
    df = pd.DataFrame(tr)
    df["wk"] = pd.to_datetime(df["entry_date"]).dt.to_period("W")
    w = df.groupby("wk")["excess"].mean()
    return (float(w.mean() / (w.std(ddof=1) / math.sqrt(len(w)))) if len(w) > 2 and w.std() > 0 else None), len(w)

tests = [("T1", "3-star, positive", 3, "pos", 5), ("T2", "3-star, positive", 3, "pos", 20),
         ("T3", "2-star, positive", 2, "pos", 5), ("T4", "2-star, positive", 2, "pos", 20),
         ("T5", "0-1 star, positive (control)", 1, "pos", 5), ("T6", "0-1 star, positive (control)", 1, "pos", 20),
         ("T7", "3-star, negative", 3, "neg", 5), ("T8", "3-star, negative", 3, "neg", 20)]
rows = []
for tid, label, grp, side, hold in tests:
    g = P[(P.stars == grp)] if grp >= 2 else P[P.stars <= 1]
    g = g[g.sent >= 0.3] if side == "pos" else g[g.sent <= -0.3]
    tr = [t for t in run_trades(g, opn, hold) if t["status"] == "lukket" and t["excess"] is not None]
    ex = np.array([t["excess"] for t in tr])
    tn = float(ex.mean() / (ex.std(ddof=1) / math.sqrt(len(ex)))) if len(ex) > 2 else None
    tw, nw = weekly_t(tr) if len(tr) > 2 else (None, 0)
    rows.append({"test": tid, "signal": label, "hold": hold, "posts": len(g), "trades": len(ex),
                 "weeks": nw, "avg_excess_pct": round(ex.mean() * 100, 2) if len(ex) else None,
                 "median_pct": round(float(np.median(ex)) * 100, 2) if len(ex) else None,
                 "beat_osebx_pct": round(float((ex > 0).mean()) * 100, 0) if len(ex) else None,
                 "t_naive": None if tn is None else round(tn, 2), "t_weekly": None if tw is None else round(tw, 2)})
R = pd.DataFrame(rows)
pd.set_option("display.width", 200)
print(R.to_string(index=False))
if len(sys.argv) > 2:
    R.to_csv(sys.argv[2], index=False)
