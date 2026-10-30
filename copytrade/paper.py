#!/usr/bin/env python3
"""
Copy-trading på papir: kopier innsidekjøp (+ følg stjernebrukere i forumet)
==========================================================================
Strategi 1 - INNSIDEKJØP (backtest fra 2020 + live paper)
    Signal:  en primærinnsider kjøper aksjer i markedet (ikke spareprogram,
             opsjoner, honorar, selskapets egne aksjer osv.)
    Inngang: åpningskurs første handelsdag ETTER at meldingen ble publisert
             (før 09:00 Oslo-tid -> samme dags åpning). Ingen titting fremover.
    Utgang:  åpningskurs H handelsdager senere.
    Størrelse: fast 10 000 kr per handel, ingen kurtasje/spread trukket fra.
    Måles mot OSEBX over nøyaktig de samme dagene (meravkastning).

    HOVEDSTRATEGIEN er låst på forhånd, før resultatene ble sett:
        CEO / CFO / styreleder, kjøp >= 500 000 kr, hold 20 handelsdager.
    De andre variantene vises bare til sammenligning. Når man tester mange
    varianter, vil noen se gode ut av ren flaks - ikke bytt til "vinneren".

Strategi 2 - STJERNEBRUKERE (kun live, ingen backtest)
    Signal:  en bruker med 3 stjerner på Nordnet Social skriver et positivt
             innlegg (sentiment >= 0.3, lokal modell eller Claude) om en aksje i watchlisten.
    Backtest er umulig uten look-ahead: stjernene vi har er DAGENS, og en
    bruker som har 3 stjerner nå hadde ikke nødvendigvis det for et år siden.
    Derfor bare forover-paper-trading fra første kjøring.

Ledger (nordnet_data/copytrade/ledger.json) husker når hvert signal ble sett
FØRSTE gang. "Ekte live"-tallene bruker kun signaler sett etter oppstart, så
de kan ikke være pyntet i ettertid.

Output: nordnet_data/copytrade/results.json (leses av dashboard.py)
"""

import json
import math
import os
import sys
from datetime import datetime, time as dtime, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from news_ml.common import BENCHMARK, load_universe  # noqa: E402
from copytrade.insiders import load_trades  # noqa: E402

OSLO = ZoneInfo("Europe/Oslo")
OPEN = dtime(9, 0)
DATA_DIR = os.path.join(ROOT, "nordnet_data")
OUT_DIR = os.path.join(DATA_DIR, "copytrade")
PRICE_CSV = os.path.join(DATA_DIR, "news_ml_prices", "prices.csv")
LEDGER = os.path.join(OUT_DIR, "ledger.json")
STAKE = 10_000

SENIOR = {"CEO", "CFO", "Styreleder"}
INSIDER_VARIANTS = {
    "senior_500k": {"label": "CEO/CFO/styreleder, ≥ 500k", "roles": SENIOR, "min_value": 500_000},
    "alle_100k": {"label": "Alle innsidere, ≥ 100k", "roles": None, "min_value": 100_000},
    "alle_1m": {"label": "Alle innsidere, ≥ 1 mill", "roles": None, "min_value": 1_000_000},
    "klynge": {"label": "Klynge: ≥ 2 innsidere kjøper innen 10 d", "roles": None, "min_value": 50_000,
               "cluster": 2},
}
HOLDS = [5, 20, 60]
MAIN = ("senior_500k", 20)
STAR_MIN_SENT = 0.3
STAR_HOLD = 20


# ------------------------------------------------------------------ kurser
def load_prices(path=None):
    px = pd.read_csv(path or PRICE_CSV, parse_dates=["date"])
    px = px.dropna(subset=["open", "close"])
    px = px[(px["close"] > 0) & (px["open"] > 0)]
    if "adj_close" not in px:
        px["adj_close"] = px["close"]
    px["adj_close"] = px["adj_close"].fillna(px["close"])
    # Utbyttejustert åpningskurs: samme justeringsfaktor som sluttkursen den dagen
    px["adj_open"] = px["open"] * px["adj_close"] / px["close"]
    opn = px.pivot_table(index="date", columns="ticker", values="adj_open", aggfunc="last").sort_index()
    cls = px.pivot_table(index="date", columns="ticker", values="close", aggfunc="last").sort_index()
    stocks = cls.drop(columns=[BENCHMARK], errors="ignore")
    cal = stocks.index[stocks.notna().sum(axis=1) >= max(1, 0.3 * stocks.shape[1])]
    opn, cls = opn.reindex(cal), cls.reindex(cal)
    if BENCHMARK in opn:
        opn[BENCHMARK] = opn[BENCHMARK].ffill(limit=3)
    return opn, cls


def entry_index(cal, published_iso):
    """Index i kalenderen for første åpning vi faktisk kunne handlet på."""
    ts = pd.Timestamp(published_iso)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    local = ts.tz_convert(OSLO)
    day = pd.Timestamp(local.date())
    i = int(cal.searchsorted(day))  # første handelsdag >= publiseringsdag
    if i < len(cal) and cal[i] == day and local.time() >= OPEN:
        i += 1  # publisert etter åpning -> neste dags åpning
    return i


def fix_value(t, cls_col, cal):
    """Sjekk innsiderens kurs mot faktisk sluttkurs og regn verdi i NOK på nytt ved behov."""
    i = entry_index(cal, t["published"]) - 1
    i = min(max(i, 0), len(cal) - 1)
    window = cls_col.iloc[max(0, i - 5):i + 1].dropna()
    if window.empty or not t["shares"]:
        return t["value_nok"]
    mkt = float(window.iloc[-1])
    p = t["price"]
    if p:
        best = min((p, p * 1000, p / 1000), key=lambda c: abs(math.log(c / mkt)))
        if abs(best / mkt - 1) <= 0.35:
            return t["shares"] * best  # (grovt i NOK - de aller fleste er NOK-noterte)
    return t["shares"] * mkt


# ------------------------------------------------------------------ signaler
def insider_signals(opn, cls, issuer_to_ticker):
    cal = opn.index
    rows = []
    for t in load_trades():
        if t["direction"] != 1 or t["noise"]:
            continue
        tk = issuer_to_ticker.get(t["issuer"])
        if not tk or tk not in cls:
            continue
        value = fix_value(t, cls[tk], cal)
        if not value:
            continue
        rows.append({**t, "ticker": tk, "value_nok": round(value)})
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["pub_ts"] = pd.to_datetime(df["published"], utc=True)
    df = df.sort_values("pub_ts").reset_index(drop=True)
    # Antall ulike kjøpsmeldinger i samme aksje siste 10 dager (inkl. denne) - for klynge-varianten
    df["cluster_n"] = [
        int(((df["ticker"] == r.ticker) & (df["pub_ts"] <= r.pub_ts)
             & (df["pub_ts"] > r.pub_ts - pd.Timedelta(days=10))).sum())
        for r in df.itertuples()
    ]
    return df


def run_trades(sig, opn, hold):
    cal = opn.index
    last = len(cal) - 1
    bench = opn[BENCHMARK] if BENCHMARK in opn else None
    out, busy_until = [], {}
    for r in sig.itertuples():
        i = entry_index(cal, r.published)
        if busy_until.get(r.ticker, -1) >= i:
            continue  # har allerede en åpen posisjon i aksjen fra et tidligere signal
        rec = {"id": r.id, "published": r.published, "ticker": r.ticker, "issuer_name": r.issuer_name,
               "role": r.role, "value_nok": int(r.value_nok), "title": r.title}
        if i > last:
            out.append({**rec, "status": "venter", "entry_date": None})
            continue
        e = opn[r.ticker].iloc[i]
        if not np.isfinite(e):
            continue
        j = i + hold
        status = "lukket" if j <= last else "åpen"
        j = min(j, last)
        x = opn[r.ticker].iloc[j]
        if not np.isfinite(x):
            x = opn[r.ticker].iloc[i:j + 1].dropna().iloc[-1]
        ret = x / e - 1
        bret = None
        if bench is not None and np.isfinite(bench.iloc[i]) and np.isfinite(bench.iloc[j]):
            bret = bench.iloc[j] / bench.iloc[i] - 1
        busy_until[r.ticker] = i + hold
        out.append({**rec, "status": status, "entry_date": str(cal[i].date()), "exit_date": str(cal[j].date()),
                    "days_held": j - i, "ret": float(ret), "bench_ret": None if bret is None else float(bret),
                    "excess": None if bret is None else float(ret - bret), "pnl": float(STAKE * ret)})
    return out


def stats(trades):
    closed = [t for t in trades if t["status"] == "lukket"]
    ex = np.array([t["excess"] for t in closed if t["excess"] is not None])
    rt = np.array([t["ret"] for t in closed])
    if len(rt) == 0:
        return {"n": 0}
    tstat = float(ex.mean() / (ex.std(ddof=1) / math.sqrt(len(ex)))) if len(ex) > 2 and ex.std() > 0 else None
    return {
        "n": len(closed), "n_open": sum(t["status"] == "åpen" for t in trades),
        "avg_ret": float(rt.mean()), "median_ret": float(np.median(rt)), "hit_rate": float((rt > 0).mean()),
        "avg_excess": float(ex.mean()) if len(ex) else None,
        "beat_bench": float((ex > 0).mean()) if len(ex) else None,
        "t_stat": tstat, "total_pnl": float(sum(t["pnl"] for t in closed)),
    }


def by_year(trades):
    out = {}
    for t in trades:
        if t["status"] != "lukket" or t["excess"] is None:
            continue
        out.setdefault(t["entry_date"][:4], []).append(t["excess"])
    return {y: {"n": len(v), "avg_excess": float(np.mean(v))} for y, v in sorted(out.items())}


def equity_curve(trades, cal):
    """Kumulativ P&L (kr) per handelsdag, 10k per handel, uten rentes rente."""
    pnl = pd.Series(0.0, index=cal)
    for t in trades:
        if t["status"] == "lukket":
            pnl[pd.Timestamp(t["exit_date"])] += t["pnl"]
    cum = pnl.cumsum()
    weekly = cum.resample("W").last().dropna()
    return [[str(d.date()), round(float(v))] for d, v in weekly.items()]


# ------------------------------------------------------------------ stjernebrukere
def star_signals(universe_slugs):
    prof_path = os.path.join(OUT_DIR, "profiles.json")
    if not os.path.exists(prof_path):
        return [], {}
    profiles = json.load(open(prof_path, encoding="utf-8"))
    starred = {u: p for u, p in profiles.items() if (p.get("stars") or 0) >= 2}
    scores = {}
    sp = os.path.join(DATA_DIR, "sentiment", "scores.jsonl")
    if os.path.exists(sp):
        for line in open(sp, encoding="utf-8"):
            if line.strip():
                s = json.loads(line)
                scores[s["key"]] = s
    from archive_posts import iter_archive
    posts = []
    for p in iter_archive(DATA_DIR):
        user = (p.get("profile_url") or "").rstrip("/").rsplit("/", 1)[-1]
        if user not in starred:
            continue
        sc = scores.get(p["key"], {})
        claude_scored = sc.get("model", "regel") != "regel"
        posts.append({
            "key": p["key"], "user": user, "stars": starred[user]["stars"], "slug": p.get("slug"),
            "posted_at": p.get("posted_at") or p.get("scraped_at"), "text": (p.get("text") or "")[:280],
            "sentiment": sc.get("sentiment") if claude_scored else None,
            "relevance": sc.get("relevance") if claude_scored else None,
            "in_watchlist": p.get("slug") in universe_slugs,
        })
    posts.sort(key=lambda r: r["posted_at"] or "", reverse=True)
    summary = {"profiles_checked": sum(1 for p in profiles.values() if p.get("checked_at")),
               "three_star": sum(1 for p in profiles.values() if p.get("stars") == 3),
               "two_star": sum(1 for p in profiles.values() if p.get("stars") == 2),
               "top_users": sorted(
                   [{"user": u, "stars": p["stars"], "followers": p.get("followers"),
                     "forum_posts": p.get("forum_posts"), "url": p.get("url")} for u, p in starred.items()],
                   key=lambda r: (-r["stars"], -(r["followers"] or 0)))[:40]}
    return posts, summary


# ------------------------------------------------------------------ ledger
def load_ledger():
    if os.path.exists(LEDGER):
        return json.load(open(LEDGER, encoding="utf-8"))
    return {"started_at": datetime.now(timezone.utc).isoformat(), "first_seen": {}}


def mark_seen(ledger, key):
    ledger["first_seen"].setdefault(str(key), datetime.now(timezone.utc).isoformat())
    return ledger["first_seen"][str(key)]


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    opn, cls = load_prices()
    cal = opn.index
    uni = load_universe()
    issuer_to_ticker = {u["issuer"]: u["ticker"] for u in uni}
    slug_to_ticker = {u["slug"]: u["ticker"] for u in uni}
    ledger = load_ledger()

    sig = insider_signals(opn, cls, issuer_to_ticker)
    variants = {}
    main_trades = []
    for key, v in INSIDER_VARIANTS.items():
        chosen = sig.iloc[0:0] if sig.empty else sig[
            (sig["value_nok"] >= v["min_value"])
            & (sig["role"].isin(v["roles"]) if v.get("roles") else True)
            & (sig["cluster_n"] >= v.get("cluster", 1))]
        for h in HOLDS:
            tr = run_trades(chosen, opn, h)
            variants[f"{key}|{h}"] = {"label": v["label"], "hold": h, **stats(tr)}
            if (key, h) == MAIN:
                main_trades = tr

    # Ekte forover-resultat: bare signaler som ble sett første gang ETTER oppstart
    for t in main_trades:
        t["first_seen"] = mark_seen(ledger, f"insider:{t['id']}")
    live = [t for t in main_trades if t["first_seen"] >= ledger["started_at"]
            and (t["published"] or "") >= ledger["started_at"][:10]]

    # Stjernebrukere: forover-paper-trading
    star_posts, star_summary = star_signals(set(slug_to_ticker))
    star_trades = []
    star_sig = [p for p in star_posts if p["stars"] == 3 and p["in_watchlist"]
                and p["sentiment"] is not None and p["sentiment"] >= STAR_MIN_SENT]
    if star_sig:
        sdf = pd.DataFrame([{"id": f"star:{p['key']}", "published": p["posted_at"],
                             "ticker": slug_to_ticker[p["slug"]], "issuer_name": p["slug"],
                             "role": f"@{p['user']}", "value_nok": 0, "title": p["text"][:120]}
                            for p in star_sig if slug_to_ticker.get(p["slug"]) in opn])
        if not sdf.empty:
            sdf["first_seen"] = [mark_seen(ledger, i) for i in sdf["id"]]
            # Bare innlegg skrevet ETTER oppstart - ellers ville hele forum-historikken
            # telt som "live" ved første kjøring.
            sdf = sdf[(sdf["first_seen"] >= ledger["started_at"])
                      & (sdf["published"] >= ledger["started_at"])].sort_values("published")
            star_trades = run_trades(sdf, opn, STAR_HOLD)

    results = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "price_last_date": str(cal[-1].date()) if len(cal) else None,
        "paper_started_at": ledger["started_at"],
        "main_key": f"{MAIN[0]}|{MAIN[1]}",
        "n_insider_buys_parsed": int(len(sig)),
        "variants": variants,
        "main": {"stats": stats(main_trades), "by_year": by_year(main_trades),
                 "equity": equity_curve(main_trades, cal),
                 "open": [t for t in main_trades if t["status"] in ("åpen", "venter")][-30:],
                 "recent_closed": [t for t in main_trades if t["status"] == "lukket"][-30:][::-1],
                 "live_stats": stats(live), "live_trades": live[-30:][::-1]},
        "stars": {**star_summary, "recent_posts": star_posts[:40], "trades": star_trades[::-1][:30],
                  "stats": stats(star_trades)},
    }
    with open(os.path.join(OUT_DIR, "results.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1, default=str)
    with open(LEDGER, "w", encoding="utf-8") as f:
        json.dump(ledger, f, indent=1)
    m = results["main"]["stats"]
    print(f"Hovedstrategi ({MAIN}): {m}")
    for k, v in variants.items():
        print(f"  {k:18s} n={v.get('n', 0):4d}  snitt={v.get('avg_ret', 0) or 0:+.2%}  "
              f"mer={v.get('avg_excess') or 0:+.2%}  t={v.get('t_stat') or 0:.2f}")


if __name__ == "__main__":
    main()
