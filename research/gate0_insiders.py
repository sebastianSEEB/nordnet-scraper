#!/usr/bin/env python3
"""
Gate 0: virker testbenken?
==========================
Før testbenken får dømme nye ideer, må den gjenskape en effekt vi vet finnes:
innsidekjøp på Oslo Børs gir ca. +1 % meravkastning rundt publisering
(NHH-masteroppgave: 1,14 % over [0,1]).

Signal: alle innsidekjøp i markedet fra børsmeldingene (copytrade/insiders.py:
retning +1, ikke støy som spareprogram, opsjoner, egne aksjer osv.), koblet til
aksjene i watchlisten. Bare bygg-perioden (før holdout_start).

Bestått hvis snitt CAR[0,1] ligger mellom car_min og car_max (config.json) og
klynge-t >= gate0.min_t. Ligger tallet langt utenfor, er det trolig en feil i
tidsstempler, kursdata eller koblingen ticker <-> utsteder - ikke en ny oppdagelse.

Output: nordnet_data/research/gate0/{report.md, results.json, status.json}
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from copytrade.insiders import load_trades  # noqa: E402
from news_ml.common import load_universe  # noqa: E402
from research.data import load_config, load_panel  # noqa: E402
from research.harness import OUT_ROOT, run_event_study  # noqa: E402

NAME = "gate0"
PARAMS = {"signal": "innsidekjøp i markedet", "direction": 1, "noise": False, "min_value_nok": None,
          "kilde": "copytrade/insiders.py load_trades()"}


def insider_buy_signals(trades=None, universe=None):
    uni = universe if universe is not None else load_universe()
    issuer_to_ticker = {u["issuer"]: u["ticker"] for u in uni}
    rows = []
    for t in trades if trades is not None else load_trades():
        if t["direction"] != 1 or t["noise"]:
            continue
        tk = issuer_to_ticker.get(t["issuer"])
        if not tk:
            continue
        rows.append({"id": t["id"], "ticker": tk, "published": t["published"], "direction": 1,
                     "role": t.get("role"), "value_nok": t.get("value_nok")})
    return pd.DataFrame(rows)


def evaluate(res, cfg):
    g = cfg["gate0"]
    s = res["reaction"]["car_0_1"]
    mean, t = s.get("mean"), s.get("t_cluster")
    reasons = []
    if not s.get("n"):
        reasons.append("ingen hendelser")
    else:
        if not (g["car_min"] <= mean <= g["car_max"]):
            reasons.append(f"snitt CAR[0,1] {mean:+.2%} utenfor [{g['car_min']:.1%}, {g['car_max']:.1%}]")
        if (t or 0) < g["min_t"]:
            reasons.append(f"klynge-t {t or 0:.2f} < {g['min_t']}")
    return {"passed": not reasons, "reasons": reasons, "car_0_1": mean, "t_cluster": t, "n": s.get("n", 0),
            "target": "≈ +1,14 % (NHH)", "checked_at": datetime.now(timezone.utc).isoformat(),
            "price_last_date": res.get("price_last_date")}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true", help="Avslutt med feilkode hvis Gate 0 ikke bestås.")
    ap.add_argument("--no-log", action="store_true", help="Ikke skriv til testloggen (f.eks. i PR-sjekker).")
    args = ap.parse_args(argv)

    cfg = load_config()
    panel = load_panel()
    sig = insider_buy_signals()
    print(f"Innsidekjøp koblet til watchlisten: {len(sig)}")
    res = run_event_study(sig, NAME, params=PARAMS, panel=panel, config=cfg, log=not args.no_log)
    status = evaluate(res, cfg)
    out = os.path.join(OUT_ROOT, NAME)
    with open(os.path.join(out, "status.json"), "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=1)
    head = ["# Gate 0: gjenskaper testbenken innsideeffekten?", "",
            f"**{'✅ BESTÅTT' if status['passed'] else '❌ IKKE BESTÅTT'}** · CAR[0,1] = "
            f"{(status['car_0_1'] or 0):+.2%} (mål ≈ +1,14 %, godkjent "
            f"{cfg['gate0']['car_min']:.1%}–{cfg['gate0']['car_max']:.1%}) · klynge-t = "
            f"{(status['t_cluster'] or 0):.2f} (krav {cfg['gate0']['min_t']}) · n = {status['n']}", ""]
    head += [f"- {r}" for r in status["reasons"]] + ([""] if status["reasons"] else [])
    head += ["Handlebar-tabellen under er informasjon, ikke en del av Gate 0: den viser hva som er igjen "
             "når man kjøper på neste åpning og betaler kostnader.", "", "---", ""]
    path = os.path.join(out, "report.md")
    with open(path, encoding="utf-8") as f:
        body = f.read()
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(head) + body)
    print("\n".join(head) + body)
    if args.strict and not status["passed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
