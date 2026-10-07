"""Four slow strategies for a student investor, tested with a holdout.

Same rules for all (fixed before looking at any result):
  * Long-only (no shorting, as on a normal Nordnet account).
  * Development: signals 2023-01-01 .. 2025-12-31.  Holdout: signals from 2026-01-01.
    Each strategy has a small grid of settings; the one with the highest t-statistic on the
    development period (min 30 trades / 24 months) is chosen and then run ONCE on the holdout.
  * Costs: Nordnet Student (0.15% per side Nordic; 0.2% min 49 kr elsewhere + 0.15% currency)
    plus the bid-ask spread by liquidity (0.05% / 0.4% / 1.5% round trip), on a 10 000 kr position.
  * Results are measured as excess return over the equal-weight market of all stocks in the data,
    using each stock's beta from the previous 252 days (past data only).
  * Event strategies enter at the first opening price after the announcement was public
    (pre-open or after-close announcements: that session's open; intraday: next day's open)
    and exit at the close H trading days later. t-statistics are clustered by month.

  A insider_buy  Oslo Børs insiders buying their own company's shares (excluding share programmes,
                 options, rights issues and other non-voluntary trades)
  B buyback      Announcement that a share buyback programme is starting
  C factor       Monthly portfolio of Nordic large/mid caps: 12-1 month momentum, low volatility,
                 or both; rebalanced at month-end closes
  D freight      Freight-rate ETFs (BDRY dry bulk, BWET tankers; US close, after Oslo closes)
                 as a signal for Oslo-listed shipping stocks the next day
"""
import json
import os
import re
from pathlib import Path

import numpy as np
import pandas as pd

import backtest as bt

OUT = Path("results")
DATA = bt.DATA
DEV_END = "2025-12-31"
NORDIC = (".OL", ".ST", ".CO", ".HE")
SPREAD = {"large": 0.0005, "mid": 0.004, "small": 0.015}
DRY = ["2020.OL", "HSHP.OL", "JIN.OL"]
TANK = ["FRO.OL", "HAFNI.OL", "OET.OL"]

BUY = re.compile(r"\b(bought|purchased|has (today )?(bought|purchased|acquired)|acquired \d|acquisition of \d|"
                 r"kjøpt|kjøpte|har kjøpt|har i dag kjøpt|purchase of [\d,. ]+ shares)\b", re.I)
SELL = re.compile(r"\b(sold|has sold|solgt|har solgt|salg av [\d,. ]+ aksjer|sale of [\d,. ]+ shares|disposed)\b", re.I)
PROGRAMME = re.compile(r"share (saving|purchase|incentive|option|bonus)|employee|ansatt|aksjespare|aksjeprogram|"
                       r"spareprogram|incentive|\bLTI\b|\bRSUs?\b|\bPSUs?\b|option|opsjon|tildel|\bgrant|allocat|allot|"
                       r"subscription right|tegningsrett|rights issue|fortrinnsrett|exercise|innløs|share[- ]based|"
                       r"bonus share|dividend reinvest|scrip|vesting|settlement of|private placement|rettet emisjon|"
                       r"lending|lån av aksjer|pledge|pant|transfer|gift|arv|inheritance", re.I)
INITIATE = re.compile(r"(initiat|launch|commenc|start|new|announces?|resolv|approv|establish|igangsett|iverksett|"
                      r"starter|nytt|vedtak).{0,60}(buy-?back|repurchase|tilbakekjøp)|"
                      r"(buy-?back|repurchase|tilbakekjøp).{0,40}(program\w*).{0,40}(initiat|launch|commenc|start|igangsett)", re.I)
NOT_INIT = re.compile(r"transaction|week|status|update|complet|ended|result|carried out|daily|uke|gjennomført|"
                      r"purchases made|repurchases? of own shares on|made under|under the|conclu|terminat|avslut|"
                      r"report|ukentlig|transaksjoner|bond|obligasjon|employee|ansatt|share saving|spareprogram|incentive", re.I)


def cost(ticker, bucket):
    nordic = ticker.endswith(NORDIC)
    per_side = 0.0015 if nordic else max(0.002, 49 / 10_000)
    return 2 * per_side + (0 if nordic else 0.0015) + SPREAD[bucket]


def tstat(x, groups):
    m = pd.Series(x).groupby(groups).mean()
    return round(float(m.mean() / m.std() * np.sqrt(len(m))), 2) if len(m) > 2 and m.std() > 0 else None


class Market:
    def __init__(self):
        self.d, _ = bt.load_prices()
        d = self.d
        self.dates = list(map(str, d.dates))
        self.pos = {x: i for i, x in enumerate(self.dates)}
        # betas from the previous 252 days, refreshed monthly
        self.beta_at = {}
        r, rm = d.rdf, d.rmdf
        for i in range(252, len(self.dates), 21):
            w, m = r.iloc[i - 252:i], rm.iloc[i - 252:i]
            ok = m.notna()
            self.beta_at[i] = w[ok].apply(lambda s: s.cov(m[ok]) / m[ok].var()).clip(0, 3).fillna(1.0)

    def beta(self, t, ticker):
        k = max((i for i in self.beta_at if i <= t), default=None)
        return float(self.beta_at[k].get(ticker, 1.0)) if k is not None else 1.0

    def trade(self, ticker, entry_day, hold):
        """Excess return from the open of entry_day to the close hold-1 trading days later."""
        d = self.d
        if ticker not in d.ix or entry_day not in self.pos:
            return None
        b = d.ix[ticker]
        td = d.tdays[b]
        p = np.searchsorted(td, self.pos[entry_day])
        if p + hold - 1 >= len(td):
            return None
        e, x = td[p], td[p + hold - 1]
        has_open = not np.isnan(d.O[e, b])
        lent = d.logO[e, b] if has_open else d.logC[e, b]
        mo = d.logMo[e] if has_open else d.logMc[e]
        bt_ = self.beta(e, ticker)
        stock = d.logC[x, b] - lent
        return dict(entry=self.dates[e], exit=self.dates[x], raw=float(stock),
                    gross=float(stock - bt_ * (d.logMc[x] - mo)), bucket=bt.bucket(d.adv[e, b]))


def entry_day(mk, ticker, published_utc):
    """First session whose OPEN comes after the announcement became public."""
    if ticker not in mk.d.ix:
        return None
    loc = pd.Timestamp(published_utc).tz_convert("Europe/Oslo")
    day, hm = loc.strftime("%Y-%m-%d"), loc.strftime("%H:%M")
    td = [mk.dates[i] for i in mk.d.tdays[mk.d.ix[ticker]]]
    i = np.searchsorted(td, day)
    if i < len(td) and td[i] == day and hm >= "09:00":
        i += 1                       # published during or after the session: next open
    return td[i] if i < len(td) else None


def run_grid(name, events_fn, grid, min_n=30):
    tried = []
    for s in grid:
        ev = events_fn(s, "dev")
        net = ev.gross - ev.cost if len(ev) else pd.Series(dtype=float)
        tried.append(dict(setting=s, trades=len(ev), gross=round(float(ev.gross.mean()), 4) if len(ev) else None,
                          net=round(float(net.mean()), 4) if len(ev) else None,
                          t=tstat(net.values, ev.signal.str[:7].values) if len(ev) else None))
    ok = [x for x in tried if x["trades"] >= min_n and x["t"] is not None]
    best = max(ok, key=lambda x: x["t"]) if ok else None
    res = dict(tried_on_dev=tried, chosen=best["setting"] if best else None, dev=best)
    if best and os.environ.get("DEV_ONLY") != "1":
        ev = events_fn(best["setting"], "holdout")                       # evaluated once
        net = ev.gross - ev.cost
        res["holdout"] = dict(trades=len(ev), gross=round(float(ev.gross.mean()), 4) if len(ev) else None,
                              net=round(float(net.mean()), 4) if len(ev) else None,
                              win=round(float((net > 0).mean()), 3) if len(ev) else None,
                              raw=round(float(ev.raw.mean()), 4) if len(ev) else None,
                              t=tstat(net.values, ev.signal.str[:7].values) if len(ev) else None)
        ev.to_csv(OUT / f"strategy_{name}_holdout_trades.csv", index=False)
    print(name, "| chosen", res["chosen"], "| dev", best, "| HOLDOUT", res.get("holdout"), flush=True)
    return res


# ---------------------------------------------------------------- A insider buys
def insider_events(mk):
    nw = pd.read_csv(DATA / "newsweb.csv.gz")
    bodies = pd.read_csv(DATA / "insider_bodies.csv.gz")
    m = nw[nw.category.fillna("").str.contains("MANAGERS")].merge(bodies, on="id", how="left")
    m["text"] = m.title.fillna("") + " " + m.body.fillna("")
    m["buy"] = m.text.str.contains(BUY) & ~m.text.str.contains(SELL) & ~m.text.str.contains(PROGRAMME)
    m["ticker"] = m.issuer.astype(str) + ".OL"
    stats = dict(messages=len(m), with_text=int(m.body.notna().sum()), classified_buys=int(m.buy.sum()),
                 sample_buys=m[m.buy].title.head(8).tolist())
    rows = []
    for _, x in m[m.buy].iterrows():
        e = entry_day(mk, x.ticker, x.published_utc)
        if e:
            rows.append(dict(ticker=x.ticker, signal=e, published=x.published_utc, title=x.title))
    ev = pd.DataFrame(rows).sort_values("signal")
    # cluster = number of buy messages for the company in the previous 10 trading days incl. this one
    ev["cluster"] = 1
    for tk, g in ev.groupby("ticker"):
        p = g.signal.map(mk.pos).values
        ev.loc[g.index, "cluster"] = [int(((p <= pi) & (p > pi - 10)).sum()) for pi in p]
    return ev, stats


def make_event_fn(mk, ev, extra=lambda e, s: True, gap=40):
    def fn(s, part):
        e = ev[(ev.signal <= DEV_END) if part == "dev" else (ev.signal > DEV_END)]
        rows, last = [], {}
        for _, x in e.iterrows():
            if not extra(x, s):
                continue
            p = mk.pos[x.signal]
            if x.ticker in last and p - last[x.ticker] < gap:
                continue                      # one trade per company per gap period
            t = mk.trade(x.ticker, x.signal, s["hold"])
            if t is None or (s.get("liq") == "lm" and t["bucket"] == "small"):
                continue
            last[x.ticker] = p
            rows.append(dict(ticker=x.ticker, signal=x.signal, cost=cost(x.ticker, t["bucket"]),
                             title=x.get("title", ""), **t))
        return pd.DataFrame(rows) if rows else pd.DataFrame(columns=["signal", "gross", "cost", "raw"])
    return fn


# ---------------------------------------------------------------- B buybacks
def buyback_events(mk):
    nw = pd.read_csv(DATA / "newsweb.csv.gz")
    t = nw.title.fillna("")
    b = nw[t.str.contains(INITIATE) & ~t.str.contains(NOT_INIT)].copy()
    b["ticker"] = b.issuer.astype(str) + ".OL"
    rows = []
    for _, x in b.iterrows():
        e = entry_day(mk, x.ticker, x.published_utc)
        if e:
            rows.append(dict(ticker=x.ticker, signal=e, title=x.title))
    ev = pd.DataFrame(rows).sort_values("signal")
    return ev, dict(announcements=len(b), tradable=len(ev), sample=b.title.head(10).tolist())


# ---------------------------------------------------------------- C factor portfolio
def factor(mk, s, part):
    d = mk.d
    dates = pd.to_datetime(mk.dates)
    month_end = [i for i in range(len(dates) - 1) if dates[i].month != dates[i + 1].month and i >= 252]
    vol = d.rdf.rolling(126, min_periods=90).std().values
    rows, prev = [], set()
    for a, b_ in zip(month_end[:-1], month_end[1:]):
        sig = mk.dates[a]
        if (part == "dev") != (sig <= DEV_END):
            continue
        ok = [k for k, tk in enumerate(d.tickers)
              if tk.endswith(NORDIC) and bt.bucket(d.adv[a, k]) in ("large", "mid")
              and not np.isnan(d.mom[a, k]) and not np.isnan(vol[a, k]) and not np.isnan(d.C[b_, k])]
        if len(ok) < 30:
            continue
        mom = pd.Series(d.mom[a, ok], index=ok).rank(pct=True)
        lv = pd.Series(-vol[a, ok], index=ok).rank(pct=True)
        score = {"momentum": mom, "lowvol": lv, "both": (mom + lv) / 2}[s["kind"]]
        pick = set(score.sort_values(ascending=False).index[:s["n"]])
        ret = lambda k: np.log(d.C[b_, k] / d.C[a, k]) if not np.isnan(d.C[a, k]) else np.nan
        port = np.nanmean([ret(k) for k in pick])
        bench = np.nanmean([ret(k) for k in ok])
        turnover = len(pick - prev) / s["n"] if prev else 1.0
        c = turnover * 2 * np.mean([0.0015 + SPREAD[bt.bucket(d.adv[a, k])] / 2 for k in pick])
        rows.append(dict(signal=sig, gross=float(port - bench), cost=float(c), raw=float(port), bench=float(bench),
                         turnover=turnover))
        prev = pick
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- D freight
def freight_fn(mk):
    fr = pd.read_csv(DATA / "freight.csv.gz", index_col=0)
    lr = np.log(fr).diff()

    def fn(s, part):
        etf = "BDRY" if s["seg"] == "dry" else "BWET"
        basket = DRY if s["seg"] == "dry" else TANK
        sig = lr[etf].rolling(s["k"]).sum()
        rows, busy = [], -1
        for day, v in sig.dropna().items():
            if (part == "dev") != (day <= DEV_END) or v < s["thr"]:
                continue
            nxt = next((x for x in mk.dates[np.searchsorted(mk.dates, day):] if x > day), None)
            if nxt is None or mk.pos[nxt] <= busy:
                continue                       # don't overlap holding periods
            ts = [mk.trade(tk, nxt, s["hold"]) for tk in basket]
            ts = [t for t in ts if t]
            if not ts:
                continue
            busy = mk.pos[nxt] + s["hold"] - 1
            rows.append(dict(signal=nxt, gross=float(np.mean([t["gross"] for t in ts])),
                             raw=float(np.mean([t["raw"] for t in ts])),
                             cost=float(np.mean([cost(tk, t["bucket"]) for tk, t in zip(basket, ts)]))))
        return pd.DataFrame(rows) if rows else pd.DataFrame(columns=["signal", "gross", "cost", "raw"])
    return fn


def main():
    mk = Market()
    report = dict(procedure=__doc__, strategies={})
    if (DATA / "insider_bodies.csv.gz").exists():
        ev, st = insider_events(mk)
        report["insider_classification"] = st
        print("insider:", st, flush=True)
        grid = [dict(hold=h, liq=l, cluster=c) for h in [20, 60, 120] for l in ["all", "lm"] for c in [1, 2]]
        report["strategies"]["A_insider_buy"] = run_grid(
            "A_insider_buy", make_event_fn(mk, ev, lambda e, s: e.cluster >= s["cluster"]), grid)
    ev, st = buyback_events(mk)
    report["buyback_classification"] = st
    print("buyback:", {k: v for k, v in st.items() if k != "sample"}, flush=True)
    grid = [dict(hold=h, liq=l) for h in [20, 60, 120] for l in ["all", "lm"]]
    report["strategies"]["B_buyback"] = run_grid("B_buyback", make_event_fn(mk, ev, gap=120), grid)
    grid = [dict(kind=k, n=n) for k in ["momentum", "lowvol", "both"] for n in [10, 20]]
    report["strategies"]["C_factor"] = run_grid("C_factor", lambda s, p: factor(mk, s, p), grid, min_n=24)
    if (DATA / "freight.csv.gz").exists():
        grid = [dict(seg=g, k=k, hold=h, thr=t) for g in ["dry", "tank"] for k in [1, 5] for h in [1, 5]
                for t in [0.0, 0.02]]
        report["strategies"]["D_freight"] = run_grid("D_freight", freight_fn(mk), grid)
    # context: what simply holding the market did (equal-weight, Nordic large/mid, before fund fees)
    if os.environ.get("DEV_ONLY") == "1":
        print(json.dumps({k: [ (x["setting"], x["trades"], x["net"], x["t"]) for x in v["tried_on_dev"]]
                          for k, v in report["strategies"].items()}, default=str)[:3000])
        return
    (OUT / "strategies.json").write_text(json.dumps(report, indent=1, default=str))


if __name__ == "__main__":
    main()
