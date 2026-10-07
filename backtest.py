"""Ripple v2 backtest.

News sources
  newsweb - Oslo Børs official announcements (exact publish time). Material categories only.
            Direction = sign of the confirmed price reaction (titles carry no reliable tone).
  gdelt   - worldwide news volume + tone per day (non-Oslo names). Event = volume spike,
            direction = tone vs its own 60-day normal, which the price must confirm.

Modes (all hedged against an equal-weight EU/EEA market index)
  ripple   - trade A's linked peers that have NOT reacted yet, in the expected direction
  red_day  - the ripple trades from good-news events on days the market fell >= 1%
  rebound  - A's news is company-specific; fade peers that moved in sympathy with no news of their own
  drift_A  - control: trade A itself in the news direction

No look-ahead
  - network and betas rebuilt every 21 trading days from the previous 252 days only
  - news baselines use the previous 60 trading days only
  - a NewsWeb message published after 16:20 Oslo time counts for the NEXT trading day
  - every trade enters at the next trading day's open, exits at the close 5 trading days after the signal
Costs: 0.30% per round trip (stock + hedge).
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
         min_peers=2, max_peers=5, hold=5, cost=0.003, red_day=-0.01, bad_ret=0.4,
         close_local="16:20")
ROUTINE = re.compile(r"notifiable trad|mandatory notification|primary insider|ex[- ]?div|ex[- ]?date|"
                     r"buy[- ]?back|share repurchase|key information|total number of|voting rights|"
                     r"annual general meeting|general meeting|financial calendar|invitation to|"
                     r"presentation of|will (present|publish|report)|webcast|share capital|"
                     r"major shareholding|disclosure of large", re.I)
MATERIAL_CATS = re.compile(r"INSIDE INFORMATION|FINANCIAL REPORT|NON-REGULATORY PRESS|ADDITIONAL REGULATED", re.I)


# ---------------------------------------------------------------- prices
def load_prices():
    px = pd.read_csv(DATA / "prices.csv.gz")
    C = px.pivot(index="date", columns="ticker", values="close").sort_index()
    O = px.pivot(index="date", columns="ticker", values="open").reindex_like(C)
    O = O.where(O > 0)
    keep = C.notna().sum() >= 300
    C, O = C.loc[:, keep], O.loc[:, keep]
    prev = C.ffill().shift(1)
    r = np.log(C / prev).where(C.notna())
    bad = r.abs() > P["bad_ret"]
    ii, jj = np.where(bad.values)
    flags = [(r.index[i], r.columns[j], round(float(r.iat[i, j]), 3)) for i, j in zip(ii, jj)]
    r = r.mask(bad)
    on = np.log(O / prev).where(O.notna() & ~bad)
    rm = r.mean(axis=1).where(r.notna().mean(axis=1) > 0.3)
    mon = on.mean(axis=1).fillna(0)
    weekday = pd.to_datetime(C.index).dayofweek
    sanity = dict(tickers=int(C.shape[1]), dropped_short_history=list(keep[~keep].index),
                  days=int(C.shape[0]), first=C.index[0], last=C.index[-1],
                  weekend_dates=int((weekday >= 5).sum()),
                  missing_open_share=round(float(O[C.notna()].isna().mean().mean()), 4),
                  extreme_moves_removed=flags[:40], n_extreme=len(flags))
    return C, O, r, rm, mon, sanity


# ---------------------------------------------------------------- news
def trading_day(td, local_dates, after_close):
    """First trading day >= the local date (or > it, if published after the close)."""
    tgt = np.where(after_close, (pd.to_datetime(local_dates) + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
                   local_dates)
    pos = np.searchsorted(td, tgt)
    return pos


def load_newsweb(C):
    p = DATA / "newsweb.csv.gz"
    if not p.exists():
        return pd.DataFrame()
    nw = pd.read_csv(p)
    nw["ticker"] = nw.issuer.astype(str) + ".OL"
    nw = nw[nw.ticker.isin(C.columns)].copy()
    t = pd.to_datetime(nw.published_utc, utc=True).dt.tz_convert("Europe/Oslo")
    nw["local_date"] = t.dt.strftime("%Y-%m-%d")
    nw["local_time"] = t.dt.strftime("%H:%M")
    nw["utc_date"] = pd.to_datetime(nw.published_utc, utc=True).dt.strftime("%Y-%m-%d")
    nw["session"] = np.select([nw.local_time < "09:00", nw.local_time >= P["close_local"]],
                              ["pre-open", "after-close"], "intraday")
    nw["material"] = nw.category.fillna("").str.contains(MATERIAL_CATS) & ~nw.title.fillna("").str.contains(ROUTINE)
    out = []
    for tk, g in nw.groupby("ticker"):
        td = C[tk].dropna().index.values
        pos = trading_day(td, g.local_date.values, (g.session == "after-close").values)
        naive = np.searchsorted(td, g.utc_date.values)
        ok = pos < len(td)
        g = g[ok].assign(tday=td[pos[ok]],
                         naive_day=np.where(naive[ok] < len(td), td[np.minimum(naive[ok], len(td) - 1)], None))
        out.append(g)
    return pd.concat(out) if out else pd.DataFrame()


def load_gdelt(C):
    files = sorted(DATA.glob("gdelt_*.csv.gz"))
    if not files:
        return pd.DataFrame(np.nan, index=C.index, columns=C.columns), pd.DataFrame(np.nan, index=C.index, columns=C.columns), pd.DataFrame(0.0, index=C.index, columns=C.columns)
    nd = pd.concat(pd.read_csv(f) for f in files)
    nd = nd[nd.ticker.isin(C.columns) & (nd.articles.fillna(0) > 0)]
    N = pd.DataFrame(0.0, index=C.index, columns=C.columns)
    T = pd.DataFrame(np.nan, index=C.index, columns=C.columns)
    for tk, g in nd.groupby("ticker"):
        td = C[tk].dropna().index.values
        pos = np.searchsorted(td, g.date_utc.values)     # GDELT day (UTC) -> first trading day >= it
        ok = pos < len(td)
        g = g[ok].assign(tday=td[pos[ok]], tw=lambda x: x.tone * x.articles)
        a = g.groupby("tday").agg(articles=("articles", "sum"), tw=("tw", "sum"))
        N.loc[a.index, tk] = a.articles
        T.loc[a.index, tk] = a.tw / a.articles
    has = nd.ticker.unique()
    N = N.where(C.notna())
    vz = pd.DataFrame(np.nan, index=C.index, columns=C.columns)
    tdev = vz.copy()
    for tk in has:
        n = np.log1p(N[tk].dropna())
        vz.loc[n.index, tk] = (n - n.rolling(60, min_periods=40).mean().shift(1)) / \
            n.rolling(60, min_periods=40).std().shift(1).replace(0, np.nan)
        t = T[tk].dropna()
        tdev.loc[t.index, tk] = t - t.rolling(60, min_periods=20).median().shift(1)
    return vz, tdev, N


def build_news(C, nw, gd, shift=0):
    """Per day and ticker: material NewsWeb messages, GDELT spike/tone. shift>0 = placebo."""
    vz, tdev, N = gd
    NW = pd.DataFrame(0.0, index=C.index, columns=C.columns)
    if len(nw):
        m = nw[nw.material]
        cnt = m.groupby(["tday", "ticker"]).size()
        for (d, tk), v in cnt.items():
            NW.at[d, tk] = v
    if shift:
        sh = lambda df: pd.DataFrame({tk: df[tk].dropna().shift(shift).reindex(C.index) for tk in C.columns})
        NW, vz, tdev, N = sh(NW.where(C.notna())).fillna(0), sh(vz), sh(tdev), sh(N.where(C.notna())).fillna(0)
    return dict(NW=NW, vz=vz, tdev=tdev, N=N)


# ---------------------------------------------------------------- network
def build(r, rm, k, links):
    w = r.iloc[k - P["lookback"]:k]
    m = rm.iloc[k - P["lookback"]:k]
    w = w.loc[:, w.notna().mean() > 0.7]
    ok = m.notna()
    beta = w[ok].apply(lambda s: s.cov(m[ok]) / m[ok].var())
    res = w - np.outer(m.fillna(0), beta)
    corr, cov, var = res.corr(min_periods=120), res.cov(min_periods=120), res.var()
    sd = res.iloc[-60:].std()
    edges = {}
    for a in corr:
        c = corr[a].drop(a).dropna()
        c = c[c >= P["min_link"]].sort_values(ascending=False).head(P["max_links"])
        edges[a] = [(b, float(c[b]), float(cov.at[a, b] / var[a])) for b in c.index]
    for a, b, sign in links:
        if a in corr and b in corr and b not in [x[0] for x in edges.get(a, [])]:
            if pd.notna(corr.at[a, b]):
                slope = cov.at[a, b] / var[a]
                if np.sign(slope) == sign:
                    edges.setdefault(a, []).append((b, max(abs(float(corr.at[a, b])), 0.2), float(slope)))
    return beta, sd, edges


# ---------------------------------------------------------------- trades
def trade_return(C, O, rm, mon, b, k, side, beta):
    td = C[b].iloc[k + 1:].dropna().index[:P["hold"]]
    if len(td) < P["hold"]:
        return None
    e, x = td[0], td[-1]
    has_open = pd.notna(O.at[e, b])
    entry = O.at[e, b] if has_open else C.at[e, b]
    stock = np.log(C.at[x, b] / entry)
    days = rm.loc[e:x].fillna(0)
    mkt = (days.iloc[0] - mon.loc[e] if has_open else 0) + days.iloc[1:].sum()
    gross = side * (stock - beta * mkt)
    return dict(entry=e, exit=x, gross=float(gross), net=float(gross - P["cost"]))


def path(C, rm, b, k, side, beta, n=10):
    td = C[b].iloc[k:].dropna().index[:n + 1]
    if len(td) < n + 1:
        return None
    rb = np.log(C.loc[td, b]).diff().iloc[1:].values
    mk = rm.reindex(td).fillna(0).iloc[1:].values
    return np.concatenate([[0], np.cumsum(side * (rb - beta * mk))])


def run(C, O, r, rm, mon, links, news, keep_paths=True):
    NW, vz, tdev, N = news["NW"], news["vz"], news["tdev"], news["N"]
    dates = C.index
    events, trades, paths = [], [], {}
    beta = sd = edges = None
    for k in range(P["lookback"], len(dates) - P["hold"] - 1):
        if (k - P["lookback"]) % P["rebuild"] == 0:
            beta, sd, edges = build(r, rm, k, links)
        D = dates[k]
        if pd.isna(rm.at[D]):
            continue
        g_cand = set(vz.columns[((vz.loc[D] >= P["news_vz"]) & (N.loc[D] >= P["news_min"])
                                 & (tdev.loc[D].abs() >= P["tone_dev"])).values])
        n_cand = set(NW.columns[(NW.loc[D] > 0).values])
        spike = lambda b: (NW.at[D, b] > 0) or (vz.at[D, b] >= P["news_vz"])
        for a in g_cand | n_cand:
            if a not in beta or pd.isna(r.at[D, a]) or not sd.get(a):
                continue
            abn = r.at[D, a] - beta[a] * rm.at[D]
            z = abn / sd[a]
            if a in g_cand:
                dirn = int(np.sign(tdev.at[D, a]))
                if z * dirn < P["price_z"]:
                    continue
                source = "gdelt+newsweb" if a in n_cand else "gdelt"
            else:
                if abs(z) < P["newsweb_z"]:
                    continue
                dirn, source = int(np.sign(z)), "newsweb"
            red = bool(rm.at[D] <= P["red_day"])
            peers = edges.get(a, [])
            specific = sum(spike(b) for b, _, _ in peers if b in NW) < 2
            rip, reb = [], []
            for b, w, slope in peers:
                if b not in beta or pd.isna(r.at[D, b]) or not sd.get(b):
                    continue
                exp, act = slope * abn, r.at[D, b] - beta[b] * rm.at[D]
                s = np.sign(exp)
                if abs(exp) >= P["min_expected"] and act * s < P["lag_frac"] * abs(exp):
                    rip.append((b, int(s), (abs(exp) - act * s) * w))
                quiet = NW.at[D, b] == 0 and not (vz.at[D, b] >= 1)
                if quiet and act * s >= max(abs(exp), sd[b]):
                    reb.append((b, int(-s), act * s / sd[b]))
            events.append(dict(date=D, ticker=a, source=source, dir=dirn, z=float(z), abn=float(abn),
                               red=red, mkt=float(rm.at[D]), specific=specific,
                               n_rip=len(rip), n_reb=len(reb)))
            groups = [("drift_A", [(a, dirn, 0)])]
            if len(rip) >= P["min_peers"]:
                groups.append(("ripple", sorted(rip, key=lambda x: -x[2])[:P["max_peers"]]))
            if specific and len(reb) >= P["min_peers"]:
                groups.append(("rebound", sorted(reb, key=lambda x: -x[2])[:P["max_peers"]]))
            for mode, picks in groups:
                for b, side, _ in picks:
                    t = trade_return(C, O, rm, mon, b, k, side, beta[b])
                    if t is None:
                        continue
                    assert t["entry"] > D, "look-ahead: entry must be after the signal day"
                    trades.append(dict(mode=mode, signal=D, source_ticker=a, news=source, ticker=b,
                                       side=side, news_dir=dirn, red=red, **t))
                    if keep_paths:
                        p = path(C, rm, b, k, side, beta[b])
                        if p is not None:
                            paths.setdefault(mode, []).append(p)
    return pd.DataFrame(events), pd.DataFrame(trades), paths


# ---------------------------------------------------------------- statistics
def stats(t):
    if t is None or t.empty:
        return dict(trades=0)
    by_day = t.groupby("signal").net.mean()
    se = by_day.std() / np.sqrt(len(by_day)) if len(by_day) > 2 else np.nan
    yearly = t.assign(y=t.signal.str[:4]).groupby("y").net.agg(["count", "mean"])
    return dict(trades=len(t), signal_days=len(by_day), mean_gross=round(float(t.gross.mean()), 5),
                mean_net=round(float(t.net.mean()), 5), win=round(float((t.net > 0).mean()), 3),
                t_stat=round(float(by_day.mean() / se), 2) if se and se > 0 else None,
                yearly={y: dict(n=int(v["count"]), mean_net=round(float(v["mean"]), 5))
                        for y, v in yearly.iterrows()})


def abn_around(C, r, rm, pairs, offsets=range(-3, 4)):
    """Average |abnormal move| of a stock around given (day, ticker) pairs."""
    acc = {o: [] for o in offsets}
    for d, tk in pairs:
        if tk not in C or d is None or pd.isna(d):
            continue
        td = C[tk].dropna().index
        if d not in td:
            continue
        j = td.get_loc(d)
        for o in offsets:
            if 0 <= j + o < len(td):
                dd = td[j + o]
                if pd.notna(rm.at[dd]) and pd.notna(r.at[dd, tk]):
                    acc[o].append(abs(r.at[dd, tk] - rm.at[dd]))
    return {o: round(float(np.mean(v)) * 100, 3) if v else None for o, v in acc.items()}


def alignment(C, r, rm, nw, news):
    """Do the news dates line up with the price moves?"""
    out = {}
    if len(nw):
        m = nw[nw.material]
        for sess in ["pre-open", "intraday", "after-close"]:
            g = m[m.session == sess]
            out[f"newsweb_{sess}"] = dict(
                n=len(g),
                mapped=abn_around(C, r, rm, zip(g.tday, g.ticker)),
                naive_calendar_date=abn_around(C, r, rm, zip(g.naive_day, g.ticker)))
        rt = nw[~nw.material]
        out["newsweb_routine_messages"] = dict(n=len(rt), mapped=abn_around(C, r, rm, zip(rt.tday, rt.ticker)))
    vz, N, tdev = news["vz"], news["N"], news["tdev"]
    sp = [(d, tk) for tk in vz.columns for d in vz.index[((vz[tk] >= P["news_vz"]) & (N[tk] >= P["news_min"])).values]]
    out["gdelt_spikes"] = dict(n=len(sp), mapped=abn_around(C, r, rm, sp))
    return out


def headline_check(events, nw, n_gdelt=12):
    rows = []
    ev = events.sort_values("z", key=abs, ascending=False)
    for _, e in ev[ev.source.str.contains("newsweb")].groupby(ev.date.str[:4]).head(6).iterrows():
        m = nw[(nw.ticker == e.ticker) & (nw.tday == e.date) & nw.material]
        for _, x in m.head(2).iterrows():
            rows.append(dict(source="newsweb", signal_day=e.date, ticker=e.ticker, move=round(e.abn, 4),
                             published=f"{x.local_date} {x.local_time} Oslo ({x.session})",
                             trade_entry=f"next open after {e.date}", title=x.title[:140]))
    from fetch_data import QUERY
    import requests
    gd = ev[ev.source == "gdelt"].groupby(ev.date.str[:4]).head(3).head(n_gdelt)
    for _, e in gd.iterrows():
        D = pd.Timestamp(e.date)
        arts = []
        for i in range(25):
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
        for a in en[:2]:
            rows.append(dict(source="gdelt", signal_day=e.date, ticker=e.ticker, move=round(e.abn, 4),
                             published=pd.to_datetime(a["seendate"], format="%Y%m%dT%H%M%SZ").strftime("%Y-%m-%d %H:%M UTC"),
                             trade_entry=f"next open after {e.date}", title=a["title"][:140]))
        if not en:
            rows.append(dict(source="gdelt", signal_day=e.date, ticker=e.ticker, move=round(e.abn, 4),
                             published="(no articles returned)", trade_entry="", title=""))
        time.sleep(6)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- main
def main():
    OUT.mkdir(exist_ok=True)
    u = json.loads((DATA / "universe.json").read_text())
    links = [tuple(x) for x in u["links"]]
    C, O, r, rm, mon, sanity = load_prices()
    nw = load_newsweb(C)
    gd = load_gdelt(C)
    news = build_news(C, nw, gd)
    sanity.update(newsweb_messages=len(nw), newsweb_material=int(nw.material.sum()) if len(nw) else 0,
                  newsweb_tickers=int(nw.ticker.nunique()) if len(nw) else 0,
                  newsweb_after_close_share=round(float((nw.session == "after-close").mean()), 3) if len(nw) else None,
                  gdelt_tickers=int((gd[2].sum() > 0).sum()),
                  top_categories=nw.category.value_counts().head(12).to_dict() if len(nw) else {})
    print(json.dumps(sanity, indent=1, default=str), flush=True)

    events, trades, paths = run(C, O, r, rm, mon, links, news)
    p_events, p_trades, _ = run(C, O, r, rm, mon, links, build_news(C, nw, gd, shift=30), keep_paths=False)

    def split(t, **kw):
        return {k: stats(v) for k, v in kw.items()}

    summary = dict(params=P, sanity=sanity, n_events=len(events), n_placebo_events=len(p_events),
                   modes={m: stats(trades[trades["mode"] == m]) for m in ["ripple", "rebound", "drift_A"]},
                   placebo={m: stats(p_trades[p_trades["mode"] == m]) if len(p_trades) else {}
                            for m in ["ripple", "rebound", "drift_A"]})
    rp = trades[trades["mode"] == "ripple"]
    rb = trades[trades["mode"] == "rebound"]
    summary["ripple_by_source"] = {s: stats(g) for s, g in rp.groupby("news")}
    summary["red_day"] = dict(good_news_red_day=stats(rp[(rp.news_dir > 0) & rp.red]),
                              good_news_other_days=stats(rp[(rp.news_dir > 0) & ~rp.red]),
                              bad_news=stats(rp[rp.news_dir < 0]))
    summary["rebound_split"] = dict(after_bad_news=stats(rb[rb.news_dir < 0]),
                                    after_good_news=stats(rb[rb.news_dir > 0]))
    summary["alignment"] = alignment(C, r, rm, nw, news)
    events.to_csv(OUT / "events.csv", index=False)
    trades.to_csv(OUT / "trades.csv", index=False)
    curves = {m: dict(n=len(v), mean=np.mean(v, axis=0).round(5).tolist()) for m, v in paths.items()}
    (OUT / "paths.json").write_text(json.dumps(curves))
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1, default=str))
    print(json.dumps({k: summary[k] for k in summary if k not in ("params", "sanity")}, indent=1, default=str), flush=True)
    charts(summary, curves, trades)
    if "--no-headlines" not in sys.argv and len(events):
        hc = headline_check(events, nw)
        hc.to_csv(OUT / "headline_check.csv", index=False)
        print(hc.to_string(), flush=True)


def charts(summary, curves, trades):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 3, figsize=(16, 4.2))
    al = summary["alignment"].get("newsweb_after-close") or summary["alignment"].get("gdelt_spikes")
    offs = [int(o) for o in al["mapped"]]
    ax[0].bar(np.array(offs) - 0.2, [al["mapped"][o] or 0 for o in al["mapped"]], 0.4,
              label="Mapped (after 16:20 -> next day)", color="#2a78d6")
    if "naive_calendar_date" in al:
        ax[0].bar(np.array(offs) + 0.2, [al["naive_calendar_date"][o] or 0 for o in al["naive_calendar_date"]],
                  0.4, label="Naive calendar date", color="#b4b2a9")
    ax[0].set(title="After-close announcements: |move| by day", xlabel="Trading days from news day",
              ylabel="Avg |abnormal move| %")
    ax[0].legend(fontsize=8)
    colors = {"ripple": "#1D9E75", "rebound": "#eb6834", "drift_A": "#6250d6"}
    for m, c in curves.items():
        ax[1].plot(np.array(c["mean"]) * 100, label=f"{m} (n={c['n']})", color=colors.get(m), lw=2)
    ax[1].axhline(0, color="grey", lw=0.6); ax[1].axvline(1, color="grey", lw=0.6, ls=":")
    ax[1].set(title="Average hedged path from signal-day close (gross)", xlabel="Days after signal", ylabel="%")
    ax[1].legend(fontsize=8)
    if len(trades):
        for m, g in trades.groupby("mode"):
            s = g.groupby("exit").net.sum().sort_index().cumsum() * 10_000
            ax[2].plot(pd.to_datetime(s.index), s.values, label=m, color=colors.get(m))
    ax[2].axhline(0, color="grey", lw=0.6)
    ax[2].xaxis.set_major_locator(mdates.YearLocator()); ax[2].xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax[2].set(title="Cumulative P&L, 10 000 kr per trade, after costs", ylabel="kr")
    ax[2].legend(fontsize=8)
    fig.tight_layout(); fig.savefig(OUT / "charts.png", dpi=120)


if __name__ == "__main__":
    main()
