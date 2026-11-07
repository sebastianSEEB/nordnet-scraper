#!/usr/bin/env python3
"""
Fase 1: raske gevinster på det som allerede kjører
==================================================
Kjører alle Fase 1-testene gjennom testbenken og sjekker Gate 1.

Forhåndsregistrerte tester (byggeperioden, logges i testloggen og øker K):
    Innsidesignal 2.0      p1_innsider_opportunistisk (score >= 2), p1_innsider_klynge,
                           p1_innsider_etter_fall, p1_innsider_forste_paa_aar,
                           p1_papir_hovedstrategi (den låste copytrade-strategien, nå med kostnader)
    Oppmerksomhet          p1_drift_alle_rapporter, p1_drift_travel_morgen, p1_drift_fredag
                           (handle i retning av reaksjonen på rapportdagen, fra neste åpning),
                           p1_utbyttemaaned, p1_emisjon_uten_reparasjon, p1_emisjon_med_reparasjon

Fremover-overvåking (ikke tester, holdout-perioden røres ikke av testbenken):
    Inngangstidspunkt      ny regel (neste åpning etter meldingen) mot gammel (etter den daglige
                           kjøringen 16:30 UTC), parvis, netto etter kostnader, 20 dagers hold
    Glidning               åpningskurs ved inngang mot kursen innsideren betalte
    Flokk-filteret         topper i forumet, og hvordan blokkerte og tillatte kjøp gikk

Gate 1 (fra veikartet):
    a) minst 40 innsidesignaler fremover, og ny inngang slår gammel etter kostnader
    b) kjøp flokk-filteret blokkerer gjør det dårligere enn kjøpene det slipper gjennom
    c) en ny feature teller bare hvis testen består (klynge-t over kravet, ca. 3)

Output: nordnet_data/research/phase1/{report.md, status.json, spikes.csv, flags.csv}
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from copytrade import paper  # noqa: E402
from copytrade.insiders import load_trades  # noqa: E402
from news_ml import attention  # noqa: E402
from news_ml.common import load_universe  # noqa: E402
from research import herd, insider2  # noqa: E402
from research.data import DATA_DIR, load_config, load_panel  # noqa: E402
from research.harness import (OUT_ROOT, normalize_published, prepare_signals, run_event_study,  # noqa: E402
                              summarize, tradable_returns)

HOLD = 20
MIN_FORWARD = 40
DRIFT_MIN_REACTION = 0.01
RUN_UTC_HOUR, RUN_UTC_MIN = 16, 30   # news_ml.yml kjører 16:30 UTC på hverdager


# ------------------------------------------------------------------ signaler
def _sig(df, direction=1):
    out = pd.DataFrame({"id": df["id"].astype(str).to_numpy(), "ticker": df["ticker"].to_numpy(),
                        "published": df["published"].to_numpy()})
    out["direction"] = direction if np.isscalar(direction) else np.asarray(direction)
    return out


def insider_tests(buys, opn, cls, i2t):
    tests = [
        ("p1_innsider_opportunistisk", buys[buys["score"] >= 2], "Innsidekjøp med minst 2 av 4 opportunistisk-flagg"),
        ("p1_innsider_klynge", buys[insider2.as_bool(buys["klynge"])], "Minst 2 ulike innsidere har kjøpt siste 10 dager"),
        ("p1_innsider_etter_fall", buys[insider2.as_bool(buys["etter_fall"])],
         "Kjøp etter at aksjen har falt >= 10 % mer enn OSEBX på 20 dager"),
        ("p1_innsider_forste_paa_aar", buys[insider2.as_bool(buys["forste_paa_aar"])], "Første innsidekjøp i selskapet på et år"),
    ]
    out = [(n, _sig(d), {"utvalg": desc, "flagg": insider2.FLAGS}, desc) for n, d, desc in tests]
    ps = paper.insider_signals(opn, cls, i2t)
    v = paper.INSIDER_VARIANTS[paper.MAIN[0]]
    if not ps.empty:
        main = ps[(ps["value_nok"] >= v["min_value"]) & ps["role"].isin(v["roles"])]
        out.append(("p1_papir_hovedstrategi", _sig(main), {"variant": paper.MAIN[0], "hold": paper.MAIN[1]},
                    f"Den låste copytrade-strategien ({v['label']}), nå med kostnader"))
    return out


def drift_tests(rep, panel):
    """Handle i retning av markedsjustert reaksjon på rapportdagen t0, fra åpningen dagen etter."""
    Cl, Bc = panel.close.to_numpy(dtype=float), panel.bench_close.to_numpy(dtype=float)
    col = {t: k for k, t in enumerate(panel.close.columns)}
    rows = []
    for r in rep.itertuples():
        c, t0 = col.get(r.ticker), int(r.t0)
        if c is None or t0 < 1:
            continue
        x = (Cl[t0, c] / Cl[t0 - 1, c] - 1) - (Bc[t0] / Bc[t0 - 1] - 1)
        if not np.isfinite(x) or abs(x) < DRIFT_MIN_REACTION:
            continue
        rows.append({"id": f"rep:{r.ticker}:{t0}", "ticker": r.ticker, "published": str(panel.cal[t0].date()),
                     "direction": int(np.sign(x)), "travel": bool(r.travel_morgen),
                     "fredag": bool(r.fredag_etter_stengning)})
    d = pd.DataFrame(rows)
    if d.empty:
        return []
    p = {"reaksjon_min": DRIFT_MIN_REACTION, "retning": "fortegn på reaksjonen dag t0"}
    return [
        ("p1_drift_alle_rapporter", d, p, "Alle rapporter: følg reaksjonen fra neste åpning"),
        ("p1_drift_travel_morgen", d[d["travel"]], {**p, "travel": "topp 10 % dager"},
         "Rapporter på travle dager (mange rapporter samtidig)"),
        ("p1_drift_fredag", d[d["fredag"]], {**p, "fredag": "etter 16:20 eller helg"},
         "Rapporter publisert fredag etter stengning eller i helgen"),
    ]


def other_attention_tests(msgs, i2t, panel):
    out = []
    last_month = str(panel.cal[-1].to_period("M"))
    div = attention.predicted_dividend_signals(attention.dividend_months(msgs, i2t), last_month)
    if len(div):
        out.append(("p1_utbyttemaaned", div[["id", "ticker", "published", "direction"]],
                    {"regel": "eks utbytte samme måned i fjor"}, "Kjøp ved starten av ventet utbyttemåned"))
    pl = attention.placement_events(msgs, i2t, panel.cal)
    if len(pl):
        pl = pl.assign(id=[f"pl:{t}:{i}" for t, i in zip(pl["ticker"], pl["t0"])])
        for name, flag, desc in (("p1_emisjon_uten_reparasjon", False, "Short etter rettet emisjon uten reparasjon"),
                                 ("p1_emisjon_med_reparasjon", True, "Short etter rettet emisjon med reparasjon")):
            sub = pl[pl["reparasjon"] == flag]
            out.append((name, _sig(sub, -1), {"reparasjon": flag, "retning": -1}, desc))
    return out


# ------------------------------------------------------------------ fremover-overvåking
def old_timing(published_iso):
    """Første daglige kjøring (16:30 UTC, hverdager) som så meldingen."""
    ts = pd.Timestamp(published_iso)
    ts = ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
    run = ts.normalize() + pd.Timedelta(hours=RUN_UTC_HOUR, minutes=RUN_UTC_MIN)
    if ts > run:
        run += pd.Timedelta(days=1)
    while run.weekday() >= 5:
        run += pd.Timedelta(days=1)
    return run.isoformat()


def _returns_by_id(sig, panel, costs, lo, hi, h=HOLD):
    prep, _ = prepare_signals(sig, panel)
    tr = tradable_returns(prep, panel, h, costs, lo, hi)
    ids = prep["id"].to_numpy()[tr["row"]]
    return pd.DataFrame({"id": ids, "i": tr["i"], "net": tr["net"], "ticker": tr["ticker"]}), tr, prep


def timing_comparison(base, panel, costs, lo, hi):
    new, _, _ = _returns_by_id(base, panel, costs, lo, hi)
    old_sig = base.assign(published=[old_timing(normalize_published(p)) for p in base["published"]])
    old, _, _ = _returns_by_id(old_sig, panel, costs, lo, hi)
    m = new.merge(old, on="id", suffixes=("_ny", "_gammel"))
    diff = m["net_ny"] - m["net_gammel"]
    return {"n_par": int(len(m)), "n_ulik_inngang": int((m["i_ny"] != m["i_gammel"]).sum()),
            "netto_ny": summarize(m["net_ny"], m["i_ny"] // HOLD),
            "netto_gammel": summarize(m["net_gammel"], m["i_ny"] // HOLD),
            "differanse": summarize(diff, m["i_ny"] // HOLD)}


def slippage(base, panel, raw_open, lo, hi):
    """Åpningskurs ved inngang / innsiderens kurs - 1, for ny og gammel inngang."""
    out = {}
    price = dict(zip(base["id"].astype(str), base["price"]))
    for label, sig in (("ny", base), ("gammel", base.assign(published=[old_timing(normalize_published(p))
                                                                         for p in base["published"]]))):
        prep, _ = prepare_signals(_sig(sig), panel)
        prep = prep[(prep["i"] >= lo) & (prep["i"] < hi)]
        vals = []
        for r in prep.itertuples():
            p = price.get(str(r.id))
            if not p or r.ticker not in raw_open:
                continue
            o = raw_open[r.ticker].iloc[r.i] if r.i < len(raw_open) else np.nan
            if np.isfinite(o) and 0.5 < o / p < 2:
                vals.append(o / p - 1)
        out[label] = {"n": len(vals), "median": float(np.median(vals)) if vals else None,
                      "mean": float(np.mean(vals)) if vals else None}
    return out


def herd_monitor(panel, costs, s2t, base, out_dir):
    counts = herd.load_post_counts(DATA_DIR, s2t, panel.cal)
    spikes = herd.find_spikes(counts, panel)
    cov = herd.coverage_start(counts) if counts.shape[1] else None
    res = {"forum_dekning_fra": None if cov is None else str(panel.cal[cov].date()), "n_topper": int(len(spikes))}
    if len(spikes):
        spikes = spikes.assign(ex_5=herd.forward_excess(spikes, panel, 5), ex_20=herd.forward_excess(spikes, panel, 20))
        for h in (5, 20):
            v = spikes[f"ex_{h}"].dropna()
            res[f"etter_topp_{h}d"] = {"n": int(len(v)), "snitt": float(v.mean()) if len(v) else None}
    spikes.to_csv(os.path.join(out_dir, "spikes.csv"), index=False)
    if cov is None:
        return res
    prep, _ = prepare_signals(base, panel)
    tr = tradable_returns(prep, panel, HOLD, costs, cov, len(panel.cal))
    if not len(tr["i"]):
        res.update({"blokkert": {"n": 0}, "tillatt": {"n": 0}, "strammet": {"n": 0}})
        return res
    sh = herd.shadow_filter(tr, spikes, panel)
    b, a, t = sh[sh["blocked"]], sh[~sh["blocked"]], sh[sh["tightened"]]
    res["blokkert"] = {"n": int(len(b)), "netto": float(b["net"].mean()) if len(b) else None}
    res["tillatt"] = {"n": int(len(a)), "netto": float(a["net"].mean()) if len(a) else None}
    res["strammet"] = {"n": int(len(t)), "netto_vanlig": float(t["net"].mean()) if len(t) else None,
                       "netto_strammet": float(t["net_tight"].mean()) if len(t) else None}
    return res


# ------------------------------------------------------------------ rapport
def _pct(v):
    return "–" if v is None or (isinstance(v, float) and not np.isfinite(v)) else f"{v * 100:+.2f} %"


def _n(v, d=2):
    return "–" if v is None else f"{v:.{d}f}"


def render(status, results):
    g = status["gate1"]
    L = ["# Fase 1: status", "",
         f"Kjørt {status['generated_at'][:16]} UTC · kurser til {status['price_last_date']} · "
         f"K = {status['K']} ulike tester → krav til klynge-t {status['required_t']:.2f}", "",
         "## Gate 1", "",
         f"- **a) Inngangstidspunkt:** {g['a']['tekst']}",
         f"- **b) Flokk-filteret:** {g['b']['tekst']}",
         f"- **c) Nye features:** {g['c']['tekst']}",
         f"- **Samlet:** {'✅ bestått' if g['passed'] else '⏳ ikke bestått ennå'}", "",
         "## Testene (byggeperioden, 20 dagers hold, netto etter kostnader)", "",
         "| Test | Hva | n | Brutto | Netto | Klynge-t | Placebo-p | Bestått på |",
         "|---|---|---:|---:|---:|---:|---:|---|"]
    for name, desc, res in results:
        v = res["horizons"].get(str(HOLD), {})
        n, gr = v.get("net", {}), v.get("gross_excess", {})
        ok = [h for h, x in res["horizons"].items() if x["passed"]]
        L.append(f"| `{name}` | {desc} | {n.get('n', 0)} | {_pct(gr.get('mean'))} | {_pct(n.get('mean'))} | "
                 f"{_n(n.get('t_cluster'))} | {_n(v.get('placebo_p'), 3)} | {', '.join(ok) + ' d' if ok else '–'} |")
    L += ["", "Hele tabellen for hver test (alle holdetider, reaksjon rundt publisering) ligger i "
          "`nordnet_data/research/<test>/report.md`.", ""]
    tm = status["timing"]
    L += ["## Inngangstidspunkt: ny regel mot gammel (alle rene innsidekjøp, 20 d)", "",
          "Ny regel: første åpning etter meldingen. Gammel: første åpning etter den daglige kjøringen 16:30 UTC. "
          "De er like for meldinger publisert mellom 09:00 og kjøringen (17:30 vinter / 18:30 sommer, Oslo-tid), så "
          "forskjellen kommer fra morgen- og kveldsmeldinger.", "",
          "| Periode | Par | Ulik inngang | Netto ny | Netto gammel | Differanse | Klynge-t diff |",
          "|---|---:|---:|---:|---:|---:|---:|"]
    for label, key in (("Historikk (bygg)", "historikk"), ("Fremover (paper)", "fremover")):
        x = tm[key]
        L.append(f"| {label} | {x['n_par']} | {x.get('n_ulik_inngang', 0)} | {_pct(x['netto_ny'].get('mean'))} | {_pct(x['netto_gammel'].get('mean'))} | "
                 f"{_pct(x['differanse'].get('mean'))} | {_n(x['differanse'].get('t_cluster'))} |")
    sl = status["glidning"]
    L += ["", f"Glidning, hele perioden (åpningskurs ved inngang mot innsiderens kurs, median): ny regel "
          f"{_pct(sl['ny']['median'])} (n = {sl['ny']['n']}), gammel {_pct(sl['gammel']['median'])} "
          f"(n = {sl['gammel']['n']}).", ""]
    h = status["herd"]
    L += ["## Flokk-filteret (fremover, forumdata fra " + str(h.get("forum_dekning_fra")) + ")", "",
          f"Topper funnet: {h['n_topper']}. "
          + (f"Meravkastning etter topp: 5 d {_pct(h.get('etter_topp_5d', {}).get('snitt'))} "
             f"(n = {h.get('etter_topp_5d', {}).get('n', 0)}), 20 d {_pct(h.get('etter_topp_20d', {}).get('snitt'))} "
             f"(n = {h.get('etter_topp_20d', {}).get('n', 0)})." if h["n_topper"] else ""), ""]
    if "blokkert" in h:
        L += [f"- Innsidekjøp filteret ville blokkert: n = {h['blokkert']['n']}, netto {_pct(h['blokkert'].get('netto'))}",
              f"- Innsidekjøp det slipper gjennom: n = {h['tillatt']['n']}, netto {_pct(h['tillatt'].get('netto'))}",
              f"- Posisjoner der salget ble strammet inn: n = {h['strammet']['n']}, netto vanlig "
              f"{_pct(h['strammet'].get('netto_vanlig'))} mot strammet {_pct(h['strammet'].get('netto_strammet'))}", ""]
    fl = status["flagg"]
    L += ["## Opportunistisk-flaggene", "",
          f"{fl['n']} rene innsidekjøp i watchlisten, {fl['med_person']} med lesbart navn på innsideren.", "",
          "| Flagg | Kjent | Sann |", "|---|---:|---:|"]
    for f in insider2.FLAGS:
        L.append(f"| {f} | {fl[f]['kjent']} | {fl[f]['sann']} |")
    L += ["", "Score-fordeling: " + ", ".join(f"{k}: {v}" for k, v in fl["score_fordeling"].items()), ""]
    return "\n".join(L)


# ------------------------------------------------------------------ main
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-log", action="store_true", help="Ikke skriv til testloggen (PR-sjekker).")
    args = ap.parse_args(argv)
    cfg = load_config()
    costs = cfg["costs"]
    out_dir = os.path.join(OUT_ROOT, "phase1")
    os.makedirs(out_dir, exist_ok=True)

    panel = load_panel()
    cal = panel.cal
    uni = load_universe()
    i2t = {u["issuer"]: u["ticker"] for u in uni}
    s2t = {u["slug"]: u["ticker"] for u in uni}
    opn, cls = paper.load_prices()
    raw_open = paper.load_raw_open(cal=cal)
    msgs = attention.load_messages()

    buys = insider2.add_flags(insider2.clean_buys(load_trades(), i2t), panel)
    buys[["id", "ticker", "published", "person", "role", "value_nok"] + insider2.FLAGS + ["score"]].to_csv(
        os.path.join(out_dir, "flags.csv"), index=False)

    rep = attention.report_events(msgs, i2t, cal)
    tests = insider_tests(buys, opn, cls, i2t) + drift_tests(rep, panel) + other_attention_tests(msgs, i2t, panel)
    results = []
    for name, sig, params, desc in tests:
        res = run_event_study(sig, name, params=params, panel=panel, config=cfg, log=not args.no_log)
        results.append((name, desc, res))
        v = res["horizons"].get(str(HOLD), {}).get("net", {})
        print(f"{name:30s} n={v.get('n', 0):5d} netto={v.get('mean') or 0:+.2%} t={v.get('t_cluster') or 0:+.2f} "
              f"bestått={[h for h, x in res['horizons'].items() if x['passed']]}")

    h_idx = int(cal.searchsorted(pd.Timestamp(cfg["holdout_start"])))
    ledger_path = os.path.join(DATA_DIR, "copytrade", "ledger.json")
    started = json.load(open(ledger_path))["started_at"] if os.path.exists(ledger_path) else cal[-1].isoformat()
    f_idx = int(cal.searchsorted(pd.Timestamp(started[:10])))
    base = _sig(buys)
    timing = {"historikk": timing_comparison(base, panel, costs, 0, h_idx),
              "fremover": timing_comparison(base, panel, costs, f_idx, len(cal))}
    n_forward_signals = int((pd.to_datetime(buys["published"], utc=True, format="ISO8601")
                             >= pd.Timestamp(started)).sum())
    slip = slippage(buys, panel, raw_open, 0, len(cal))
    herd_res = herd_monitor(panel, costs, s2t, base, out_dir)

    last = results[-1][2] if results else {"K_distinct_tests": 0, "required_t": cfg["min_t"]}
    fw = timing["fremover"]
    a_ok = (n_forward_signals >= MIN_FORWARD and fw["n_par"] > 0
            and (fw["differanse"].get("mean") or 0) > 0)
    a_txt = (f"{n_forward_signals} av {MIN_FORWARD} innsidesignaler fremover siden {started[:10]}; "
             f"{fw['n_par']} ferdige 20-dagers par, differanse ny − gammel {_pct(fw['differanse'].get('mean'))}. "
             + ("Bestått." if a_ok else "Venter på flere signaler." if n_forward_signals < MIN_FORWARD
                else "Ny inngang slår ikke gammel ennå."))
    hb, ha = herd_res.get("blokkert", {}), herd_res.get("tillatt", {})
    b_ok = bool(hb.get("n", 0) >= 10 and hb.get("netto") is not None and ha.get("netto") is not None
                and hb["netto"] < ha["netto"])
    b_txt = (f"{hb.get('n', 0)} blokkerte kjøp (netto {_pct(hb.get('netto'))}) mot {ha.get('n', 0)} tillatte "
             f"(netto {_pct(ha.get('netto'))}). " + ("Bestått." if b_ok else "Trenger minst 10 blokkerte kjøp "
                                                     "og at de gjør det dårligere."))
    feat = {name: any(x["passed"] for x in res["horizons"].values()) for name, _, res in results
            if name.startswith(("p1_drift", "p1_utbytte", "p1_emisjon"))}
    passed_feats = [k for k, v in feat.items() if v]
    c_txt = (f"{len(passed_feats)} av {len(feat)} oppmerksomhets-tester bestått"
             + (f" ({', '.join(passed_feats)}). Kan slås på i nyhetsmodellen med phase1.attention_in_model."
                if passed_feats else ". Ingen nye features går inn i nyhetsmodellen."))
    status = {"generated_at": datetime.now(timezone.utc).isoformat(), "price_last_date": str(cal[-1].date()),
              "K": last["K_distinct_tests"], "required_t": last["required_t"],
              "gate1": {"a": {"passed": a_ok, "tekst": a_txt, "n_forward": n_forward_signals},
                        "b": {"passed": b_ok, "tekst": b_txt}, "c": {"passed": bool(passed_feats), "tekst": c_txt,
                                                                     "features": feat},
                        "passed": bool(a_ok and b_ok)},
              "timing": timing, "glidning": slip, "herd": herd_res, "flagg": insider2.flag_summary(buys),
              "tests": {name: {"passed_horizons": [h for h, x in res["horizons"].items() if x["passed"]],
                               "net_20": res["horizons"].get(str(HOLD), {}).get("net", {})}
                        for name, _, res in results}}
    with open(os.path.join(out_dir, "status.json"), "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=1, default=str)
    text = render(status, results)
    with open(os.path.join(out_dir, "report.md"), "w", encoding="utf-8") as f:
        f.write(text)
    print(text)


if __name__ == "__main__":
    main()
