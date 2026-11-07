#!/usr/bin/env python3
"""
Testbenken (Fase 0)
===================
Én og samme test for alle signalideer:

    inn:  signaler med ticker, publiseringstidspunkt og retning (+1 kjøp, -1 short)
    ut:   meravkastning mot OSEBX etter kostnader etter 1/5/20/60 handelsdager,
          treffrate, antall hendelser, t-verdi og placebo-p, + en dom per horisont.

Regler som ikke kan skrus av:
  * Inngang på første åpning ETTER publisering (før 09:00 Oslo -> samme dags åpning),
    samme regel som copytrade/paper.py (entry_index importeres derfra).
  * Kostnader trekkes alltid fra (research/costs.py, satser i research/config.json).
  * Holdout: hendelser fra holdout_start og senere er låst. Vanlige kjøringer ser dem
    ikke, og handler som ville gått inn i holdout-perioden tas ut. En idé får røre
    holdout-perioden én gang (use_holdout=True); andre gang stopper testbenken.
  * Hver kjøring skrives til nordnet_data/research/test_log.jsonl. Antall ulike tester K
    (ulike spec-hasher) styrer kravet til t-verdi: max(min_t, Bonferroni-z for K tester).
    Jo flere varianter man prøver, jo strengere blir kravet for alle.

To mål på avkastning:
  * Reaksjon CAR[0,1]: slutt(t0-1) -> slutt(t0+1) minus OSEBX, der t0 er publiseringsdagen
    hvis meldingen kom før 16:20 Oslo-tid, ellers neste handelsdag. Klassisk hendelsesstudie,
    IKKE handlebar (inkluderer kursbevegelsen før vi rakk å kjøpe). Brukes til Gate 0.
  * Handlebar: åpning(inngang) -> åpning(inngang + h) minus OSEBX over de samme dagene,
    minus kostnader. Det er dette dommen bygger på.

t-verdien er klyngejustert: hendelser grupperes i blokker på max(5, h) handelsdager,
fordi mange hendelser samme uke (eller overlappende hold) ikke er uavhengige.
Placebo: samme aksjer, tilfeldige inngangsdager i samme periode, samme kostnader.
"""

import argparse
import hashlib
import json
import math
import os
import sys
from datetime import datetime, time as dtime, timezone
from statistics import NormalDist

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from copytrade.paper import OSLO, entry_index  # noqa: E402  (én definisjon av inngangsregelen)
from research import costs as C  # noqa: E402
from research.data import DATA_DIR, Panel, load_config, load_panel  # noqa: E402

OUT_ROOT = os.environ.get("RESEARCH_OUT", os.path.join(DATA_DIR, "research"))
CLOSE = dtime(16, 20)   # Oslo Børs: sluttauksjon ca. 16:20
DATE_ONLY_TIME = "23:59"  # signaler med bare dato antas publisert etter børsslutt (konservativt)


class HoldoutUsed(RuntimeError):
    pass


# ------------------------------------------------------------------ tidsregler
def normalize_published(value):
    """Til UTC-ISO. Bare dato -> 23:59 Oslo-tid samme dag (kan ikke handles før neste åpning)."""
    s = str(value).strip()
    if len(s) <= 10:
        ts = pd.Timestamp(f"{s} {DATE_ONLY_TIME}").tz_localize(OSLO)
    else:
        ts = pd.Timestamp(s)
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
    return ts.tz_convert("UTC").isoformat()


def reaction_index(cal, published_iso):
    """t0 for hendelsesstudien: publiseringsdagen hvis før 16:20 Oslo-tid, ellers neste handelsdag."""
    ts = pd.Timestamp(published_iso)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    local = ts.tz_convert(OSLO)
    day = pd.Timestamp(local.date())
    i = int(cal.searchsorted(day))
    if i < len(cal) and cal[i] == day and local.time() >= CLOSE:
        i += 1
    return i


# ------------------------------------------------------------------ statistikk
def required_t(k, min_t=3.0, alpha=0.05):
    """Krav til |t| når K ulike tester er kjørt: max(min_t, tosidig Bonferroni)."""
    k = max(int(k), 1)
    return max(float(min_t), NormalDist().inv_cdf(1 - alpha / (2 * k)))


def clustered_t(x, groups):
    """t for snittet med klyngerobust standardfeil (summer av avvik per klynge)."""
    x = np.asarray(x, dtype=float)
    n = len(x)
    if n < 3:
        return None
    e = x - x.mean()
    s = pd.Series(e).groupby(np.asarray(groups)).sum().to_numpy()
    g = len(s)
    if g < 2:
        return None
    var = (s ** 2).sum() / n ** 2 * g / (g - 1)
    if not var > 0:
        return None
    return float(x.mean() / math.sqrt(var))


def summarize(x, groups):
    x = np.asarray(x, dtype=float)
    n = len(x)
    if n == 0:
        return {"n": 0}
    sd = float(x.std(ddof=1)) if n > 1 else None
    t = float(x.mean() / (sd / math.sqrt(n))) if sd else None
    return {"n": n, "mean": float(x.mean()), "median": float(np.median(x)), "hit_rate": float((x > 0).mean()),
            "std": sd, "t": t, "t_cluster": clustered_t(x, groups), "n_clusters": int(len(set(np.asarray(groups))))}


# ------------------------------------------------------------------ spec, logg og holdout
def spec_hash(name, params, horizons):
    blob = json.dumps({"name": name, "params": params or {}, "horizons": list(horizons)}, sort_keys=True,
                      ensure_ascii=False, default=str)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:12]


def read_log(out_root):
    path = os.path.join(out_root, "test_log.jsonl")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def distinct_tests(log_rows, extra_hash=None):
    hashes = {r["spec_hash"] for r in log_rows if r.get("mode", "build") == "build"}
    if extra_hash:
        hashes.add(extra_hash)
    return len(hashes)


def append_log(out_root, row):
    os.makedirs(out_root, exist_ok=True)
    with open(os.path.join(out_root, "test_log.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def _lock_path(out_root):
    return os.path.join(out_root, "holdout_lock.json")


def check_and_lock_holdout(out_root, name, shash, force=False):
    path = _lock_path(out_root)
    lock = {"used": []}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            lock = json.load(f)
    prior = [u for u in lock["used"] if u["name"] == name]
    if prior and not force:
        raise HoldoutUsed(f"'{name}' har allerede brukt holdout-perioden ({prior[0]['at']}). "
                          "En idé får bare ett forsøk mot holdout - lag en ny idé i stedet for å justere denne.")
    lock["used"].append({"name": name, "spec_hash": shash, "at": datetime.now(timezone.utc).isoformat(),
                         "forced": bool(prior)})
    os.makedirs(out_root, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(lock, f, ensure_ascii=False, indent=1)


# ------------------------------------------------------------------ kjernen
def prepare_signals(signals, panel):
    """Signaler -> DataFrame med kolonneindeks, inngangsindeks og t0. Returnerer (df, dropped)."""
    df = pd.DataFrame(signals).copy()
    if "direction" not in df:
        df["direction"] = 1
    if "id" not in df:
        df["id"] = np.arange(len(df)).astype(str)
    dropped = {}
    col_of = {t: k for k, t in enumerate(panel.open.columns)}
    df["col"] = df["ticker"].map(col_of)
    dropped["ukjent_ticker"] = int(df["col"].isna().sum())
    df = df[df["col"].notna()].copy()
    df["col"] = df["col"].astype(int)
    df["direction"] = df["direction"].astype(int)
    bad_dir = ~df["direction"].isin([1, -1])
    dropped["ugyldig_retning"] = int(bad_dir.sum())
    df = df[~bad_dir].copy()
    df["published"] = [normalize_published(p) for p in df["published"]]
    cal = panel.cal
    df["i"] = [entry_index(cal, p) for p in df["published"]]
    df["t0"] = [reaction_index(cal, p) for p in df["published"]]
    pub_day = pd.to_datetime(df["published"], utc=True, format="ISO8601").dt.tz_convert(OSLO).dt.tz_localize(None).dt.normalize()
    before = (pub_day < cal[0]).to_numpy() if len(cal) else np.ones(len(df), dtype=bool)
    dropped["før_kurshistorikken"] = int(before.sum())
    after = df["i"].to_numpy() >= len(cal)
    dropped["ikke_handlet_ennå"] = int((after & ~before).sum())
    df = df[~before & ~after].copy()
    n0 = len(df)
    df = df.sort_values("published").drop_duplicates(["ticker", "i", "direction"], keep="first")
    dropped["duplikat_samme_aksje_og_dag"] = int(n0 - len(df))
    return df.reset_index(drop=True), dropped


def _exit_prices(O, i, j, c):
    x = O[j, c].copy()
    for k in np.flatnonzero(~np.isfinite(x)):
        seg = O[i[k]:j[k] + 1, c[k]]
        seg = seg[np.isfinite(seg)]
        x[k] = seg[-1] if len(seg) else np.nan
    return x


def tradable_returns(df, panel, h, costs, lo, hi):
    """Handlebar meravkastning for hold h. Bare handler med inngang >= lo og utgang < hi."""
    O = panel.open.to_numpy(dtype=float)
    B = panel.bench_open.to_numpy(dtype=float)
    HS = panel.half_spread(costs).to_numpy(dtype=float)
    i = df["i"].to_numpy()
    j = i + h
    ok = (i >= lo) & (j < hi)
    i, j, c, d = i[ok], j[ok], df["col"].to_numpy()[ok], df["direction"].to_numpy()[ok]
    e = O[i, c]
    x = _exit_prices(O, i, j, c)
    bi, bj = B[i], B[j]
    good = np.isfinite(e) & np.isfinite(x) & np.isfinite(bi) & np.isfinite(bj)
    i, j, c, d, e, x, bi, bj = (a[good] for a in (i, j, c, d, e, x, bi, bj))
    gross = x / e - 1
    bret = bj / bi - 1
    signed = d * (gross - bret)
    hs_in = np.where(i >= 1, HS[np.maximum(i - 1, 0), c], np.nan)
    hs_out = HS[j - 1, c]
    cost = C.round_trip_cost(hs_in, hs_out, costs)
    idx = np.flatnonzero(ok)[good]
    return {"row": idx, "i": i, "j": j, "gross": gross, "bench": bret, "excess": signed, "cost": cost,
            "net": signed - cost, "hs_in": hs_in, "direction": d,
            "ticker": np.asarray(panel.open.columns)[c] if len(c) else np.array([], dtype=object)}


def placebo(df_rows, panel, h, costs, lo, hi, draws, rng):
    """Snitt-netto for tilfeldige inngangsdager i de samme aksjene, `draws` ganger."""
    O = panel.open.to_numpy(dtype=float)
    B = panel.bench_open.to_numpy(dtype=float)
    HS = panel.half_spread(costs).to_numpy(dtype=float)
    T = len(panel.cal)
    c_ev = df_rows["col"].to_numpy()
    d_ev = df_rows["direction"].to_numpy()
    if len(c_ev) == 0:
        return None
    lo_i, hi_i = max(lo, int(df_rows["i"].min())), min(hi - h, int(df_rows["i"].max()) + 1)
    if hi_i - lo_i < 5:
        return None
    ii = np.arange(lo_i, hi_i)
    picks = np.empty((len(c_ev), draws), dtype=int)
    keep = np.ones(len(c_ev), dtype=bool)
    cache = {}
    for k, c in enumerate(c_ev):
        if c not in cache:
            v = (np.isfinite(O[ii, c]) & np.isfinite(O[np.minimum(ii + h, T - 1), c])
                 & np.isfinite(B[ii]) & np.isfinite(B[np.minimum(ii + h, T - 1)]))
            cache[c] = ii[v]
        pool = cache[c]
        if len(pool) == 0:
            keep[k] = False
            continue
        picks[k] = rng.choice(pool, size=draws)
    if keep.sum() < 3:
        return None
    picks, c_ev, d_ev = picks[keep], c_ev[keep], d_ev[keep]
    cc = np.repeat(c_ev[:, None], draws, axis=1)
    gross = O[picks + h, cc] / O[picks, cc] - 1
    bret = B[picks + h] / B[picks] - 1
    hs_in = np.where(picks >= 1, HS[np.maximum(picks - 1, 0), cc], np.nan)
    cost = C.round_trip_cost(hs_in, HS[picks + h - 1, cc], costs)
    net = d_ev[:, None] * (gross - bret) - cost
    return net.mean(axis=0)


def reaction_car(df, panel, lo, hi, a=0, b=1):
    """CAR[a,b] rundt t0 med sluttkurser, markedsjustert. Bare hendelser med hele vinduet i [lo, hi)."""
    Cl = panel.close.to_numpy(dtype=float)
    Bc = panel.bench_close.to_numpy(dtype=float)
    t0 = df["t0"].to_numpy()
    s, e = t0 + a - 1, t0 + b
    ok = (s >= max(lo, 0)) & (e < hi) & (t0 < len(panel.cal))
    c, d, s, e, t0 = df["col"].to_numpy()[ok], df["direction"].to_numpy()[ok], s[ok], e[ok], t0[ok]
    r = Cl[e, c] / Cl[s, c] - 1
    rb = Bc[e] / Bc[s] - 1
    good = np.isfinite(r) & np.isfinite(rb)
    return d[good] * (r[good] - rb[good]), t0[good]


def run_event_study(signals, name, params=None, panel=None, config=None, use_holdout=False, force=False,
                    out_root=None, log=True, write=True, save_events=False):
    """Kjør hele testen og returner resultat-dict. Skriver rapport og logg under out_root/<name>/."""
    cfg = config or load_config()
    costs = cfg["costs"]
    horizons = [int(h) for h in cfg["horizons"]]
    out_root = out_root or OUT_ROOT
    panel = panel if panel is not None else load_panel()
    assert isinstance(panel, Panel)
    shash = spec_hash(name, params, horizons)
    mode = "holdout" if use_holdout else "build"
    if use_holdout:
        check_and_lock_holdout(out_root, name, shash, force=force)

    df, dropped = prepare_signals(signals, panel)
    n_in = len(pd.DataFrame(signals))
    cal = panel.cal
    T = len(cal)
    h_idx = int(cal.searchsorted(pd.Timestamp(cfg["holdout_start"])))
    lo, hi = (h_idx, T) if use_holdout else (0, h_idx)

    log_rows = read_log(out_root)
    K = distinct_tests(log_rows, shash)
    req_t = float(cfg.get("holdout_min_t", 2.0)) if use_holdout else required_t(K, cfg["min_t"], cfg["alpha"])

    rng = np.random.default_rng(int(cfg.get("seed", 0)))
    res = {"name": name, "spec_hash": shash, "mode": mode, "generated_at": datetime.now(timezone.utc).isoformat(),
           "params": params or {}, "n_signals_in": n_in, "dropped": dropped, "K_distinct_tests": K,
           "required_t": req_t, "holdout_start": cfg["holdout_start"], "costs": C.describe(costs),
           "price_first_date": str(cal[0].date()) if T else None,
           "price_last_date": str(cal[-1].date()) if T else None, "horizons": {}}

    car, t0 = reaction_car(df, panel, lo, hi, 0, 1)
    pre, t0p = reaction_car(df, panel, lo, hi, -5, -1)
    res["reaction"] = {"car_0_1": summarize(car, t0 // 5), "car_m5_m1": summarize(pre, t0p // 5)}

    events = {}
    any_pass = False
    for h in horizons:
        tr = tradable_returns(df, panel, h, costs, lo, hi)
        n = len(tr["net"])
        groups = tr["i"] // max(5, h)
        st_net = summarize(tr["net"], groups)
        st_gross = summarize(tr["excess"], groups)
        pm = placebo(df.iloc[tr["row"]], panel, h, costs, lo, hi, int(cfg["placebo_draws"]), rng) if n else None
        p_val = None
        if pm is not None and n:
            p_val = float((1 + (pm >= st_net["mean"]).sum()) / (len(pm) + 1))
        reasons = []
        if n < cfg["min_events"]:
            reasons.append(f"for få hendelser ({n} < {cfg['min_events']})")
        if not n or st_net["mean"] <= 0:
            reasons.append("snitt etter kostnader er ikke positivt")
        if not n or (st_net.get("t_cluster") or 0) < req_t:
            reasons.append(f"klynge-t {st_net.get('t_cluster') or 0:.2f} < krav {req_t:.2f}")
        if p_val is None or p_val >= cfg["placebo_p"]:
            reasons.append(f"placebo-p {p_val if p_val is not None else float('nan'):.3f} >= {cfg['placebo_p']}")
        passed = not reasons
        any_pass |= passed
        res["horizons"][str(h)] = {
            "gross_excess": st_gross, "net": st_net,
            "mean_cost": float(np.mean(tr["cost"])) if n else None,
            "spread_default_share": float(np.mean(~np.isfinite(tr["hs_in"]))) if n else None,
            "median_half_spread": (float(np.nanmedian(tr["hs_in"])) if n and np.isfinite(tr["hs_in"]).any()
                                   else None),
            "placebo_mean": float(np.mean(pm)) if pm is not None else None,
            "placebo_p": p_val, "passed": passed, "reasons": reasons,
            "first_entry": str(cal[int(tr["i"].min())].date()) if n else None,
            "last_entry": str(cal[int(tr["i"].max())].date()) if n else None,
        }
        if save_events:
            rows = df.iloc[tr["row"]]
            events[h] = pd.DataFrame({"id": rows["id"].to_numpy(), "ticker": rows["ticker"].to_numpy(),
                                      "published": rows["published"].to_numpy(),
                                      "direction": rows["direction"].to_numpy(), "hold": h,
                                      "entry_date": cal[tr["i"]].date, "exit_date": cal[tr["j"]].date,
                                      "gross": tr["gross"], "bench": tr["bench"], "excess": tr["excess"],
                                      "cost": tr["cost"], "net": tr["net"]})
    res["passed_any"] = any_pass

    if log:
        append_log(out_root, {"at": res["generated_at"], "name": name, "spec_hash": shash, "mode": mode,
                              "params": params or {}, "K": K, "required_t": req_t,
                              "n": {h: v["net"].get("n", 0) for h, v in res["horizons"].items()},
                              "t_cluster": {h: v["net"].get("t_cluster") for h, v in res["horizons"].items()},
                              "passed": {h: v["passed"] for h, v in res["horizons"].items()}})
    if write:
        d = os.path.join(out_root, name)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "results.json"), "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=1, default=str)
        with open(os.path.join(d, "report.md"), "w", encoding="utf-8") as f:
            f.write(render_report(res))
        if save_events and events:
            pd.concat(events.values(), ignore_index=True).to_csv(os.path.join(d, "events.csv"), index=False)
    return res


# ------------------------------------------------------------------ rapport
def _pct(v, d=2):
    return "–" if v is None else f"{v * 100:+.{d}f} %"


def _num(v, d=2):
    return "–" if v is None else f"{v:.{d}f}"


def render_report(res):
    L = [f"# Testbenk: {res['name']}", "",
         f"Modus: **{res['mode']}** · spec `{res['spec_hash']}` · kjørt {res['generated_at'][:16]} UTC  ",
         f"Kurser {res['price_first_date']} → {res['price_last_date']} · holdout fra {res['holdout_start']} "
         f"({'brukt i denne kjøringen' if res['mode'] == 'holdout' else 'ikke brukt'})  ",
         f"Ulike tester i loggen K = {res['K_distinct_tests']} → krav til klynge-t: **{res['required_t']:.2f}**  ",
         f"Kostnader: {res['costs']}", "",
         f"Signaler inn: {res['n_signals_in']} · tatt ut: "
         + (", ".join(f"{k.replace('_', ' ')} {v}" for k, v in res["dropped"].items() if v) or "ingen"), "",
         "## Reaksjon rundt publisering (ikke handlebar)", "",
         "| Vindu | n | Snitt | Median | Treff | t | Klynge-t |", "|---|---:|---:|---:|---:|---:|---:|"]
    for key, label in (("car_0_1", "CAR[0,1]"), ("car_m5_m1", "CAR[-5,-1] (før)")):
        s = res["reaction"][key]
        L.append(f"| {label} | {s.get('n', 0)} | {_pct(s.get('mean'))} | {_pct(s.get('median'))} | "
                 f"{_num(s.get('hit_rate'))} | {_num(s.get('t'))} | {_num(s.get('t_cluster'))} |")
    L += ["", "## Handlebar: inngang neste åpning, meravkastning mot OSEBX", "",
          "| Hold (dager) | n | Brutto | Kostnad | Netto | Median netto | Treff netto | Klynge-t | Placebo-p | Dom |",
          "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    for h, v in res["horizons"].items():
        g, n = v["gross_excess"], v["net"]
        L.append(f"| {h} | {n.get('n', 0)} | {_pct(g.get('mean'))} | {_pct(v['mean_cost'])} | {_pct(n.get('mean'))} | "
                 f"{_pct(n.get('median'))} | {_num(n.get('hit_rate'))} | {_num(n.get('t_cluster'))} | "
                 f"{_num(v['placebo_p'], 3)} | {'✅ bestått' if v['passed'] else '❌'} |")
    v1 = next(iter(res["horizons"].values()), {})
    if v1.get("spread_default_share") is not None:
        L += ["", f"Spread ved inngang: median anslått halv spread {_pct(v1.get('median_half_spread')).lstrip('+')}, "
                  f"{v1['spread_default_share']:.0%} av handlene brukte standardverdien (for lite høy/lav-historikk)."]
    L += [""]
    for h, v in res["horizons"].items():
        if v["reasons"]:
            L.append(f"- **{h} d:** " + "; ".join(v["reasons"]))
    L += ["", "Brutto = snitt meravkastning før kostnader. Netto = etter spread, kurtasje og slippage. "
          "Klynge-t grupperer hendelser i blokker på max(5, hold) handelsdager. Placebo-p = andel tilfeldige "
          "inngangsdager i de samme aksjene som ga minst like høyt netto-snitt.", ""]
    return "\n".join(L)


# ------------------------------------------------------------------ CLI
def main(argv=None):
    ap = argparse.ArgumentParser(description="Kjør testbenken på en CSV med signaler (ticker, published, [direction], [id]).")
    ap.add_argument("--signals", required=True)
    ap.add_argument("--name", required=True, help="Navn på ideen. Samme navn + samme params = samme test i loggen.")
    ap.add_argument("--params", default="{}", help="JSON som beskriver hvordan signalene ble laget.")
    ap.add_argument("--holdout", action="store_true", help="Bruk holdout-perioden (kun én gang per idé).")
    ap.add_argument("--force", action="store_true", help="Overstyr holdout-låsen (logges).")
    ap.add_argument("--events", action="store_true", help="Lagre hver handel i events.csv.")
    args = ap.parse_args(argv)
    sig = pd.read_csv(args.signals)
    res = run_event_study(sig, args.name, params=json.loads(args.params), use_holdout=args.holdout,
                          force=args.force, save_events=args.events)
    print(render_report(res))


if __name__ == "__main__":
    main()
