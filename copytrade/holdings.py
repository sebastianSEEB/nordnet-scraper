#!/usr/bin/env python3
"""
Beholdningen til 3-stjerners brukere, hentet halvmanuelt
========================================================
Nordnet viser beholdningen på Nordnet Social bare for innloggede (uten
innlogging får man en uskarp plassholder med Unity, Disney, Chewy ...).
Derfor hentes den IKKE av GitHub Actions, men fra Sebastians egen nettleser
med Claude i Chrome mens han er logget inn. Ingen innloggingsdata lagres.

Gang:
    1. python copytrade/holdings.py targets --top 75
           -> nordnet_data/copytrade/holdings/targets.json (hvem som skal sjekkes)
    2. Claude i Chrome åpner hver profil, fanen «Beholdning», kopierer teksten
       og lagrer den med:
           python copytrade/holdings.py add <bruker> <fil-med-sidetekst>
       (eller bygger snapshot-filen direkte i samme format)
    3. python copytrade/holdings.py diff
           -> sammenligner de to siste snapshotene og skriver
              nordnet_data/copytrade/holdings/changes.json

Tolkning av endringer mellom to snapshot:
    ny linje                    = KJØPT
    linje borte                 = SOLGT
    GAV endret                  = ØKT (nye kjøp flytter GAV; salg gjør det ikke)
    vekt ned >= 40 % relativt,
      GAV uendret               = trolig REDUSERT (vekt endres også av kurs, så usikkert)
Vi vet ikke NÅR mellom snapshotene handelen skjedde, bare at den skjedde.
"""

import argparse
import glob
import json
import os
import re
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

DATA_DIR = os.path.join(ROOT, "nordnet_data")
HOLD_DIR = os.path.join(DATA_DIR, "copytrade", "holdings")
PROFILES = os.path.join(DATA_DIR, "copytrade", "profiles.json")
TARGETS = os.path.join(HOLD_DIR, "targets.json")
CHANGES = os.path.join(HOLD_DIR, "changes.json")

# Plassholderen Nordnet viser til utloggede - samme for alle profiler.
PLACEHOLDER = {"Unity Software Inc", "Walt Disney Company (The)", "Chewy, Inc. Class A"}

_NUM = r"−?-?\d[\d\s.]*,?\d*"
ROW_RE = re.compile(
    rf"(?P<name>[^\n%]+?)\s+(?P<weight>{_NUM})\s*%\s+(?P<gav>{_NUM})\s*(?P<cur>[A-Z]{{3}})\s+(?P<ret>{_NUM})\s*%")


def _num(s):
    s = s.replace("−", "-").replace("\xa0", "").replace(" ", "").replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def parse_holdings(text):
    """Teksten fra Beholdning-fanen -> liste med {name, kind, weight, gav, currency, ret}.
    Returnerer None hvis siden bare viser plassholderen (ikke innlogget)."""
    text = text.replace("\xa0", " ")
    if "Logg på Nordnet Social for å se beholdning" in text:
        return None
    rows, kind = [], "aksje"
    # Seksjonene heter «Børshandlede» og «Fond», med kolonneoverskrifter etter
    parts = re.split(r"\b(Børshandlede|Fond)\s+Vekting\s+GAV\s+Avkastning", text)
    for part in parts:
        if part in ("Børshandlede", "Fond"):
            kind = "aksje" if part == "Børshandlede" else "fond"
            continue
        for m in ROW_RE.finditer(part):
            name = re.sub(r"^\s*[A-ZÆØÅ0-9]\s+(?=\S)", "", m["name"].strip())  # fjern ikon-bokstaven
            rows.append({"name": name, "kind": kind, "weight": _num(m["weight"]), "gav": _num(m["gav"]),
                         "currency": m["cur"], "ret": _num(m["ret"])})
    if rows and {r["name"] for r in rows} >= PLACEHOLDER:
        return None
    return rows


def snapshot_path(ts=None):
    ts = ts or datetime.now(timezone.utc)
    return os.path.join(HOLD_DIR, f"snap_{ts.strftime('%Y-%m-%d')}.json")


def cmd_targets(args):
    profiles = json.load(open(PROFILES, encoding="utf-8"))
    three = [(u, p) for u, p in profiles.items() if p.get("stars") == 3]
    three.sort(key=lambda x: -(x[1].get("followers") or 0))
    targets = [{"user": u, "url": p.get("url") or f"https://www.nordnet.no/aksjeforum/medlemmer/{u}",
                "followers": p.get("followers")} for u, p in three[:args.top]]
    os.makedirs(HOLD_DIR, exist_ok=True)
    json.dump({"made_at": datetime.now(timezone.utc).isoformat(), "targets": targets},
              open(TARGETS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(targets)} av {len(three)} 3-stjerners brukere -> {TARGETS}")


def cmd_add(args):
    text = open(args.textfile, encoding="utf-8").read()
    rows = parse_holdings(text)
    path = snapshot_path()
    snap = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {"users": {}}
    snap["taken_at"] = datetime.now(timezone.utc).isoformat()
    if rows is None:
        snap["users"][args.user] = {"status": "ikke innlogget"}
    elif not rows:
        snap["users"][args.user] = {"status": "skjult eller tom"}
    else:
        snap["users"][args.user] = {"status": "ok", "holdings": rows}
    os.makedirs(HOLD_DIR, exist_ok=True)
    json.dump(snap, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"@{args.user}: {snap['users'][args.user]['status']}, {len(rows or [])} linjer -> {path}")


def diff(old, new):
    """Endringer for én bruker mellom to beholdningslister."""
    o = {h["name"]: h for h in old}
    n = {h["name"]: h for h in new}
    out = []
    for name in n.keys() - o.keys():
        out.append({"name": name, "action": "kjøpt", "weight": n[name]["weight"]})
    for name in o.keys() - n.keys():
        out.append({"name": name, "action": "solgt", "weight_before": o[name]["weight"]})
    for name in n.keys() & o.keys():
        a, b = o[name], n[name]
        if a["gav"] and b["gav"] and abs(b["gav"] / a["gav"] - 1) > 0.002:
            out.append({"name": name, "action": "økt", "gav_before": a["gav"], "gav": b["gav"],
                        "weight_before": a["weight"], "weight": b["weight"]})
        elif a["weight"] and b["weight"] is not None and b["weight"] <= 0.6 * a["weight"]:
            out.append({"name": name, "action": "trolig redusert", "weight_before": a["weight"],
                        "weight": b["weight"]})
    return out


def cmd_diff(args):
    snaps = sorted(glob.glob(os.path.join(HOLD_DIR, "snap_*.json")))
    if len(snaps) < 2:
        print("Trenger minst to snapshot for å se endringer.")
        return
    old, new = (json.load(open(p, encoding="utf-8")) for p in snaps[-2:])
    changes = []
    for user, nu in new["users"].items():
        ou = old["users"].get(user)
        if not ou or ou.get("status") != "ok" or nu.get("status") != "ok":
            continue
        for c in diff(ou["holdings"], nu["holdings"]):
            changes.append({"user": user, "between": [old["taken_at"][:10], new["taken_at"][:10]], **c})
    json.dump({"from": snaps[-2], "to": snaps[-1], "changes": changes},
              open(CHANGES, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for c in changes:
        print(f"@{c['user']:20s} {c['action']:16s} {c['name']}")
    print(f"{len(changes)} endringer -> {CHANGES}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("targets"); t.add_argument("--top", type=int, default=75)
    a = sub.add_parser("add"); a.add_argument("user"); a.add_argument("textfile")
    sub.add_parser("diff")
    args = ap.parse_args()
    {"targets": cmd_targets, "add": cmd_add, "diff": cmd_diff}[args.cmd](args)


if __name__ == "__main__":
    main()
