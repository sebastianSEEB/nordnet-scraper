"""How fast do Oslo stocks absorb an announcement? (The 'a bot notices faster' question.)

Uses Yahoo 5-minute bars (available for roughly the last 60 days) and NewsWeb's exact
publish times. For every material announcement published during trading hours that moved
the stock by at least 1.5% (vs the market) by the close, it measures how many minutes it
took to reach 50% and 80% of that day's move, split by company liquidity.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from backtest import DATA, FX, MATERIAL_CATS, OUT, P, ROUTINE, bucket

MIN_MOVE = 0.015
CHECK = [5, 10, 15, 30, 60, 120]


def main():
    import yfinance as yf
    nw = pd.read_csv(DATA / "newsweb.csv.gz")
    nw["ticker"] = nw.issuer.astype(str) + ".OL"
    t = pd.to_datetime(nw.published_utc, utc=True).dt.tz_convert("Europe/Oslo")
    nw["t0"] = t
    nw = nw[(t >= pd.Timestamp.now(tz="Europe/Oslo") - pd.Timedelta(days=57))
            & (t.dt.strftime("%H:%M") >= "09:10") & (t.dt.strftime("%H:%M") <= "15:30")
            & nw.category.fillna("").str.contains(MATERIAL_CATS) & ~nw.title.fillna("").str.contains(ROUTINE)]
    px = pd.read_csv(DATA / "prices.csv.gz")
    oslo = sorted(t for t in px.ticker.unique() if t.endswith(".OL"))
    nw = nw[nw.ticker.isin(oslo)]
    print(f"intraday: {len(nw)} announcements during trading hours in the last ~57 days", flush=True)
    if nw.empty:
        return
    bars = yf.download(oslo, period="60d", interval="5m", auto_adjust=True, progress=False, threads=True)["Close"]
    bars.index = bars.index.tz_convert("Europe/Oslo")
    lr = np.log(bars).diff()
    mkt = lr.mean(axis=1)
    last = px[px.date >= px.date.max()[:4] + "-01-01"]
    turn = (last.close * last.volume).groupby(last.ticker).median() * FX[".OL"]

    rows, paths = [], {"large": [], "mid": [], "small": []}
    for _, m in nw.iterrows():
        tk = m.ticker
        if tk not in bars:
            continue
        day = m.t0.normalize()
        s = lr[tk][(lr.index >= day) & (lr.index < day + pd.Timedelta(days=1))].dropna()
        if len(s) < 20:
            continue
        ab = (s - mkt.reindex(s.index).fillna(0)).cumsum()
        before = ab[ab.index <= m.t0 - pd.Timedelta(minutes=5)]      # last bar fully before the news
        if before.empty:
            continue
        base = before.iloc[-1]
        after = ab[ab.index > m.t0 - pd.Timedelta(minutes=5)] - base
        if after.empty:
            continue
        total = after.iloc[-1]
        if abs(total) < MIN_MOVE:
            continue
        mins = ((after.index - m.t0).total_seconds() / 60 + 5).values      # bar end time minus publish time
        frac = (after * np.sign(total) / abs(total)).values
        t50 = mins[np.argmax(frac >= 0.5)] if (frac >= 0.5).any() else np.nan
        t80 = mins[np.argmax(frac >= 0.8)] if (frac >= 0.8).any() else np.nan
        bk = bucket(turn.get(tk, np.nan))
        at = {c: float(np.interp(c, mins, frac)) for c in CHECK}
        rows.append(dict(ticker=tk, published=m.t0.strftime("%Y-%m-%d %H:%M"), title=str(m.title)[:120],
                         bucket=bk, day_move=round(float(total), 4), minutes_to_50=t50, minutes_to_80=t80,
                         **{f"done_after_{c}min": round(v, 3) for c, v in at.items()}))
        paths[bk].append([at[c] for c in CHECK])
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "intraday_events.csv", index=False)
    summary = {}
    for bk, g in df.groupby("bucket") if len(df) else []:
        summary[bk] = dict(n=len(g), median_minutes_to_50=float(g.minutes_to_50.median()),
                           median_minutes_to_80=float(g.minutes_to_80.median()),
                           share_of_move_left_after={f"{c}min": round(1 - float(g[f'done_after_{c}min'].mean()), 3)
                                                     for c in CHECK})
    (OUT / "intraday.json").write_text(json.dumps(dict(n=len(df), min_move=MIN_MOVE, by_bucket=summary), indent=1))
    print(json.dumps(summary, indent=1), flush=True)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(7, 4))
    col = {"large": "#2a78d6", "mid": "#1D9E75", "small": "#eb6834"}
    for bk, v in paths.items():
        if v:
            ax.plot([0] + CHECK, [0] + list(np.mean(v, axis=0) * 100), "-o", color=col[bk], label=f"{bk} (n={len(v)})")
    ax.axhline(100, color="grey", lw=0.6, ls=":")
    ax.set(title="How much of the day's move has happened, minutes after an announcement",
           xlabel="Minutes after publish time", ylabel="% of the day's move")
    ax.legend(); fig.tight_layout(); fig.savefig(OUT / "intraday.png", dpi=110)


if __name__ == "__main__":
    main()
