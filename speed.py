"""Idea 1: the speed edge. Trade the announcement-day move itself, minutes after an Oslo Børs announcement.

Rule tested: wait until the first price after the announcement (a delay), take the direction of the
move so far (vs the pre-news price, minus the market), and if that move is big enough, trade in
the same direction. Exit at that day's close, the next day's close, or after 5 days.

Two datasets
  5-minute bars, last ~60 days  : how much of the move is still left after 5/10/15/30/60 minutes
  hourly bars, last ~2 years    : the trading rule, with a holdout. Settings are chosen on
                                  signals up to 2025-12-31, then the chosen setting is run once on 2026.
Costs: Nordnet Student (0.15% per side, min 1 kr) + bid-ask spread by liquidity
(0.05% / 0.4% / 1.5% round trip); sensitivity with 50% extra spread because spreads widen after news.
Pre-open and after-close announcements count for the next session (reference = previous close).
"""
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

from backtest import DATA, FX, MATERIAL_CATS, OUT, P, ROUTINE, bucket

SPREAD = {"large": 0.0005, "mid": 0.004, "small": 0.015}
COMM = 0.003
DEV_END = "2025-12-31"
OSLO = "Europe/Oslo"


def load_events(px):
    nw = pd.read_csv(DATA / "newsweb.csv.gz")
    nw["ticker"] = nw.issuer.astype(str) + ".OL"
    nw = nw[nw.ticker.isin(px.ticker.unique())]
    nw = nw[nw.category.fillna("").str.contains(MATERIAL_CATS) & ~nw.title.fillna("").str.contains(ROUTINE)]
    nw["t0"] = pd.to_datetime(nw.published_utc, utc=True).dt.tz_convert(OSLO)
    hm = nw.t0.dt.strftime("%H:%M")
    nw["session"] = np.select([hm < "09:00", hm >= "16:20"], ["pre-open", "after-close"], "intraday")
    return nw.drop_duplicates(["ticker", "t0"])


def liquidity(px):
    px = px[px.ticker.str.endswith(".OL")].copy()
    px["turn"] = px.close * px.volume * FX[".OL"]
    adv = {}
    for tk, g in px.groupby("ticker"):
        s = g.set_index("date").turn.rolling(60, min_periods=20).median().shift(1)
        adv[tk] = s
    return adv


def download(tickers, period, interval):
    import yfinance as yf
    frames = []
    for i in range(0, len(tickers), 40):
        df = yf.download(tickers[i:i + 40], period=period, interval=interval, auto_adjust=True,
                         progress=False, threads=True)["Close"]
        frames.append(df)
    c = pd.concat(frames, axis=1)
    c.index = c.index.tz_convert(OSLO)
    c = c[(c.index.strftime("%H:%M") >= "09:00") & (c.index.strftime("%H:%M") < "16:30")]
    return c


def bar_end(idx, minutes):
    end = idx + pd.Timedelta(minutes=minutes)
    close = pd.to_datetime(idx.strftime("%Y-%m-%d") + " 16:20").tz_localize(OSLO)
    return end.where(end <= close, close)


def build_trades(nw, bars, minutes, delays, daily_close, daily_mkt, adv):
    """For every announcement and entry delay: direction-signed returns to several exits."""
    lr = np.log(bars).diff()
    mkt = lr.mean(axis=1)
    mcum = mkt.fillna(0).cumsum()
    ends = bar_end(bars.index, minutes)
    dstr = np.asarray(bars.index.strftime("%Y-%m-%d"))
    days = pd.Index(sorted(set(dstr)))
    rows = []
    for _, m in nw.iterrows():
        tk = m.ticker
        if tk not in bars:
            continue
        s = bars[tk]
        if m.session == "intraday":
            day = m.t0.strftime("%Y-%m-%d")
            ref_mask = ends <= m.t0
            start = m.t0
        else:
            d0 = (m.t0 + pd.Timedelta(hours=8)).strftime("%Y-%m-%d") if m.session == "after-close" else m.t0.strftime("%Y-%m-%d")
            pos = days.searchsorted(d0)
            if pos >= len(days):
                continue
            day = days[pos]
            ref_mask = bars.index < pd.Timestamp(day + " 00:00", tz=OSLO)
            start = pd.Timestamp(day + " 09:00", tz=OSLO)
        if day not in days:
            continue
        ref = s[ref_mask].dropna()
        if ref.empty:
            continue
        ref_t, ref_px = ref.index[-1], ref.iloc[-1]
        today = dstr == day
        day_s = s[today].ffill()
        if day_s.dropna().empty:
            continue
        close_t, close_px = day_s.index[-1], day_s.iloc[-1]
        # every exit comes from the same intraday price series (daily prices are adjusted differently)
        pos_d = days.get_loc(day)
        exits = {}
        for name, k in [("r_next", 1), ("r_5d", 5)]:
            if pos_d + k < len(days):
                dk = days[pos_d + k]
                sk = s[dstr == dk].dropna()
                if not sk.empty:
                    exits[name] = (sk.index[-1], sk.iloc[-1])
        bk = bucket(adv.get(tk, pd.Series(dtype=float)).get(day, np.nan))
        for dl in delays:
            target = start + pd.Timedelta(minutes=dl)
            ok = today & (ends >= target)
            if not ok.any():
                continue
            e_t = bars.index[ok][0]
            e_px = day_s.get(e_t, np.nan)
            if np.isnan(e_px):
                continue
            so_far = np.log(e_px / ref_px) - (mcum[e_t] - mcum[ref_t])
            side = int(np.sign(so_far)) or 1
            row = dict(ticker=tk, t0=m.t0.strftime("%Y-%m-%d %H:%M"), day=day, session=m.session,
                       delay=dl, entry=e_t.strftime("%H:%M"), so_far=float(so_far), side=side, bucket=bk,
                       title=str(m.title)[:100])
            row["r_close"] = float(side * (np.log(close_px / e_px) - (mcum[close_t] - mcum[e_t])))
            for name, (x_t, x_px) in exits.items():
                row[name] = float(side * (np.log(x_px / e_px) - (mcum[x_t] - mcum[e_t])))
            row["total_day"] = float(side * (np.log(close_px / ref_px) - (mcum[close_t] - mcum[ref_t])))
            rows.append(row)
    return pd.DataFrame(rows)


def costed(t, col, extra_spread=0.0):
    c = COMM + t.bucket.map(SPREAD) * (1 + extra_spread)
    return t[col] - c


def tstat(x, g):
    m = x.groupby(g).mean()
    return round(float(m.mean() / m.std() * np.sqrt(len(m))), 2) if len(m) > 2 and m.std() > 0 else None


def main():
    px = pd.read_csv(DATA / "prices.csv.gz")
    oslo = sorted(t for t in px.ticker.unique() if t.endswith(".OL"))
    daily_close = px[px.ticker.isin(oslo)].pivot(index="date", columns="ticker", values="close").sort_index()
    daily_mkt = np.log(daily_close / daily_close.ffill().shift(1)).mean(axis=1).fillna(0)
    adv = liquidity(px)
    nw = load_events(px)
    out = {}

    # ---------- 5-minute bars: how fast is news priced? (descriptive) ----------
    b5 = download(oslo, "60d", "5m")
    first5 = b5.index.min()
    e5 = build_trades(nw[nw.t0 >= first5], b5, 5, [5, 10, 15, 30, 60], daily_close, daily_mkt, adv)
    e5.to_csv(OUT / "speed_5m.csv", index=False)
    big = e5[e5.so_far.abs() >= 0.01]
    desc = {}
    for (sess, bk), g in big.groupby([big.session.replace({"after-close": "pre-open"}), "bucket"]):
        desc[f"{sess}/{bk}"] = {f"{dl}min": dict(n=int(len(x)), left_to_close=round(float(x.r_close.mean()), 4),
                                                   left_to_next_close=round(float(x.r_next.mean()), 4) if "r_next" in x and x.r_next.notna().any() else None,
                                                   after_student_costs=round(float(costed(x, "r_close").mean()), 4))
                                for dl, x in g.groupby("delay")}
    out["five_minute"] = dict(window=f"{first5.date()} to {b5.index.max().date()}", events=int(e5[e5.delay == 5].shape[0]),
                              moves_over_1pct=desc)
    print(json.dumps(out["five_minute"], indent=1), flush=True)

    # ---------- hourly bars: the trading rule with a 2026 holdout ----------
    b60 = download(oslo, "730d", "60m")
    e60 = build_trades(nw[nw.t0 >= b60.index.min()], b60, 60, [0], daily_close, daily_mkt, adv)
    e60["sess"] = e60.session.replace({"after-close": "pre-open"})
    e60.to_csv(OUT / "speed_60m.csv.gz", index=False)
    grid = [dict(sess=s, thr=th, exit=ex, longonly=lo) for s in ["pre-open", "intraday"] for th in [0.005, 0.01, 0.02]
            for ex in ["r_close", "r_next", "r_5d"] for lo in [False, True]]

    def pick(df, g):
        x = df[(df.sess == g["sess"]) & (df.so_far.abs() >= g["thr"])].dropna(subset=[g["exit"]])
        if g["longonly"]:
            x = x[x.side > 0]
        x = x[~((x.bucket == "small") & (x.side < 0))]          # small caps can't be shorted
        return x

    dev, hold = e60[e60.day <= DEV_END], e60[e60.day > DEV_END]
    tried = []
    for g in grid:
        x = pick(dev, g)
        net = costed(x, g["exit"])
        tried.append(dict(setting=g, trades=int(len(x)), gross=round(float(x[g["exit"]].mean()), 4) if len(x) else None,
                          net=round(float(net.mean()), 4) if len(x) else None, t=tstat(net, x.day.str[:7]) if len(x) else None))
    ok = [r for r in tried if r["trades"] >= 30 and r["t"] is not None]
    best = max(ok, key=lambda r: r["t"]) if ok else None
    res = dict(window=f"{b60.index.min().date()} to {b60.index.max().date()}", tried_on_dev=tried,
               chosen=best["setting"] if best else None, dev=best)
    if best:
        g = best["setting"]
        x = pick(hold, g)                                          # evaluated once
        for label, extra in [("holdout", 0.0), ("holdout_wider_spread", 0.5)]:
            net = costed(x, g["exit"], extra)
            res[label] = dict(trades=int(len(x)), gross=round(float(x[g["exit"]].mean()), 4) if len(x) else None,
                              net=round(float(net.mean()), 4) if len(x) else None, win=round(float((net > 0).mean()), 3) if len(x) else None,
                              t=tstat(net, x.day.str[:7]) if len(x) else None,
                              by_bucket={b: round(float(costed(y, g["exit"]).mean()), 4) for b, y in x.groupby("bucket")})
    out["hourly_rule"] = res
    print(json.dumps({k: v for k, v in res.items() if k != "tried_on_dev"}, indent=1), flush=True)
    (OUT / "speed.json").write_text(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
