"""Ideas 2-5, tested with a holdout.

Procedure (fixed before looking at any result):
  * Development period: signals 2023-01-01 .. 2025-12-31. Holdout: signals from 2026-01-01.
  * Each idea has a small grid of settings, listed in GRIDS below.
  * The setting with the highest t-statistic on the development period (min 30 trades) is
    chosen per idea. Only that one setting is then evaluated on the holdout, once.
  * t-statistics are clustered by signal month (holds overlap, so daily clustering overstates).
  * Costs: Nordnet Student class (0.15% per side Nordic, min 1 kr; 0.2% min 49 kr elsewhere,
    plus 0.15% currency) + bid-ask spread by liquidity (0.05% / 0.4% / 1.5% round trip).
    A "limit order" sensitivity (half the spread) is reported for the chosen settings only.
  * All trades: enter at the next trading day's open, exit at the close H trading days later,
    hedged against the equal-weight market with the stock's beta (betas use past data only).

Ideas
  2 selective   ripple laggards, only big surprises / strong links, Nordic large+mid caps
  3 drift_long  the news stock itself, held longer, Nordic large+mid caps
  4 follow      peers that moved in sympathy without their own news, traded in the SAME direction
  5 ann_type    the news stock itself, by Oslo Børs announcement type (earnings / contract / M&A)
"""
import itertools
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

import backtest as bt

OUT = Path("results")
HOLDS = [5, 10, 20, 40]
DEV_END, HOLD_START = "2025-12-31", "2026-01-01"
NORDIC = (".OL", ".ST", ".CO", ".HE")
SPREAD = {"large": 0.0005, "mid": 0.004, "small": 0.015}
TRADE = 10_000
TYPES = [("earnings", re.compile(r"quarter|\bq[1-4]\b|half[- ]?year|interim|annual (report|result)|results|"
                                 r"financial report|trading update|preliminary", re.I)),
         ("contract", re.compile(r"contract|award|order|letter of intent|\bloi\b|charter|fixture|framework agreement", re.I)),
         ("m&a", re.compile(r"acqui|merger|offer for|takeover|divest|sale of|agreement to (buy|sell|acquire)|combination", re.I)),
         ("guidance", re.compile(r"guidance|profit warning|outlook|trading statement", re.I))]

GRIDS = {
    "2 selective": [dict(hold=h, zmin=z, link=l) for h in [5, 10, 20] for z in [2, 3] for l in ["any", "strong"]],
    "3 drift_long": [dict(hold=h, zmin=z) for h in [10, 20, 40] for z in [2, 3]],
    "4 follow": [dict(hold=h, specific=s) for h in [5, 10, 20] for s in [True, False]],
    "5 ann_type": [dict(hold=h, type=t) for h in [10, 20, 40] for t in ["earnings", "contract", "m&a"]],
}


def ann_type(titles):
    for name, rx in TYPES:
        if any(rx.search(t or "") for t in titles):
            return name
    return "other"


def cost(ticker, bucket, limit=False):
    nordic = ticker.endswith(NORDIC)
    per_side = max(0.0015, 1 / TRADE) if nordic else max(0.002, 49 / TRADE)
    spread = SPREAD[bucket] * (0.5 if limit else 1)
    return 2 * per_side + (0 if nordic else 0.0015) + spread


def returns(d, b, t, side, beta):
    """Hedged returns for each hold length, from the next open."""
    td = d.tdays[b]
    p = np.searchsorted(td, t + 1)
    out = {}
    if p >= len(td):
        return out
    e = td[p]
    has_open = not np.isnan(d.O[e, b])
    lent = d.logO[e, b] if has_open else d.logC[e, b]
    mo_e = d.logMo[e] if has_open else d.logMc[e]
    for h in HOLDS:
        if p + h - 1 < len(td):
            x = td[p + h - 1]
            out[h] = float(side * ((d.logC[x, b] - lent) - beta * (d.logMc[x] - mo_e)))
    return out


def candidates(d, news, links, nw):
    NW, vz, tdev, N = news["NW"], news["vz"], news["tdev"], news["N"]
    seeded = {(d.ix[a], d.ix[b]) for a, b, _ in links if a in d.ix and b in d.ix}
    titles = {}
    if len(nw):
        for (dd, tk), g in nw[nw.material].groupby(["tday", "ticker"]):
            titles[(dd, tk)] = list(g.title.fillna(""))
    rows = []
    beta = sd = edges = None
    T = len(d.dates)
    for t in range(bt.P["lookback"], T - 6):
        if (t - bt.P["lookback"]) % bt.P["rebuild"] == 0:
            beta, sd, edges = bt.build(d, t, links)
        rmt = d.rm[t]
        if np.isnan(rmt):
            continue
        g_c = set(np.where((vz[t] >= bt.P["news_vz"]) & (N[t] >= bt.P["news_min"]) & (np.abs(tdev[t]) >= bt.P["tone_dev"]))[0])
        n_c = set(np.where(NW[t] > 0)[0])
        date = str(d.dates[t])
        for a in g_c | n_c:
            if np.isnan(beta[a]) or np.isnan(d.r[t, a]) or not sd[a] > 0:
                continue
            abn = d.r[t, a] - beta[a] * rmt
            z = abn / sd[a]
            if a in g_c:
                dirn = int(np.sign(tdev[t, a]))
                if z * dirn < bt.P["price_z"]:
                    continue
            else:
                if abs(z) < bt.P["newsweb_z"]:
                    continue
                dirn = int(np.sign(z))
            peers = edges.get(a, [])
            specific = sum((NW[t, b] > 0) or (vz[t, b] >= bt.P["news_vz"]) for b, _, _ in peers) < 2
            atype = ann_type(titles.get((date, d.tickers[a]), [])) if a in n_c else "none"
            base = dict(signal=date, source_ticker=d.tickers[a], z=abs(float(z)), dirn=dirn, specific=specific, atype=atype)

            def add(kind, b, side, **kw):
                rr = returns(d, b, t, side, beta[b])
                if rr:
                    rows.append(dict(base, kind=kind, ticker=d.tickers[b], side=side,
                                     bucket=bt.bucket(d.adv[t, b]), **kw, **{f"r{h}": v for h, v in rr.items()}))
            add("news_stock", a, dirn)
            for b, w, slope in peers:
                if np.isnan(beta[b]) or np.isnan(d.r[t, b]) or not sd[b] > 0:
                    continue
                exp, act = slope * abn, d.r[t, b] - beta[b] * rmt
                s = np.sign(exp)
                strong = (a, b) in seeded or w >= 0.4
                if abs(exp) >= bt.P["min_expected"] and act * s < bt.P["lag_frac"] * abs(exp):
                    add("laggard", b, int(s), strong=strong, gap=float(abs(exp) - act * s))
                quiet = NW[t, b] == 0 and not (vz[t, b] >= 1)
                if quiet and act * s >= max(abs(exp), sd[b]):
                    add("sympathy", b, int(s), strong=strong)
    c = pd.DataFrame(rows)
    c["nordic_lm"] = c.ticker.str.endswith(NORDIC) & c.bucket.isin(["large", "mid"])
    return c


def select(c, idea, s):
    if idea == "2 selective":
        g = c[(c.kind == "laggard") & c.nordic_lm & (c.z >= s["zmin"])]
        if s["link"] == "strong":
            g = g[g.strong == True]
        # fewer, bigger bets: per event keep at most the 2 biggest expected gaps
        g = g.sort_values("gap", ascending=False).groupby(["signal", "source_ticker"]).head(2)
    elif idea == "3 drift_long":
        g = c[(c.kind == "news_stock") & c.nordic_lm & (c.z >= s["zmin"])]
    elif idea == "4 follow":
        g = c[(c.kind == "sympathy") & c.nordic_lm]
        if s["specific"]:
            g = g[g.specific == True]
    else:
        g = c[(c.kind == "news_stock") & c.nordic_lm & (c.atype == s["type"])]
    g = g.drop_duplicates(["signal", "ticker"])
    return g.assign(gross=g[f"r{s['hold']}"]).dropna(subset=["gross"])


def score(g, limit=False):
    if len(g) == 0:
        return dict(trades=0)
    net = g.gross - g.apply(lambda r: cost(r.ticker, r.bucket, limit), axis=1)
    m = net.groupby(g.signal.str[:7]).mean()
    t = m.mean() / m.std() * np.sqrt(len(m)) if len(m) > 2 and m.std() > 0 else np.nan
    return dict(trades=int(len(g)), months=int(len(m)), gross=round(float(g.gross.mean()), 4),
                net=round(float(net.mean()), 4), win=round(float((net > 0).mean()), 3),
                t=round(float(t), 2) if not np.isnan(t) else None)


def main():
    u = json.loads((bt.DATA / "universe.json").read_text())
    links = [tuple(x) for x in u["links"]]
    d, _ = bt.load_prices()
    nw, gd = bt.load_newsweb(d.Cdf), bt.load_gdelt(d.Cdf)
    news = bt.build_news(d.Cdf, nw, gd)
    c = candidates(d, news, links, nw)
    c.to_csv(OUT / "idea_candidates.csv.gz", index=False)
    dev, hold = c[c.signal <= DEV_END], c[c.signal >= HOLD_START]
    print(f"candidates: {len(c)} (dev {len(dev)}, holdout {len(hold)})", flush=True)

    report = dict(procedure=__doc__, grids=GRIDS, ideas={})
    for idea, grid in GRIDS.items():
        tried = []
        for s in grid:
            r = score(select(dev, idea, s))
            tried.append(dict(setting=s, dev=r))
        ok = [x for x in tried if x["dev"].get("trades", 0) >= 30 and x["dev"].get("t") is not None]
        best = max(ok, key=lambda x: x["dev"]["t"]) if ok else None
        res = dict(tried_on_dev=tried, chosen=best["setting"] if best else None)
        if best:
            hsel = select(hold, idea, best["setting"])
            res["dev"] = best["dev"]
            res["holdout"] = score(hsel)                      # evaluated once
            res["holdout_limit_orders"] = score(hsel, limit=True)
            res["dev_limit_orders"] = score(select(dev, idea, best["setting"]), limit=True)
        report["ideas"][idea] = res
        print(idea, "chosen", res.get("chosen"), "| dev", res.get("dev"), "| HOLDOUT", res.get("holdout"),
              "| holdout w/ limit orders", res.get("holdout_limit_orders"), flush=True)
    (OUT / "ideas.json").write_text(json.dumps(report, indent=1, default=str))


if __name__ == "__main__":
    main()
