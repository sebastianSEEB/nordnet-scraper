"""Ripple v2 backtest.

News sources
  newsweb - Oslo Børs official announcements (exact publish time), material categories only.
            Direction = sign of the confirmed price reaction (titles carry no reliable tone).
  gdelt   - worldwide news volume + tone per day (non-Oslo names). Event = volume spike,
            direction = tone vs its own 60-day normal, which the price must confirm.

Modes (all hedged against an equal-weight EU/EEA market index)
  ripple   - trade A's linked peers that have NOT reacted yet, in the expected direction
  rebound  - A's news is company-specific; fade peers that moved in sympathy with no news of their own
  drift_A  - control: trade A itself in the news direction

Upgrades tested
  red-day boost   1.5x size for good-news ripple trades on days the market fell >= 1%
  momentum        12-1 month market-relative momentum of the traded stock: half size when it fights the trade;
                  plus a momentum-matched benchmark to see whether returns are just momentum
  liquidity       Corwin-Schultz bid-ask spread from daily high/low -> cost per trade; large/mid/small buckets
                  by median daily turnover; small caps also tested long-only
  slippage rule   skip a trade when its estimated cost exceeds 1/3 of the expected move
  stops           hedged stop at -3% / -5% checked at each close, exit at the next open (gaps included)
  portfolio       max 3 open trades per sector, max 25 open in total

No look-ahead
  - network and betas rebuilt every 21 trading days from the previous 252 days only
  - news, liquidity and spread baselines use past data only
  - a NewsWeb message published after 16:20 Oslo time counts for the NEXT trading day
  - trades enter at the next trading day's open, exit at the close 5 trading days after the signal
"""
import json
import re
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

DATA, OUT = Path("data"), Path("results")
P = dict(lookback=252, rebuild=21, min_link=0.25, max_links=8, news_min=3, news_vz=2.0,
         tone_dev=0.75, price_z=1.5, newsweb_z=2.0, min_expected=0.004, lag_frac=0.5,
         min_peers=2, max_peers=5, hold=5, red_day=-0.01, bad_ret=0.4, close_local="16:20",
         fee=0.0015, bucket_cost={"large": 0.003, "mid": 0.01, "small": 0.02},
         large_eur=20e6, small_eur=2e6, skip_ratio=1 / 3, red_boost=1.5, fight_size=0.5,
         stops=[0.03, 0.05], default_stop={"ripple": 0.05, "rebound": None, "drift_A": None},
         sector_cap=3, max_open=25, notional=10_000, capital=100_000)
FX = {".OL": 0.085, ".ST": 0.087, ".CO": 0.134}
ROUTINE = re.compile(r"notifiable trad|mandatory notification|primary insider|ex[- ]?div|ex[- ]?date|"
                     r"buy[- ]?back|share repurchase|key information|total number of|voting rights|"
                     r"annual general meeting|general meeting|financial calendar|invitation to|"
                     r"presentation of|will (present|publish|report)|webcast|share capital|"
                     r"major shareholding|disclosure of large", re.I)
MATERIAL_CATS = re.compile(r"INSIDE INFORMATION|FINANCIAL REPORT|NON-REGULATORY PRESS|ADDITIONAL REGULATED", re.I)


# ================================================================ prices
class Px:
    pass


def corwin_schultz(h, l):
    """Bid-ask spread estimate from two consecutive days' high/low (Corwin & Schultz 2012)."""
    hl = np.log(h / l) ** 2
    beta = hl + hl.shift(-1)
    gamma = np.log(np.maximum(h, h.shift(-1)) / np.minimum(l, l.shift(-1))) ** 2
    k = 3 - 2 * np.sqrt(2)
    alpha = (np.sqrt(2 * beta) - np.sqrt(beta)) / k - np.sqrt(gamma / k)
    s = 2 * (np.exp(alpha) - 1) / (1 + np.exp(alpha))
    return s.clip(lower=0)


def load_prices():
    px = pd.read_csv(DATA / "prices.csv.gz")
    piv = lambda c: px.pivot(index="date", columns="ticker", values=c).sort_index()
    C = piv("close")
    keep = C.notna().sum() >= 300
    C = C.loc[:, keep]
    O, H, L, V = (piv(c).reindex_like(C) for c in ["open", "high", "low", "volume"])
    O = O.where(O > 0)
    prev = C.ffill().shift(1)
    r = np.log(C / prev).where(C.notna())
    bad = r.abs() > P["bad_ret"]
    ii, jj = np.where(bad.values)
    flags = [(r.index[i], r.columns[j], round(float(r.iat[i, j]), 3)) for i, j in zip(ii, jj)]
    r = r.mask(bad)
    on = np.log(O / prev).where(O.notna() & ~bad)
    rm = r.mean(axis=1).where(r.notna().mean(axis=1) > 0.3)
    mon = on.mean(axis=1).fillna(0)

    d = Px()
    d.dates, d.tickers = C.index.values, list(C.columns)
    d.ix = {t: i for i, t in enumerate(d.tickers)}
    d.C, d.O, d.r, d.rm = C.values, O.values, r.values, rm.values
    d.Cdf, d.rdf, d.rmdf = C, r, rm
    d.logC = np.log(C.values)
    d.logO = np.log(O.values)
    d.logCf = np.log(C.ffill().values)
    lm = np.cumsum(np.nan_to_num(rm.values))
    d.logMc = lm
    d.logMo = np.concatenate([[0], lm[:-1]]) + mon.values
    d.tdays = [np.where(~np.isnan(d.C[:, k]))[0] for k in range(len(d.tickers))]
    # 12-1 month momentum relative to the market
    T = len(d.dates)
    mom = np.full_like(d.C, np.nan)
    a, b = 21, 252
    mom[b:] = (d.logCf[b - a:T - a] - d.logCf[:T - b]) - (lm[b - a:T - a] - lm[:T - b])[:, None]
    d.mom = mom
    # liquidity (EUR turnover, past 60 trading days) and spread (past 20 days, Corwin-Schultz)
    fx = np.array([next((v for s, v in FX.items() if t.endswith(s)), 1.0) for t in d.tickers])
    turn = (C * V) * fx
    adv = pd.DataFrame(np.nan, index=C.index, columns=C.columns)
    spr = adv.copy()
    for t in C.columns:
        s = turn[t].dropna()
        adv.loc[s.index, t] = s.rolling(60, min_periods=20).median().shift(1)
        hh, ll = H[t].dropna(), L[t].dropna()
        idx = hh.index.intersection(ll.index)
        cs = corwin_schultz(hh[idx], ll[idx]).rolling(20, min_periods=10).mean().shift(2)
        spr.loc[cs.index, t] = cs
    d.adv, d.spread = adv.ffill().values, spr.ffill().values
    u = json.loads((DATA / "universe.json").read_text())
    d.sector = [u["universe"].get(t, ["", "Other"])[1] for t in d.tickers]
    d.name = [u["universe"].get(t, [t])[0] for t in d.tickers]
    weekday = pd.to_datetime(C.index).dayofweek
    bucket_now = pd.Series(adv.iloc[-1]).apply(bucket)
    sanity = dict(tickers=len(d.tickers), dropped_short_history=list(keep[~keep].index),
                  days=T, first=C.index[0], last=C.index[-1], weekend_dates=int((weekday >= 5).sum()),
                  missing_open_share=round(float(O[C.notna()].isna().mean().mean()), 4),
                  extreme_moves_removed=flags[:40], n_extreme=len(flags),
                  bucket_counts_today=bucket_now.value_counts().to_dict(),
                  median_spread_by_bucket={b: round(float(np.nanmedian(spr.iloc[-1][bucket_now == b])), 4)
                                           for b in ["large", "mid", "small"] if (bucket_now == b).any()})
    return d, sanity


def bucket(adv_eur):
    if not adv_eur or np.isnan(adv_eur):
        return "small"
    return "large" if adv_eur >= P["large_eur"] else ("small" if adv_eur < P["small_eur"] else "mid")


# ================================================================ news
def load_newsweb(C):
    p = DATA / "newsweb.csv.gz"
    if not p.exists():
        return pd.DataFrame()
    nw = pd.read_csv(p)
    nw["ticker"] = nw.issuer.astype(str) + ".OL"
    nw = nw[nw.ticker.isin(C.columns)].copy()
    t = pd.to_datetime(nw.published_utc, utc=True)
    loc = t.dt.tz_convert("Europe/Oslo")
    nw["local_date"], nw["local_time"] = loc.dt.strftime("%Y-%m-%d"), loc.dt.strftime("%H:%M")
    nw["utc_date"] = t.dt.strftime("%Y-%m-%d")
    nw["session"] = np.select([nw.local_time < "09:00", nw.local_time >= P["close_local"]],
                              ["pre-open", "after-close"], "intraday")
    nw["material"] = nw.category.fillna("").str.contains(MATERIAL_CATS) & ~nw.title.fillna("").str.contains(ROUTINE)
    out = []
    for tk, g in nw.groupby("ticker"):
        td = C[tk].dropna().index.values
        tgt = np.where(g.session == "after-close",
                       (pd.to_datetime(g.local_date) + pd.Timedelta(days=1)).dt.strftime("%Y-%m-%d"),
                       g.local_date)
        pos, naive = np.searchsorted(td, tgt), np.searchsorted(td, g.utc_date.values)
        ok = pos < len(td)
        out.append(g[ok].assign(tday=td[pos[ok]], naive_day=td[np.minimum(naive[ok], len(td) - 1)]))
    return pd.concat(out) if out else pd.DataFrame()


def load_gdelt(C):
    empty = pd.DataFrame(np.nan, index=C.index, columns=C.columns)
    files = sorted(DATA.glob("gdelt_*.csv.gz"))
    if not files:
        return empty, empty.copy(), empty.fillna(0)
    nd = pd.concat(pd.read_csv(f) for f in files)
    nd = nd[nd.ticker.isin(C.columns) & (nd.articles.fillna(0) > 0)]
    N, T = empty.fillna(0), empty.copy()
    for tk, g in nd.groupby("ticker"):
        td = C[tk].dropna().index.values
        pos = np.searchsorted(td, g.date_utc.values)
        ok = pos < len(td)
        g = g[ok].assign(tday=td[pos[ok]], tw=lambda x: x.tone * x.articles)
        a = g.groupby("tday").agg(articles=("articles", "sum"), tw=("tw", "sum"))
        N.loc[a.index, tk] = a.articles
        T.loc[a.index, tk] = a.tw / a.articles
    N = N.where(C.notna())
    vz, tdev = empty.copy(), empty.copy()
    for tk in nd.ticker.unique():
        n = np.log1p(N[tk].dropna())
        vz.loc[n.index, tk] = (n - n.rolling(60, min_periods=40).mean().shift(1)) / \
            n.rolling(60, min_periods=40).std().shift(1).replace(0, np.nan)
        t = T[tk].dropna()
        tdev.loc[t.index, tk] = t - t.rolling(60, min_periods=20).median().shift(1)
    return vz, tdev, N


def build_news(C, nw, gd, shift=0):
    vz, tdev, N = gd
    NW = pd.DataFrame(0.0, index=C.index, columns=C.columns)
    if len(nw):
        for (dd, tk), v in nw[nw.material].groupby(["tday", "ticker"]).size().items():
            NW.at[dd, tk] = v
    if shift:
        sh = lambda df: pd.DataFrame({t: df[t].dropna().shift(shift).reindex(C.index) for t in C.columns})
        NW, vz, tdev, N = sh(NW.where(C.notna())).fillna(0), sh(vz), sh(tdev), sh(N.where(C.notna())).fillna(0)
    return dict(NW=NW.values, vz=vz.values, tdev=tdev.values, N=N.fillna(0).values, NWdf=NW, vzdf=vz, Ndf=N)


# ================================================================ network
def build(d, k, links):
    w = d.rdf.iloc[k - P["lookback"]:k]
    m = d.rmdf.iloc[k - P["lookback"]:k]
    w = w.loc[:, w.notna().mean() > 0.7]
    ok = m.notna()
    b = w[ok].apply(lambda s: s.cov(m[ok]) / m[ok].var())
    res = w - np.outer(m.fillna(0), b)
    corr, cov, var = res.corr(min_periods=120), res.cov(min_periods=120), res.var()
    sd = res.iloc[-60:].std()
    beta, sdv = np.full(len(d.tickers), np.nan), np.full(len(d.tickers), np.nan)
    for t in b.index:
        beta[d.ix[t]], sdv[d.ix[t]] = b[t], sd[t]
    edges = {}
    for a in corr:
        c = corr[a].drop(a).dropna()
        c = c[c >= P["min_link"]].sort_values(ascending=False).head(P["max_links"])
        edges[d.ix[a]] = [(d.ix[x], float(c[x]), float(cov.at[a, x] / var[a])) for x in c.index]
    for a, x, sign in links:
        if a in corr and x in corr and pd.notna(corr.at[a, x]):
            if d.ix[x] not in [e[0] for e in edges.get(d.ix[a], [])]:
                slope = cov.at[a, x] / var[a]
                if np.sign(slope) == sign:
                    edges.setdefault(d.ix[a], []).append((d.ix[x], max(abs(float(corr.at[a, x])), 0.2), float(slope)))
    return beta, sdv, edges


# ================================================================ trade evaluation
def evaluate(d, b, t, side, beta):
    """Hedged trade from the next open after day t, with stop variants and a momentum-matched benchmark."""
    td = d.tdays[b]
    p = np.searchsorted(td, t + 1)
    days = td[p:p + P["hold"]]
    if len(days) < P["hold"]:
        return None
    e, x = days[0], days[-1]
    has_open = not np.isnan(d.O[e, b])
    lent = d.logO[e, b] if has_open else d.logC[e, b]
    mo_e = d.logMo[e] if has_open else d.logMc[e]
    cc = side * ((d.logC[days, b] - lent) - beta * (d.logMc[days] - mo_e))
    oo = side * ((d.logO[days, b] - lent) - beta * (d.logMo[days] - mo_e))
    out = dict(entry=str(d.dates[e]), exit=str(d.dates[x]), gross_nostop=float(cc[-1]))
    for L in P["stops"]:
        hit = np.where(cc[:-1] <= -L)[0]
        if len(hit):
            j = hit[0] + 1
            out[f"gross_stop{int(L * 100)}"] = float(oo[j] if not np.isnan(oo[j]) else cc[j])
        else:
            out[f"gross_stop{int(L * 100)}"] = float(cc[-1])
    # momentum-matched benchmark (close-to-close from the signal day, same momentum quintile)
    allx = (d.logCf[x] - d.logCf[t]) - BETA_NOW * (d.logMc[x] - d.logMc[t])
    q = MOMQ[b]
    same = (MOMQ == q) & ~np.isnan(allx)
    same[b] = False
    own = side * ((d.logCf[x, b] - d.logCf[t, b]) - beta * (d.logMc[x] - d.logMc[t]))
    out["own_cc"] = float(own)
    out["mom_adj"] = float(own - side * np.nanmean(allx[same])) if same.sum() >= 5 else np.nan
    return out


BETA_NOW = None
MOMQ = None


def run(d, news, links, keep_paths=True):
    global BETA_NOW, MOMQ
    NW, vz, tdev, N = news["NW"], news["vz"], news["tdev"], news["N"]
    T = len(d.dates)
    events, trades, paths = [], [], {}
    beta = sd = edges = None
    for t in range(P["lookback"], T - P["hold"] - 2):
        if (t - P["lookback"]) % P["rebuild"] == 0:
            beta, sd, edges = build(d, t, links)
            BETA_NOW = np.nan_to_num(beta, nan=1.0)
        rmt = d.rm[t]
        if np.isnan(rmt):
            continue
        mrow = d.mom[t]
        MOMQ = np.full(len(d.tickers), -1)
        okm = ~np.isnan(mrow)
        if okm.sum() >= 20:
            MOMQ[okm] = pd.qcut(mrow[okm], 5, labels=False, duplicates="drop")
        g_c = set(np.where((vz[t] >= P["news_vz"]) & (N[t] >= P["news_min"]) & (np.abs(tdev[t]) >= P["tone_dev"]))[0])
        n_c = set(np.where(NW[t] > 0)[0])
        for a in g_c | n_c:
            if np.isnan(beta[a]) or np.isnan(d.r[t, a]) or not sd[a] > 0:
                continue
            abn = d.r[t, a] - beta[a] * rmt
            z = abn / sd[a]
            if a in g_c:
                dirn = int(np.sign(tdev[t, a]))
                if z * dirn < P["price_z"]:
                    continue
                source = "gdelt+newsweb" if a in n_c else "gdelt"
            else:
                if abs(z) < P["newsweb_z"]:
                    continue
                dirn, source = int(np.sign(z)), "newsweb"
            red = bool(rmt <= P["red_day"])
            peers = edges.get(a, [])
            specific = sum((NW[t, b] > 0) or (vz[t, b] >= P["news_vz"]) for b, _, _ in peers) < 2
            rip, reb = [], []
            for b, w, slope in peers:
                if np.isnan(beta[b]) or np.isnan(d.r[t, b]) or not sd[b] > 0:
                    continue
                exp, act = slope * abn, d.r[t, b] - beta[b] * rmt
                s = np.sign(exp)
                if abs(exp) >= P["min_expected"] and act * s < P["lag_frac"] * abs(exp):
                    rip.append((b, int(s), (abs(exp) - act * s) * w, abs(exp) - act * s))
                quiet = NW[t, b] == 0 and not (vz[t, b] >= 1)
                if quiet and act * s >= max(abs(exp), sd[b]):
                    reb.append((b, int(-s), act * s / sd[b], 0.5 * abs(act)))
            events.append(dict(date=str(d.dates[t]), ticker=d.tickers[a], source=source, dir=dirn,
                               z=float(z), abn=float(abn), red=red, mkt=float(rmt), specific=specific,
                               n_rip=len(rip), n_reb=len(reb)))
            groups = [("drift_A", [(a, dirn, 0, abs(abn))])]
            if len(rip) >= P["min_peers"]:
                groups.append(("ripple", sorted(rip, key=lambda x: -x[2])[:P["max_peers"]]))
            if specific and len(reb) >= P["min_peers"]:
                groups.append(("rebound", sorted(reb, key=lambda x: -x[2])[:P["max_peers"]]))
            for mode, picks in groups:
                for b, side, _, expected in picks:
                    ev = evaluate(d, b, t, side, beta[b])
                    if ev is None:
                        continue
                    assert ev["entry"] > str(d.dates[t]), "look-ahead: entry must be after the signal day"
                    adv, spr = d.adv[t, b], d.spread[t, b]
                    bk = bucket(adv)
                    cost = (spr if not np.isnan(spr) else P["bucket_cost"][bk] - P["fee"]) + P["fee"]
                    mom = d.mom[t, b]
                    trades.append(dict(mode=mode, signal=str(d.dates[t]), source_ticker=d.tickers[a],
                                       news=source, ticker=d.tickers[b], sector=d.sector[b], side=side,
                                       news_dir=dirn, red=red, expected=float(expected), adv_eur=float(adv),
                                       bucket=bk, spread=float(spr), cost=float(cost),
                                       cost_stress=P["bucket_cost"][bk], mom=float(mom),
                                       mom_agree=(None if np.isnan(mom) else bool(np.sign(mom) == side)), **ev))
                    if keep_paths:
                        td = d.tdays[b]
                        p = np.searchsorted(td, t)
                        days = td[p:p + 11]
                        if len(days) == 11:
                            path = side * ((d.logC[days, b] - d.logC[days[0], b]) - beta[b] * (d.logMc[days] - d.logMc[days[0]]))
                            paths.setdefault(mode, []).append(path)
    return pd.DataFrame(events), pd.DataFrame(trades), paths


# ================================================================ statistics
def finish(t):
    """Adds the net columns used everywhere: default stop per mode, cost from the spread estimate."""
    if t.empty:
        return t
    t = t.copy()
    stop = t["mode"].map(P["default_stop"])
    t["gross"] = np.where(stop == 0.05, t.gross_stop5, np.where(stop == 0.03, t.gross_stop3, t.gross_nostop))
    # Main cost model: round-trip cost by liquidity bucket (0.3% / 1% / 2%). The Corwin-Schultz
    # spread estimate is biased upward by volatility on daily data (it gave ~0.5% for both Equinor
    # and small caps), so it is kept only as an alternative ("net_cs").
    t["net"] = t.gross - t.cost_stress
    t["net_cs"] = t.gross - t.cost
    t["net_stress"] = t.gross - 2 * t.cost_stress
    t["skip"] = (t["mode"] != "drift_A") & (t.cost_stress > P["skip_ratio"] * t.expected)
    return t


def stats(t, col="net"):
    if t is None or len(t) == 0:
        return dict(trades=0)
    by_day = t.groupby("signal")[col].mean()
    se = by_day.std() / np.sqrt(len(by_day)) if len(by_day) > 2 else np.nan
    yearly = t.assign(y=t.signal.str[:4]).groupby("y")[col].agg(["count", "mean"])
    return dict(trades=int(len(t)), signal_days=int(len(by_day)), mean=round(float(t[col].mean()), 5),
                mean_gross=round(float(t.gross.mean()), 5) if "gross" in t else None,
                win=round(float((t[col] > 0).mean()), 3),
                t_stat=round(float(by_day.mean() / se), 2) if se and se > 0 else None,
                yearly={y: dict(n=int(v["count"]), mean=round(float(v["mean"]), 5)) for y, v in yearly.iterrows()})


def portfolio(t, d, modes=("ripple", "rebound")):
    """Ripple v2 as one book: skip rule, red-day boost, momentum tilt, sector cap, max open trades."""
    t = t[t["mode"].isin(modes) & ~t.skip].sort_values(["entry", "signal"]).copy()
    w = np.ones(len(t))
    w[((t["mode"] == "ripple") & (t.news_dir > 0) & t.red).values] *= P["red_boost"]
    w[(t.mom_agree == False).values] *= P["fight_size"]
    t["weight"] = w
    open_, keep = [], []
    for i, row in t.iterrows():
        open_ = [o for o in open_ if o[0] >= row.entry]
        if len(open_) >= P["max_open"] or sum(o[1] == row.sector for o in open_) >= P["sector_cap"]:
            keep.append(False); continue
        open_.append((row.exit, row.sector)); keep.append(True)
    t = t[keep]
    pnl = (t.net * t.weight * P["notional"]).groupby(t.exit).sum()
    pnl.index = pd.to_datetime(pnl.index)
    daily = pnl.reindex(pd.to_datetime(d.dates), fill_value=0.0)
    eq = P["capital"] + daily.cumsum()
    wk = daily.resample("W").sum() / P["capital"]
    dd = (eq / eq.cummax() - 1).min()
    first = t.entry.min() if len(t) else None
    years = (pd.to_datetime(d.dates[-1]) - pd.to_datetime(first)).days / 365.25 if first else np.nan
    return t, eq, dict(trades=int(len(t)), skipped_by_caps=int(len(keep) - sum(keep)),
                       total_pnl=round(float(daily.sum()), 0),
                       annual_return=round(float(daily.sum() / P["capital"] / years), 4) if years else None,
                       sharpe=round(float(wk.mean() / wk.std() * np.sqrt(52)), 2) if wk.std() > 0 else None,
                       max_drawdown=round(float(dd), 4))


# ================================================================ date alignment
def abn_around(d, pairs, offsets=range(-3, 4)):
    acc = {o: [] for o in offsets}
    C, r, rm = d.Cdf, d.rdf, d.rmdf
    for dd, tk in pairs:
        if tk not in C or dd is None or pd.isna(dd):
            continue
        td = C[tk].dropna().index
        if dd not in td:
            continue
        j = td.get_loc(dd)
        for o in offsets:
            if 0 <= j + o < len(td):
                x = td[j + o]
                if pd.notna(rm.at[x]) and pd.notna(r.at[x, tk]):
                    acc[o].append(abs(r.at[x, tk] - rm.at[x]))
    return {o: round(float(np.mean(v)) * 100, 3) if v else None for o, v in acc.items()}


def alignment(d, nw, news):
    out = {}
    if len(nw):
        m = nw[nw.material]
        for sess in ["pre-open", "intraday", "after-close"]:
            g = m[m.session == sess]
            out[f"newsweb_{sess}"] = dict(n=len(g), mapped=abn_around(d, zip(g.tday, g.ticker)),
                                          naive_calendar_date=abn_around(d, zip(g.naive_day, g.ticker)))
        rt = nw[~nw.material]
        out["newsweb_routine_messages"] = dict(n=len(rt), mapped=abn_around(d, zip(rt.tday, rt.ticker)))
    vz, N = news["vzdf"], news["Ndf"]
    sp = [(dd, tk) for tk in vz.columns for dd in vz.index[((vz[tk] >= P["news_vz"]) & (N[tk] >= P["news_min"])).values]]
    out["gdelt_spikes"] = dict(n=len(sp), mapped=abn_around(d, sp))
    return out


def headline_check(events, nw, n_gdelt=6):
    rows = []
    ev = events.sort_values("z", key=abs, ascending=False)
    for _, e in ev[ev.source.str.contains("newsweb")].groupby(ev.date.str[:4]).head(6).iterrows():
        for _, x in nw[(nw.ticker == e.ticker) & (nw.tday == e.date) & nw.material].head(2).iterrows():
            rows.append(dict(source="newsweb", signal_day=e.date, ticker=e.ticker, move=round(e.abn, 4),
                             published=f"{x.local_date} {x.local_time} Oslo ({x.session})", title=x.title[:140]))
    from fetch_data import QUERY
    import requests
    for _, e in ev[ev.source == "gdelt"].groupby(ev.date.str[:4]).head(2).head(n_gdelt).iterrows():
        D = pd.Timestamp(e.date)
        arts = []
        for i in range(10):
            try:
                resp = requests.get("https://api.gdeltproject.org/api/v2/doc/doc", timeout=60, params=dict(
                    query=QUERY.get(e.ticker, e.ticker), mode="ArtList", format="json", maxrecords=30,
                    sort="HybridRel", startdatetime=(D - pd.Timedelta(days=1)).strftime("%Y%m%d000000"),
                    enddatetime=(D + pd.Timedelta(days=1)).strftime("%Y%m%d060000")))
                if resp.text.strip().startswith("{"):
                    arts = resp.json().get("articles", []); break
            except Exception:
                pass
            time.sleep(12)
        en = [a for a in arts if a.get("language") == "English"] or arts
        for a in en[:2] or [dict(seendate=None, title="(no articles returned)")]:
            pub = pd.to_datetime(a["seendate"], format="%Y%m%dT%H%M%SZ").strftime("%Y-%m-%d %H:%M UTC") if a["seendate"] else ""
            rows.append(dict(source="gdelt", signal_day=e.date, ticker=e.ticker, move=round(e.abn, 4),
                             published=pub, title=a["title"][:140]))
        time.sleep(6)
    return pd.DataFrame(rows)


# ================================================================ main
def main():
    OUT.mkdir(exist_ok=True)
    u = json.loads((DATA / "universe.json").read_text())
    links = [tuple(x) for x in u["links"]]
    d, sanity = load_prices()
    nw, gd = load_newsweb(d.Cdf), load_gdelt(d.Cdf)
    news = build_news(d.Cdf, nw, gd)
    sanity.update(newsweb_messages=len(nw), newsweb_material=int(nw.material.sum()) if len(nw) else 0,
                  newsweb_tickers=int(nw.ticker.nunique()) if len(nw) else 0,
                  newsweb_after_close_share=round(float((nw.session == "after-close").mean()), 3) if len(nw) else None,
                  gdelt_tickers=int((gd[2].sum() > 0).sum()),
                  top_categories=nw.category.value_counts().head(12).to_dict() if len(nw) else {})
    print(json.dumps(sanity, indent=1, default=str), flush=True)

    t0 = time.time()
    events, trades, paths = run(d, news, links)
    print(f"main run {time.time() - t0:.0f}s: {len(events)} events, {len(trades)} trades", flush=True)
    trades = finish(trades)
    _, p_trades, _ = run(d, build_news(d.Cdf, nw, gd, shift=30), links, keep_paths=False)
    p_trades = finish(p_trades)

    modes = ["ripple", "rebound", "drift_A"]
    M = lambda df, m: df[df["mode"] == m] if len(df) else df
    S = dict(params=P, sanity=sanity, n_events=len(events))
    S["modes"] = {m: stats(M(trades, m)) for m in modes}
    S["placebo"] = {m: stats(M(p_trades, m)) for m in modes}
    S["costs"] = {m: dict(gross=stats(M(trades, m), "gross"), bucket_cost=stats(M(trades, m)),
                          spread_estimate_cost=stats(M(trades, m), "net_cs"),
                          double_cost=stats(M(trades, m), "net_stress"),
                          with_skip_rule=stats(M(trades, m)[~M(trades, m).skip]),
                          skipped_share=round(float(M(trades, m).skip.mean()), 3) if len(M(trades, m)) else None)
                  for m in modes}
    S["stops"] = {m: {name: stats(M(trades, m).assign(x=lambda df, c=col: df[c] - df.cost_stress), "x")
                      for name, col in [("none", "gross_nostop"), ("stop_3pct", "gross_stop3"), ("stop_5pct", "gross_stop5")]}
                  for m in modes}
    S["liquidity"] = {m: {bk: dict(spread_cost=stats(g), gross=stats(g, "gross"),
                                   median_spread=round(float(g.spread.median()), 4))
                          for bk, g in M(trades, m).groupby("bucket")} for m in ["ripple", "rebound"]}
    sm = trades[(trades.bucket == "small") & (trades.side > 0)]
    S["small_caps_long_only"] = {m: stats(M(sm, m)) for m in ["ripple", "rebound"]}
    S["momentum"] = {m: dict(agrees=stats(M(trades, m)[M(trades, m).mom_agree == True]),
                             fights=stats(M(trades, m)[M(trades, m).mom_agree == False]),
                             own_close_to_close=stats(M(trades, m).dropna(subset=["mom_adj"]), "own_cc"),
                             after_removing_momentum=stats(M(trades, m).dropna(subset=["mom_adj"]), "mom_adj"))
                     for m in modes}
    rp, rb = M(trades, "ripple"), M(trades, "rebound")
    S["red_day"] = dict(good_news_red_day=stats(rp[(rp.news_dir > 0) & rp.red]),
                        good_news_other_days=stats(rp[(rp.news_dir > 0) & ~rp.red]),
                        bad_news=stats(rp[rp.news_dir < 0]))
    S["rebound_split"] = dict(after_bad_news=stats(rb[rb.news_dir < 0]), after_good_news=stats(rb[rb.news_dir > 0]))
    S["by_news_source"] = {m: {s: stats(g) for s, g in M(trades, m).groupby("news")} for m in modes}
    book, eq, S["portfolio"] = portfolio(trades, d)
    _, eq_r, S["portfolio_ripple_only"] = portfolio(trades, d, ("ripple",))
    eq_r.to_csv(OUT / "portfolio_equity_ripple_only.csv")
    S["alignment"] = alignment(d, nw, news)

    events.to_csv(OUT / "events.csv", index=False)
    trades.to_csv(OUT / "trades.csv.gz", index=False)
    eq.to_csv(OUT / "portfolio_equity.csv")
    curves = {m: dict(n=len(v), mean=np.mean(v, axis=0).round(5).tolist()) for m, v in paths.items()}
    (OUT / "paths.json").write_text(json.dumps(curves))
    (OUT / "summary.json").write_text(json.dumps(S, indent=1, default=str))
    show = {k: S[k] for k in ["modes", "placebo", "portfolio", "portfolio_ripple_only", "small_caps_long_only", "red_day"]}
    print(json.dumps(show, indent=1, default=str), flush=True)
    charts(S, curves, trades, eq)
    if "--no-headlines" not in sys.argv and len(events):
        hc = headline_check(events, nw)
        hc.to_csv(OUT / "headline_check.csv", index=False)
        print(hc.to_string(), flush=True)


def charts(S, curves, trades, eq):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(2, 2, figsize=(14, 9))
    al = S["alignment"].get("newsweb_after-close") or S["alignment"]["gdelt_spikes"]
    offs = np.array([int(o) for o in al["mapped"]])
    ax[0, 0].bar(offs - 0.2, [v or 0 for v in al["mapped"].values()], 0.4, color="#2a78d6",
                 label="Mapped (after 16:20 -> next day)")
    if "naive_calendar_date" in al:
        ax[0, 0].bar(offs + 0.2, [v or 0 for v in al["naive_calendar_date"].values()], 0.4, color="#b4b2a9",
                     label="Naive calendar date")
    ax[0, 0].set(title=f"After-close announcements (n={al['n']}): |move| by day",
                 xlabel="Trading days from news day", ylabel="Avg |abnormal move| %")
    ax[0, 0].legend(fontsize=8)
    colors = {"ripple": "#1D9E75", "rebound": "#eb6834", "drift_A": "#6250d6"}
    for m, c in curves.items():
        ax[0, 1].plot(np.array(c["mean"]) * 100, label=f"{m} (n={c['n']})", color=colors.get(m), lw=2)
    ax[0, 1].axhline(0, color="grey", lw=0.6); ax[0, 1].axvline(1, color="grey", lw=0.6, ls=":")
    ax[0, 1].set(title="Average hedged path from signal-day close (before costs)", xlabel="Days after signal", ylabel="%")
    ax[0, 1].legend(fontsize=8)
    if len(trades):
        for m, g in trades.groupby("mode"):
            s = g.groupby("exit").net.sum().sort_index().cumsum() * P["notional"]
            ax[1, 0].plot(pd.to_datetime(s.index), s.values, label=m, color=colors.get(m))
    ax[1, 0].plot(eq.index, eq.values - P["capital"], color="black", lw=2, label="v2 portfolio")
    ax[1, 0].axhline(0, color="grey", lw=0.6)
    ax[1, 0].xaxis.set_major_locator(mdates.YearLocator()); ax[1, 0].xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax[1, 0].set(title="Cumulative P&L after costs (10 000 kr per trade)", ylabel="kr")
    ax[1, 0].legend(fontsize=8)
    labels, vals, errs = [], [], []
    for m in ["ripple", "rebound"]:
        for bk in ["large", "mid", "small"]:
            v = S["liquidity"].get(m, {}).get(bk)
            if v and v["spread_cost"]["trades"]:
                labels.append(f"{m}\n{bk}"); vals.append(v["spread_cost"]["mean"] * 100)
                errs.append(v["spread_cost"]["mean"] * 100 / v["spread_cost"]["t_stat"] if v["spread_cost"]["t_stat"] else 0)
    ax[1, 1].bar(labels, vals, yerr=np.abs(errs), color=["#1D9E75"] * 3 + ["#eb6834"] * 3, capsize=3)
    ax[1, 1].axhline(0, color="grey", lw=0.6)
    ax[1, 1].set(title="Average result per trade after spread costs, by liquidity", ylabel="%")
    fig.tight_layout(); fig.savefig(OUT / "charts.png", dpi=110)


if __name__ == "__main__":
    main()
