#!/usr/bin/env python3
"""
Nyhets-ML + paper trading-backtest
==================================
Spørsmål: kan ekte børsmeldinger (kontrakter, innsidekjøp, kvartalstall …) +
kursdata si noe om hvilke aksjer som slår OSEBX de neste 10 handelsdagene?

    børsmeldinger ─┐
                   ├─> features per aksje per dag ─> modell (walk-forward) ─> sannsynlighet
    kurser ────────┘                                                         │
                         paper trading: kjøp de beste ved neste åpning, hold 10 dager

Ærlighetsregler i koden:
  * All informasjon må være kjent ved børsslutt dagen signalet gis. Handel skjer
    på NESTE dags åpningskurs. Meldinger etter 16:20 teller først neste handelsdag.
  * Walk-forward: modellen trenes på nytt hver måned, kun på data FØR måneden,
    med en karantene på 10 handelsdager så treningsmålet ikke overlapper testen.
  * Kurtasje + glidning trekkes på hver handel.
  * Sammenlignes med OSEBX og med 300 tilfeldige porteføljer som handler like ofte.

Output: nordnet_data/news_ml/results.json  (dashboardet leser denne)
        nordnet_data/news_ml/report.md      (lesbar på GitHub/mobil)
        nordnet_data/news_ml/paper_live.json (den fremadrettede paper-porteføljen)
"""

import argparse
import glob
import json
import math
import os
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import roc_auc_score

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from news_ml.common import (BENCHMARK, NEWS_DIR, OUT_DIR, PRICE_DIR, classify,  # noqa: E402
                            insider_direction, load_universe, parse_amount_nok)

OSLO = ZoneInfo("Europe/Oslo")

# ---- Faste regler, bestemt FØR resultatene ble sett (ikke tunet på testdata) ----
HOLD = 10                 # handelsdager per posisjon
SLOTS = 8                 # maks samtidige posisjoner
MAX_NEW_PER_DAY = 3       # maks nye kjøp per dag
MIN_PROB = 0.55           # modellen må mene >55 % sjanse for å slå OSEBX
COST_PER_SIDE = 0.002     # 0,1 % kurtasje + 0,1 % glidning, per kjøp og per salg
MIN_TURNOVER = 2e6        # minst 2 MNOK snittomsetning per dag (20 d) for å kunne handles
START_CAPITAL = 100_000.0
MIN_TRAIN_DAYS = 500      # ~2 års historikk før første test
N_RANDOM = 300
JUMP_LIMIT = 0.45         # daglige hopp større enn ±45 % behandles som selskapshendelse (f.eks. utskillelse)

FEATURES = [
    # kurs
    "ret_5", "ret_20", "ret_60", "ret_120", "ex_20", "ex_60", "dist_sma50", "dist_sma200", "bb_pctb",
    "rsi_14", "vol_20", "vol_ratio", "dd_252", "volz", "log_turnover", "rank_ret_20", "rank_ret_60",
    "rank_vol_20",
    # nyheter
    "n_news_30", "news_z", "n_contract_30", "n_contract_90", "contract_rel_mcap_90", "contract_rel_mcap_qtd",
    "days_since_contract", "contract_react_90", "insider_buy_90", "insider_sell_90", "insider_net_90",
    "n_buyback_90", "n_financing_90", "n_mna_90", "n_guidance_30", "days_since_report", "days_to_report",
    "report_react_last",
    # marked
    "bench_ret_20", "bench_vol_20",
]
FEATURE_NO = {
    "ret_5": "Avkastning 5 d", "ret_20": "Avkastning 20 d", "ret_60": "Avkastning 60 d",
    "ret_120": "Avkastning 120 d", "ex_20": "Meravkastning 20 d", "ex_60": "Meravkastning 60 d",
    "dist_sma50": "Avstand til SMA50", "dist_sma200": "Avstand til SMA200", "bb_pctb": "Bollinger %B",
    "rsi_14": "RSI 14", "vol_20": "Volatilitet 20 d", "vol_ratio": "Volatilitet 20 d / 120 d",
    "dd_252": "Fall fra 52-ukers topp", "volz": "Volum-z (20 d mot 60 d)", "log_turnover": "Omsetning (log)",
    "rank_ret_20": "Rang avkastning 20 d", "rank_ret_60": "Rang avkastning 60 d",
    "rank_vol_20": "Rang volatilitet", "n_news_30": "Antall meldinger 30 d",
    "news_z": "Meldingsaktivitet mot normalt", "n_contract_30": "Kontraktsmeldinger 30 d",
    "n_contract_90": "Kontraktsmeldinger 90 d", "contract_rel_mcap_90": "Kontraktsverdi 90 d / markedsverdi",
    "contract_rel_mcap_qtd": "Kontraktsverdi siden rapport / markedsverdi",
    "days_since_contract": "Dager siden kontrakt", "contract_react_90": "Kursreaksjon på kontrakter 90 d",
    "insider_buy_90": "Innsidekjøp 90 d", "insider_sell_90": "Innsidesalg 90 d",
    "insider_net_90": "Netto innsidekjøp 90 d", "n_buyback_90": "Tilbakekjøp 90 d",
    "n_financing_90": "Emisjoner/lån 90 d", "n_mna_90": "Oppkjøp/fusjon 90 d",
    "n_guidance_30": "Guiding/oppdatering 30 d", "days_since_report": "Dager siden kvartalsrapport",
    "days_to_report": "Dager til ventet rapport", "report_react_last": "Kursreaksjon på forrige rapport",
    "bench_ret_20": "OSEBX 20 d", "bench_vol_20": "OSEBX volatilitet",
}


# =============================================================== data
def load_prices():
    px = pd.read_csv(os.path.join(PRICE_DIR, "prices.csv"), parse_dates=["date"])
    px = px.dropna(subset=["close", "adj_close"])
    px = px[px["close"] > 0]
    piv = {c: px.pivot_table(index="date", columns="ticker", values=c, aggfunc="last")
           for c in ["open", "close", "adj_close", "volume", "high", "low"]}
    cal = piv["close"].index.sort_values()
    if BENCHMARK in piv["close"].columns:
        cal = piv["close"][BENCHMARK].dropna().index.sort_values()
    piv = {k: v.reindex(cal) for k, v in piv.items()}
    shares = {}
    sp = os.path.join(PRICE_DIR, "shares.json")
    if os.path.exists(sp):
        shares = json.load(open(sp))
    return piv, cal, shares


def repair_jumps(adj):
    """Bytt ut urealistiske endagshopp (utskillelser o.l. som Yahoo ikke justerer) med 0 % avkastning."""
    r = adj.ffill().pct_change(fill_method=None)
    bad = r.abs() > JUMP_LIMIT
    r = r.mask(bad, 0.0)
    first = adj.apply(lambda s: s.first_valid_index())
    rebuilt = (1 + r.fillna(0)).cumprod()
    for t in adj.columns:
        fv = first[t]
        if fv is None or pd.isna(fv):
            continue
        rebuilt[t] = rebuilt[t] / rebuilt.at[fv, t] * adj.at[fv, t]
        rebuilt.loc[rebuilt.index < fv, t] = np.nan
    rebuilt = rebuilt.where(adj.notna())
    events = [(str(adj.index[i].date()), adj.columns[j]) for i, j in zip(*np.where(bad.to_numpy()))]
    return rebuilt, events


def load_news(universe, cal):
    rows = []
    for p in sorted(glob.glob(os.path.join(NEWS_DIR, "messages_*.jsonl"))):
        with open(p, encoding="utf-8") as f:
            rows += [json.loads(l) for l in f if l.strip()]
    if not rows:
        return pd.DataFrame(columns=["ticker", "sday", "kind", "title", "amount", "ins_dir", "published"])
    df = pd.DataFrame(rows)
    issuer_to_ticker = {u["issuer"]: u["ticker"] for u in universe}
    df["ticker"] = df["issuer"].map(issuer_to_ticker)
    df = df.dropna(subset=["ticker", "published"])
    df["kind"] = [classify(t or "", c or "") for t, c in zip(df["title"], df["category"])]  # alltid nyeste regler
    ts = pd.to_datetime(df["published"], utc=True, errors="coerce")
    df = df[ts.notna()].copy()
    local = ts[ts.notna()].dt.tz_convert(OSLO)
    # signaldag = første handelsdag der børsslutt (16:20) kommer etter publisering
    cutoff = (local.dt.hour * 60 + local.dt.minute) >= 16 * 60 + 20
    d = local.dt.tz_localize(None).dt.normalize()
    pos = cal.searchsorted(d.to_numpy(), side="left")
    on_cal = (pos < len(cal)) & (cal[np.minimum(pos, len(cal) - 1)] == d.to_numpy())
    pos = np.where(on_cal & cutoff.to_numpy(), pos + 1, pos)
    df["sday_idx"] = pos
    df = df[df["sday_idx"] < len(cal)].copy()
    df["sday"] = cal[df["sday_idx"].to_numpy()]
    text = df["title"].fillna("") + "\n" + df.get("body", pd.Series("", index=df.index)).fillna("")
    df["amount"] = [parse_amount_nok(t) if k == "contract" else None for t, k in zip(text, df["kind"])]
    df["ins_dir"] = [insider_direction(t) if k == "insider" else 0 for t, k in zip(text, df["kind"])]
    df["published"] = local.dt.strftime("%Y-%m-%d %H:%M")
    return df[["ticker", "sday", "kind", "title", "amount", "ins_dir", "published"]]


# =============================================================== features
def roll_sum(daily, w):
    return daily.rolling(w, min_periods=1).sum()


def build_panel(piv, cal, shares, news, tickers):
    adj, repaired_events = repair_jumps(piv["adj_close"])
    close = piv["close"]
    ratio = (adj / close).replace([np.inf, -np.inf], np.nan)
    opn = (piv["open"] * ratio).where(piv["open"] > 0)
    vol = piv["volume"]
    bench = adj[BENCHMARK] if BENCHMARK in adj else adj[tickers].pct_change(fill_method=None).mean(axis=1).add(1).cumprod()
    T = [t for t in tickers if t in adj.columns]
    C, O, V = adj[T], opn[T], vol[T]
    r1 = C.pct_change(fill_method=None)
    br1 = bench.pct_change(fill_method=None)
    ex1 = r1.sub(br1, axis=0)

    f = {}
    for w in (5, 20, 60, 120):
        f[f"ret_{w}"] = C / C.shift(w) - 1
    b20, b60 = bench / bench.shift(20) - 1, bench / bench.shift(60) - 1
    f["ex_20"] = f["ret_20"].sub(b20, axis=0)
    f["ex_60"] = f["ret_60"].sub(b60, axis=0)
    sma50, sma200 = C.rolling(50, min_periods=40).mean(), C.rolling(200, min_periods=150).mean()
    f["dist_sma50"], f["dist_sma200"] = C / sma50 - 1, C / sma200 - 1
    m20, s20 = C.rolling(20).mean(), C.rolling(20).std()
    f["bb_pctb"] = (C - (m20 - 2 * s20)) / (4 * s20)
    up, dn = r1.clip(lower=0).rolling(14).mean(), (-r1.clip(upper=0)).rolling(14).mean()
    f["rsi_14"] = 100 - 100 / (1 + up / dn.replace(0, np.nan))
    f["vol_20"] = r1.rolling(20).std()
    f["vol_ratio"] = f["vol_20"] / r1.rolling(120, min_periods=60).std()
    f["dd_252"] = C / C.rolling(252, min_periods=60).max() - 1
    lv = np.log1p(V)
    f["volz"] = (lv.rolling(20).mean() - lv.rolling(60).mean()) / lv.rolling(60).std()
    turnover = (close[T] * V).rolling(20, min_periods=10).mean()
    f["log_turnover"] = np.log1p(turnover)
    for k in ("ret_20", "ret_60", "vol_20"):
        f[f"rank_{k}"] = f[k].rank(axis=1, pct=True)
    f["bench_ret_20"] = pd.DataFrame({t: b20 for t in T})
    f["bench_vol_20"] = pd.DataFrame({t: br1.rolling(20).std() for t in T})

    # ---- nyheter -> daglige matriser (dato x ticker)
    def daily(mask, value=None):
        sub = news[mask & news["ticker"].isin(T)]
        if sub.empty:
            return pd.DataFrame(0.0, index=cal, columns=T)
        val = sub[value] if value else pd.Series(1.0, index=sub.index)
        m = pd.DataFrame({"sday": sub["sday"], "ticker": sub["ticker"], "v": val.fillna(0).astype(float)})
        return m.pivot_table(index="sday", columns="ticker", values="v", aggfunc="sum").reindex(index=cal, columns=T).fillna(0.0)

    k = news["kind"]
    all_n = daily(news["ticker"].notna())
    con_n = daily(k == "contract")
    con_amt = daily(k == "contract", "amount")
    ins_buy = daily((k == "insider") & (news["ins_dir"] > 0))
    ins_sell = daily((k == "insider") & (news["ins_dir"] < 0))
    rep_n = daily(k == "report")
    f["n_news_30"] = roll_sum(all_n, 30)
    base = roll_sum(all_n, 250) / 250 * 30
    f["news_z"] = (f["n_news_30"] - base) / np.sqrt(base + 1)
    f["n_contract_30"], f["n_contract_90"] = roll_sum(con_n, 30), roll_sum(con_n, 90)
    sh = pd.Series({t: shares.get(t, np.nan) for t in T})
    mcap = close[T].mul(sh, axis=1)  # NB: dagens aksjeantall - grov tilnærming bakover i tid
    f["contract_rel_mcap_90"] = roll_sum(con_amt, 90) / mcap
    # kontraktsverdi siden siste kvartalsrapport (det KOG-mønsteret handlet om)
    rep_group = (rep_n > 0).cumsum()
    qtd = pd.DataFrame(index=cal, columns=T, dtype=float)
    for t in T:
        qtd[t] = con_amt[t].groupby(rep_group[t]).cumsum()
    f["contract_rel_mcap_qtd"] = qtd / mcap

    idx = np.arange(len(cal))

    def days_since(event_df, cap=400):
        out = pd.DataFrame(index=cal, columns=T, dtype=float)
        for t in T:
            last = pd.Series(np.where(event_df[t].to_numpy() > 0, idx, np.nan), index=cal).ffill()
            out[t] = np.minimum(idx - last.to_numpy(), cap)
        return out.fillna(cap)

    f["days_since_contract"] = days_since(con_n)
    dsr = days_since(rep_n)
    f["days_since_report"] = dsr
    f["days_to_report"] = (63 - dsr).clip(lower=-30)  # ~63 handelsdager mellom kvartalsrapporter
    react = ex1.where(con_n > 0)
    f["contract_react_90"] = react.rolling(90, min_periods=1).mean()
    rep_react = ex1.where(rep_n > 0).ffill(limit=120)
    f["report_react_last"] = rep_react
    f["insider_buy_90"], f["insider_sell_90"] = roll_sum(ins_buy, 90), roll_sum(ins_sell, 90)
    f["insider_net_90"] = f["insider_buy_90"] - f["insider_sell_90"]
    f["n_buyback_90"] = roll_sum(daily(k == "buyback"), 90)
    f["n_financing_90"] = roll_sum(daily(k == "financing"), 90)
    f["n_mna_90"] = roll_sum(daily(k == "mna"), 90)
    f["n_guidance_30"] = roll_sum(daily(k == "guidance"), 30)

    # ---- mål: kjøp neste åpning, selg ved slutt dag t+HOLD, minus OSEBX samme periode
    entry = O.shift(-1)
    exit_ = C.shift(-HOLD)
    fwd = exit_ / entry - 1
    if BENCHMARK in adj:
        bo = piv["open"][BENCHMARK] * (adj[BENCHMARK] / piv["close"][BENCHMARK])
        bench_open = bo.where(bo > 0).fillna(bench.shift(1)).fillna(bench)
    else:
        bench_open = bench
    bfwd = bench.shift(-HOLD) / bench_open.shift(-1) - 1
    fwd_ex = fwd.sub(bfwd, axis=0)

    hist = C.notna().cumsum()
    long = []
    for name, m in f.items():
        long.append(m[T].stack(future_stack=True).rename(name))
    panel = pd.concat(long, axis=1)
    panel["fwd"] = fwd.stack(future_stack=True)
    panel["fwd_ex"] = fwd_ex.stack(future_stack=True)
    panel["turnover"] = turnover.stack(future_stack=True)
    panel["hist"] = hist.stack(future_stack=True)
    panel["close"] = close[T].stack(future_stack=True)
    panel.index.names = ["date", "ticker"]
    panel = panel.reset_index()
    panel = panel[panel["close"].notna() & (panel["hist"] >= 150)].copy()
    panel[FEATURES] = panel[FEATURES].replace([np.inf, -np.inf], np.nan).astype(float)
    for c in FEATURES:  # helt tomme kolonner (f.eks. ingen rapporter funnet) knekker treningen
        if panel[c].notna().sum() == 0:
            panel[c] = 0.0
    panel["tradeable"] = (panel["turnover"] >= MIN_TURNOVER) & (panel["close"] >= 3)
    return panel, {"C": C, "O": O, "close_raw": close[T], "bench": bench, "bench_open": bench_open,
                   "repaired": repaired_events}


# =============================================================== modell
def make_model():
    return HistGradientBoostingClassifier(max_iter=250, learning_rate=0.04, max_leaf_nodes=15,
                                          min_samples_leaf=300, l2_regularization=1.0, random_state=7)


def walk_forward(panel, cal):
    lab = panel.dropna(subset=["fwd_ex"])
    lab = lab[lab["tradeable"]]
    dates = np.array(sorted(panel["date"].unique()))
    if len(dates) < MIN_TRAIN_DAYS + 60:
        raise SystemExit(f"For lite historikk ({len(dates)} dager).")
    first_test = pd.Timestamp(dates[MIN_TRAIN_DAYS])
    months = pd.period_range(first_test.to_period("M"), pd.Timestamp(dates[-1]).to_period("M"), freq="M")
    cal_pos = {d: i for i, d in enumerate(cal)}
    preds, fold_auc = [], []
    for mo in months:
        m_start, m_end = mo.start_time, mo.end_time
        test = panel[(panel["date"] >= m_start) & (panel["date"] <= m_end)]
        if test.empty:
            continue
        first_pos = cal_pos.get(test["date"].min(), None)
        cut = cal[max(0, first_pos - HOLD - 2)]  # karantene: treningsmål kan ikke strekke seg inn i testen
        train = lab[lab["date"] < cut]
        if len(train) < 5000:
            continue
        y = (train["fwd_ex"] > 0).astype(int)
        model = make_model().fit(train[FEATURES], y)
        p = model.predict_proba(test[FEATURES])[:, 1]
        out = test[["date", "ticker", "fwd", "fwd_ex", "tradeable", "close"]].copy()
        out["p"] = p
        preds.append(out)
        t_lab = out.dropna(subset=["fwd_ex"])
        t_lab = t_lab[t_lab["tradeable"]]
        if t_lab["fwd_ex"].gt(0).nunique() == 2:
            fold_auc.append((str(mo), float(roc_auc_score(t_lab["fwd_ex"] > 0, t_lab["p"])), len(t_lab)))
    preds = pd.concat(preds, ignore_index=True)
    return preds, fold_auc, model, train


# =============================================================== backtest
def simulate(signals, px, cal, start, end, score_col="p", min_score=MIN_PROB, rng=None, entries_per_day=None):
    """Dag for dag: selg posisjoner som har holdt HOLD dager ved slutt, kjøp nye på neste åpning.
    signals: DataFrame date,ticker,score,tradeable.  rng+entries_per_day => tilfeldig portefølje."""
    C, O = px["C"], px["O"]
    days = cal[(cal >= start) & (cal <= end)]
    by_day = {d: g for d, g in signals.groupby("date")}
    cash, positions, pending = START_CAPITAL, [], []
    equity, trades, n_new_by_day = [], [], {}
    for i, d in enumerate(days):
        # 1) fyll ordre fra i går på dagens åpning
        for o in pending:
            px_open = O.at[d, o["ticker"]] if o["ticker"] in O.columns else np.nan
            if not np.isfinite(px_open) or px_open <= 0:
                continue
            alloc = min(o["alloc"], cash)
            if alloc <= 0:
                continue
            shares = alloc * (1 - COST_PER_SIDE) / px_open
            cash -= alloc
            positions.append({"ticker": o["ticker"], "entry_date": d, "entry_px": px_open, "shares": shares,
                              "cost": alloc, "held": 0, "score": o["score"], "signal_date": o["signal_date"]})
        pending = []
        # 2) hold-telling + salg ved slutt
        keep = []
        for pos in positions:
            pos["held"] += 1
            c = C.at[d, pos["ticker"]]
            if np.isfinite(c):
                pos["last_px"] = c
            if pos["held"] >= HOLD:
                exit_px = pos.get("last_px", pos["entry_px"])
                value = pos["shares"] * exit_px * (1 - COST_PER_SIDE)
                cash += value
                trades.append({"ticker": pos["ticker"], "signal_date": str(pos["signal_date"].date()),
                               "entry_date": str(pos["entry_date"].date()), "exit_date": str(d.date()),
                               "entry_px": round(pos["entry_px"], 4), "exit_px": round(exit_px, 4),
                               "ret": value / pos["cost"] - 1, "score": pos["score"]})
            else:
                keep.append(pos)
        positions = keep
        mtm = sum(p["shares"] * p.get("last_px", p["entry_px"]) for p in positions)
        eq = cash + mtm
        equity.append(eq)
        # 3) nye signaler ved slutt i dag -> ordre til i morgen
        if i == len(days) - 1:
            break
        free = SLOTS - len(positions)
        if free <= 0:
            continue
        g = by_day.get(d)
        if g is None:
            continue
        held = {p["ticker"] for p in positions}
        cand = g[g["tradeable"] & ~g["ticker"].isin(held)]
        if rng is not None:
            n = min(entries_per_day.get(d, 0), free, len(cand))
            pick = cand.sample(n=n, random_state=rng) if n > 0 else cand.iloc[:0]
        else:
            cand = cand[cand[score_col] >= min_score].sort_values(score_col, ascending=False)
            pick = cand.head(min(MAX_NEW_PER_DAY, free))
        n_new_by_day[d] = len(pick)
        for _, r in pick.iterrows():
            pending.append({"ticker": r["ticker"], "alloc": eq / SLOTS, "score": float(r[score_col]),
                            "signal_date": d})
    return pd.Series(equity, index=days), trades, n_new_by_day


def metrics(eq, trades, bench_eq=None):
    if len(eq) < 2:
        return {}
    r = eq.pct_change().dropna()
    years = (eq.index[-1] - eq.index[0]).days / 365.25
    total = eq.iloc[-1] / eq.iloc[0] - 1
    dd = (eq / eq.cummax() - 1).min()
    out = {"total_return": total, "cagr": (1 + total) ** (1 / years) - 1 if years > 0 else None,
           "vol": r.std() * math.sqrt(252), "sharpe": (r.mean() / r.std() * math.sqrt(252)) if r.std() > 0 else None,
           "max_dd": dd, "years": years}
    if trades is not None:
        tr = pd.Series([t["ret"] for t in trades])
        out.update({"n_trades": len(tr), "hit_rate": float((tr > 0).mean()) if len(tr) else None,
                    "avg_trade": float(tr.mean()) if len(tr) else None,
                    "median_trade": float(tr.median()) if len(tr) else None})
    if bench_eq is not None:
        b = bench_eq.reindex(eq.index).ffill()
        out["bench_total"] = b.iloc[-1] / b.iloc[0] - 1
        out["excess_total"] = total - out["bench_total"]
    return out


def clean(o):
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if not np.isfinite(o) else round(float(o), 6)
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (pd.Timestamp, datetime)):
        return str(o.date()) if hasattr(o, "date") else str(o)
    return o


# =============================================================== live paper trading (fremover)
def update_live(live_path, latest_signals, px, cal):
    """Ekte paper trading fra i dag og fremover - ingen backtest, ingen fasit."""
    C, O = px["C"], px["O"]
    today = cal[-1]
    st = json.load(open(live_path)) if os.path.exists(live_path) else {
        "started": str(today.date()), "cash": START_CAPITAL, "positions": [], "pending": [], "closed": [],
        "equity": [], "last_date": None}
    if st["last_date"] == str(today.date()):
        return st
    new_days = [today] if st["last_date"] is None else [d for d in cal if d > pd.Timestamp(st["last_date"])]
    for d in new_days:
        still = []
        for o in st["pending"]:
            if pd.Timestamp(o["signal_date"]) >= d:
                still.append(o)
                continue
            p = O.at[d, o["ticker"]] if o["ticker"] in O.columns else np.nan
            if np.isfinite(p) and p > 0 and st["cash"] >= o["alloc"] * 0.5:
                alloc = min(o["alloc"], st["cash"])
                st["cash"] -= alloc
                st["positions"].append({"ticker": o["ticker"], "signal_date": o["signal_date"],
                                        "entry_date": str(d.date()), "entry_px": float(p),
                                        "shares": alloc * (1 - COST_PER_SIDE) / p, "cost": alloc, "held": 0,
                                        "p": o["p"]})
        st["pending"] = still
        keep = []
        for pos in st["positions"]:
            pos["held"] += 1
            c = C.at[d, pos["ticker"]]
            if np.isfinite(c):
                pos["last_px"] = float(c)
            if pos["held"] >= HOLD:
                val = pos["shares"] * pos.get("last_px", pos["entry_px"]) * (1 - COST_PER_SIDE)
                st["cash"] += val
                st["closed"].append({**pos, "exit_date": str(d.date()), "ret": val / pos["cost"] - 1})
            else:
                keep.append(pos)
        st["positions"] = keep
        eq = st["cash"] + sum(p["shares"] * p.get("last_px", p["entry_px"]) for p in st["positions"])
        st["equity"].append({"date": str(d.date()), "equity": eq})
    # nye ordre fra dagens signaler (fylles på neste åpning)
    free = SLOTS - len(st["positions"]) - len(st["pending"])
    held = {p["ticker"] for p in st["positions"]} | {o["ticker"] for o in st["pending"]}
    cand = latest_signals[latest_signals["tradeable"] & (latest_signals["p"] >= MIN_PROB)
                          & ~latest_signals["ticker"].isin(held)].sort_values("p", ascending=False)
    eq_now = st["equity"][-1]["equity"] if st["equity"] else st["cash"]
    for _, r in cand.head(max(0, min(MAX_NEW_PER_DAY, free))).iterrows():
        st["pending"].append({"ticker": r["ticker"], "signal_date": str(today.date()), "alloc": eq_now / SLOTS,
                              "p": float(r["p"])})
    st["last_date"] = str(today.date())
    with open(live_path, "w") as f:
        json.dump(clean(st), f, indent=1)
    return st


# =============================================================== main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT_DIR)
    ap.add_argument("--case", default="KOG.OL")
    ap.add_argument("--no-live", action="store_true")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    universe = load_universe()
    piv, cal, shares = load_prices()
    tickers = sorted({u["ticker"] for u in universe} & set(piv["close"].columns))
    name_of = {u["ticker"]: u["slug"].rsplit("-", 2)[0].replace("-", " ").title() for u in universe}
    news = load_news(universe, cal)
    print(f"{len(tickers)} aksjer, {len(cal)} handelsdager, {len(news)} børsmeldinger")

    panel, px = build_panel(piv, cal, shares, news, tickers)
    preds, fold_auc, last_model, last_train = walk_forward(panel, cal)
    start, end = preds["date"].min(), preds["date"].max()
    print(f"Test (ut-av-utvalget): {start.date()} -> {end.date()}, {len(preds)} rader")

    # ---- strategien
    eq, trades, n_new = simulate(preds, px, cal, start, end)
    bench_eq = (px["bench"].reindex(eq.index) / px["bench"].reindex(eq.index).iloc[0] * START_CAPITAL)
    m_strat = metrics(eq, trades, bench_eq)
    m_bench = metrics(bench_eq, None)

    # ---- regelen fra KOG-diskusjonen (uten ML)
    rule = panel[(panel["date"] >= start) & (panel["date"] <= end)].copy()
    rule["rule"] = ((rule["contract_rel_mcap_qtd"] >= 0.01) & (rule["contract_react_90"] <= 0)
                    & (rule["dist_sma200"] <= 0.05) & (rule["days_to_report"].between(0, 30))).astype(float)
    eq_rule, trades_rule, _ = simulate(rule, px, cal, start, end, score_col="rule", min_score=1.0)
    m_rule = metrics(eq_rule, trades_rule, bench_eq)

    # ---- tilfeldige porteføljer med samme handelsfrekvens
    rng = np.random.RandomState(42)
    finals, rand_curves = [], []
    for s in range(N_RANDOM):
        e_r, _, _ = simulate(preds, px, cal, start, end, rng=rng, entries_per_day=n_new)
        finals.append(e_r.iloc[-1])
        rand_curves.append(e_r.to_numpy())
    rand_curves = np.vstack(rand_curves)
    p_random = float((np.array(finals) >= eq.iloc[-1]).mean())

    # ---- prediksjonskvalitet ut-av-utvalget
    lab = preds.dropna(subset=["fwd_ex"])
    lab = lab[lab["tradeable"]].copy()
    auc = float(roc_auc_score(lab["fwd_ex"] > 0, lab["p"]))
    lab["decile"] = lab.groupby("date")["p"].transform(lambda s: pd.qcut(s.rank(method="first"), 10, labels=False)
                                                       if len(s) >= 10 else np.nan)
    deciles = lab.groupby("decile")["fwd_ex"].agg(["mean", "count"]).reset_index()
    lab["year"] = lab["date"].dt.year
    auc_year = {int(y): float(roc_auc_score(g["fwd_ex"] > 0, g["p"])) for y, g in lab.groupby("year")
                if g["fwd_ex"].gt(0).nunique() == 2}
    ic = lab.groupby("date").apply(lambda g: g["p"].corr(g["fwd_ex"], method="spearman"), include_groups=False)

    # ---- hva modellen bruker (permutasjon på siste 9 mnd ut-av-utvalget)
    # egen modell trent FØR vinduet, så viktigheten måles på data modellen ikke har sett
    imp_start = end - pd.Timedelta(days=270)
    recent = lab[lab["date"] >= imp_start]
    recent_full = panel.merge(recent[["date", "ticker"]], on=["date", "ticker"])
    pos0 = int(cal.searchsorted(imp_start))
    imp_train = panel.dropna(subset=["fwd_ex"])
    imp_train = imp_train[imp_train["tradeable"] & (imp_train["date"] < cal[max(0, pos0 - HOLD - 2)])]
    imp = None
    if len(recent_full) > 500 and len(imp_train) > 5000:
        imp_model = make_model().fit(imp_train[FEATURES], (imp_train["fwd_ex"] > 0).astype(int))
        imp = permutation_importance(imp_model, recent_full[FEATURES], (recent_full["fwd_ex"] > 0).astype(int),
                                     scoring="roc_auc", n_repeats=5, random_state=0)
    importance = sorted([{"feature": f, "label": FEATURE_NO.get(f, f), "imp": float(v)}
                         for f, v in zip(FEATURES, imp.importances_mean)], key=lambda x: -x["imp"]) if imp else []

    # ---- dagens signaler: modell trent på ALT med fasit
    full_lab = panel.dropna(subset=["fwd_ex"])
    full_lab = full_lab[full_lab["tradeable"]]
    final_model = make_model().fit(full_lab[FEATURES], (full_lab["fwd_ex"] > 0).astype(int))
    today = panel["date"].max()
    latest = panel[panel["date"] == today].copy()
    latest["p"] = final_model.predict_proba(latest[FEATURES])[:, 1]
    show_cols = ["contract_rel_mcap_qtd", "contract_react_90", "n_contract_90", "insider_net_90",
                 "dist_sma200", "days_to_report", "ret_20", "dd_252"]
    signals_today = [{"ticker": r["ticker"], "name": name_of.get(r["ticker"], r["ticker"]), "p": r["p"],
                      "tradeable": bool(r["tradeable"]), "close": r["close"],
                      **{c: r[c] for c in show_cols}}
                     for _, r in latest.sort_values("p", ascending=False).head(25).iterrows()]

    live = None
    if not args.no_live:
        live = update_live(os.path.join(args.out, "paper_live.json"), latest, px, cal)

    # ---- historikk per aksje siste ~9 mnd (score + kurs + meldinger) til dashboardet
    hist_start = end - pd.Timedelta(days=270)
    ph = preds[preds["date"] >= hist_start]
    lp = latest[["date", "ticker", "p", "close"]]
    ph = pd.concat([ph[["date", "ticker", "p", "close"]], lp]).drop_duplicates(["date", "ticker"], keep="last")
    ticker_hist = {}
    for t, g in ph.groupby("ticker"):
        g = g.sort_values("date")
        ev = news[(news["ticker"] == t) & (news["sday"] >= hist_start)
                  & news["kind"].isin(["contract", "insider", "report", "mna", "guidance", "buyback", "financing"])]
        ticker_hist[t] = {"name": name_of.get(t, t), "d": [str(x.date()) for x in g["date"]],
                          "c": [round(float(x), 3) for x in g["close"]], "p": [round(float(x), 4) for x in g["p"]],
                          "ev": [{"d": str(r["sday"].date()), "k": r["kind"], "t": r["title"][:140],
                                  "amt": r["amount"], "dir": int(r["ins_dir"])} for _, r in ev.iterrows()]}

    step = max(1, len(eq) // 600)
    curve_idx = list(range(0, len(eq), step)) + ([len(eq) - 1] if (len(eq) - 1) % step else [])
    results = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "data": {"tickers": len(tickers), "news": int(len(news)),
                 "news_by_kind": news["kind"].value_counts().to_dict(),
                 "first_date": str(cal[0].date()), "last_date": str(cal[-1].date()),
                 "test_start": str(start.date()), "test_end": str(end.date()),
                 "repaired_jumps": len(px["repaired"])},
        "rules": {"hold_days": HOLD, "slots": SLOTS, "max_new_per_day": MAX_NEW_PER_DAY, "min_prob": MIN_PROB,
                  "cost_per_side": COST_PER_SIDE, "min_turnover": MIN_TURNOVER, "start_capital": START_CAPITAL,
                  "n_random": N_RANDOM},
        "metrics": {"strategy": m_strat, "benchmark": m_bench, "rule": m_rule,
                    "random_median_total": float(np.median(finals) / START_CAPITAL - 1),
                    "random_p": p_random},
        "curve": {"d": [str(eq.index[i].date()) for i in curve_idx],
                  "strategy": [eq.iloc[i] for i in curve_idx],
                  "bench": [bench_eq.iloc[i] for i in curve_idx],
                  "rule": [eq_rule.reindex(eq.index).ffill().iloc[i] for i in curve_idx],
                  "rand_p5": [float(np.percentile(rand_curves[:, i], 5)) for i in curve_idx],
                  "rand_p50": [float(np.percentile(rand_curves[:, i], 50)) for i in curve_idx],
                  "rand_p95": [float(np.percentile(rand_curves[:, i], 95)) for i in curve_idx]},
        "quality": {"auc": auc, "auc_by_year": auc_year, "auc_by_month": fold_auc,
                    "ic_mean": float(ic.mean()), "ic_t": float(ic.mean() / ic.std() * math.sqrt(len(ic))),
                    "deciles": deciles.to_dict(orient="records"), "base_rate": float((lab["fwd_ex"] > 0).mean())},
        "importance": importance[:20],
        "trades": sorted(trades, key=lambda t: t["entry_date"], reverse=True),
        "trades_rule": sorted(trades_rule, key=lambda t: t["entry_date"], reverse=True)[:200],
        "signals_today": {"date": str(today.date()), "rows": signals_today},
        "live": live,
        "names": name_of,
        "ticker_hist": ticker_hist,
        "case": args.case,
        "feature_labels": FEATURE_NO,
    }
    for t in results["trades"]:
        t["name"] = name_of.get(t["ticker"], t["ticker"])
    with open(os.path.join(args.out, "results.json"), "w", encoding="utf-8") as f:
        json.dump(clean(results), f, ensure_ascii=False, separators=(",", ":"))
    write_report(os.path.join(args.out, "report.md"), clean(results))
    print(json.dumps(clean(results["metrics"]), indent=1))
    print("AUC", round(auc, 4), "IC", round(float(ic.mean()), 4))


def pct(x):
    return "–" if x is None else f"{x * 100:+.1f} %"


def write_report(path, r):
    m = r["metrics"]
    s, b, ru = m["strategy"], m["benchmark"], m["rule"]
    lines = [
        "# Nyhets-ML: paper trading-backtest", "",
        f"Generert {r['generated'][:16]} UTC · {r['data']['tickers']} aksjer · {r['data']['news']} børsmeldinger",
        f"Testperiode (modellen har aldri sett disse dagene): {r['data']['test_start']} → {r['data']['test_end']}", "",
        "| | ML-strategi | Regel (KOG-mønster) | OSEBX |", "|---|---|---|---|",
        f"| Total avkastning | {pct(s.get('total_return'))} | {pct(ru.get('total_return'))} | {pct(b.get('total_return'))} |",
        f"| Årlig (CAGR) | {pct(s.get('cagr'))} | {pct(ru.get('cagr'))} | {pct(b.get('cagr'))} |",
        f"| Største fall | {pct(s.get('max_dd'))} | {pct(ru.get('max_dd'))} | {pct(b.get('max_dd'))} |",
        f"| Sharpe | {s.get('sharpe') or 0:.2f} | {ru.get('sharpe') or 0:.2f} | {b.get('sharpe') or 0:.2f} |",
        f"| Handler | {s.get('n_trades')} | {ru.get('n_trades')} | – |",
        f"| Treffrate | {pct(s.get('hit_rate'))} | {pct(ru.get('hit_rate'))} | – |", "",
        f"**Tilfeldighetstest:** {m['random_p'] * 100:.1f} % av {r['rules']['n_random']} tilfeldige porteføljer "
        f"med samme handelsfrekvens endte like godt eller bedre (median tilfeldig: {pct(m['random_median_total'])}).", "",
        f"**AUC ut-av-utvalget:** {r['quality']['auc']:.3f} (0,50 = mynt­kast) · "
        f"**IC:** {r['quality']['ic_mean']:.3f} (t = {r['quality']['ic_t']:.1f})", "",
        "## Viktigste signaler (permutasjon, siste 9 mnd)", "",
    ]
    for it in r["importance"][:10]:
        lines.append(f"- {it['label']}: {it['imp']:+.4f}")
    lines += ["", "## Begrensninger", "",
              "- Universet er dagens watchlist (overlevelsesskjevhet: aksjer som gikk konkurs er ikke med).",
              "- Markedsverdi bakover i tid bruker dagens aksjeantall.",
              "- Kontraktsverdier tolkes fra tekst med faste valutakurser - grovt.",
              "- Kvartalsrapport-dato er estimert (~63 handelsdager etter forrige).",
              "- Dette er forskning, ikke investeringsråd."]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
