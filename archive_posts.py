#!/usr/bin/env python3
"""
Permanent arkiv over alle forum-innlegg
=======================================
Scraperen overskriver `latest/` hver kjøring, og `state/` lagrer bare ID-er.
Dette modulet gir et permanent arkiv som sentimentanalysen bygger på:

    nordnet_data/archive/posts_YYYY-MM.jsonl   (én linje = ett innlegg)

Hver linje har innlegget slik scraperen så det, pluss:
    slug             aksjen innlegget sto under
    scraped_at       når scraperen så innlegget (UTC)
    posted_at        beste estimat for når innlegget ble skrevet (UTC)
    time_precision   "min" | "hour" | "day" | "date" | null

Om posted_at (viktig for å unngå look-ahead):
Nordnet viser bare relativ tid ("for 3 t siden"), som er rundet NED. Et
innlegg merket "for 3 t siden" ble skrevet for mellom 3 og 4 timer siden.
Vi bruker bevisst det SENESTE mulige tidspunktet (scraped_at - 3 t). Da kan
vi aldri tilordne et innlegg til en handelsdag FØR det faktisk fantes - et
innlegg kan i verste fall havne én dag for sent, men aldri for tidlig.
Innlegg som bare har dato ("5. okt.") settes til 23:59 Oslo-tid samme dag.

Bruk:
    # Bygg/fyll arkivet fra git-historikken (krever full klone, ikke
    # --depth 1). Trygt å kjøre flere ganger - kjente innlegg hoppes over.
    # Tomt arkiv -> hele historikken. Sentiment-workflowen kjører dette
    # daglig med --since-days 14 for å tette eventuelle hull.
    python archive_posts.py --backfill-from-git [--since-days 14]

    # Fra scraperen (gjøres automatisk):
    from archive_posts import append_to_archive
"""

import argparse
import glob
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional, Tuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

try:
    OSLO = ZoneInfo("Europe/Oslo")
except ZoneInfoNotFoundError:  # Windows har ikke tidssonedatabasen innebygd
    sys.exit("Mangler tidssonedata - kjør: pip install tzdata")
ARCHIVE_SUBDIR = "archive"

REL_RE = re.compile(r"for\s+(\d+)\s*(min|t|døgn|d)\b", re.IGNORECASE)
NO_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "mai": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "okt": 10, "nov": 11, "des": 12,
}
# Innlegg der scraperen ikke fant relativ tid har ofte datoen limt inn
# foran teksten, f.eks. "5. okt. · Endret · Her er hva ..."
DATE_PREFIX_RE = re.compile(
    r"^\s*(\d{1,2})\.\s*(jan|feb|mar|apr|mai|jun|jul|aug|sep|okt|nov|des)\.?(?:\s*(\d{4}))?",
    re.IGNORECASE,
)


def estimate_posted_at(post: dict, scraped_at: Optional[str]) -> Tuple[Optional[datetime], Optional[str]]:
    """Returnerer (seneste mulige posted_at i UTC, presisjon)."""
    if not scraped_at:
        return None, None
    scraped = datetime.fromisoformat(scraped_at)
    if scraped.tzinfo is None:
        scraped = scraped.replace(tzinfo=timezone.utc)

    rel = post.get("posted_relative") or ""
    m = REL_RE.search(rel)
    if m:
        n, unit = int(m.group(1)), m.group(2).lower()
        if unit == "min":
            return scraped - timedelta(minutes=n), "min"
        if unit == "t":
            return scraped - timedelta(hours=n), "hour"
        return scraped - timedelta(days=n), "day"

    m = DATE_PREFIX_RE.match(post.get("text") or "")
    if m:
        day, month = int(m.group(1)), NO_MONTHS[m.group(2).lower()]
        scraped_local = scraped.astimezone(OSLO)
        year = int(m.group(3)) if m.group(3) else scraped_local.year
        try:
            local = datetime(year, month, day, 23, 59, tzinfo=OSLO)
        except ValueError:
            return None, None
        if not m.group(3) and local > scraped_local + timedelta(days=1):
            local = local.replace(year=year - 1)  # f.eks. "30. des." sett i januar
        return min(local.astimezone(timezone.utc), scraped), "date"

    return None, None


def archive_dir(data_dir: str) -> str:
    return os.path.join(data_dir, ARCHIVE_SUBDIR)


def iter_archive(data_dir: str) -> Iterable[dict]:
    for path in sorted(glob.glob(os.path.join(archive_dir(data_dir), "posts_*.jsonl"))):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    yield json.loads(line)


def load_archive_keys(data_dir: str) -> set:
    return {p["key"] for p in iter_archive(data_dir)}


def _record(post: dict, slug: str, scraped_at: str) -> dict:
    posted_at, precision = estimate_posted_at(post, scraped_at)
    rec = dict(post)
    rec["slug"] = slug
    rec["scraped_at"] = scraped_at
    rec["posted_at"] = posted_at.isoformat() if posted_at else None
    rec["time_precision"] = precision
    return rec


def _write_records(data_dir: str, records: List[dict]) -> int:
    if not records:
        return 0
    os.makedirs(archive_dir(data_dir), exist_ok=True)
    by_month: Dict[str, List[dict]] = {}
    for r in records:
        ts = r["posted_at"] or r["scraped_at"]
        month = datetime.fromisoformat(ts).astimezone(OSLO).strftime("%Y-%m")
        by_month.setdefault(month, []).append(r)
    for month, recs in by_month.items():
        path = os.path.join(archive_dir(data_dir), f"posts_{month}.jsonl")
        with open(path, "a", encoding="utf-8") as f:
            for r in recs:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return len(records)


def append_to_archive(data_dir: str, slug: str, posts: List[dict], scraped_at: str,
                      known_keys: Optional[set] = None) -> int:
    """Legger nye innlegg i arkivet. Returnerer antall som ble skrevet.

    known_keys kan sendes inn (og oppdateres) for å slippe å lese hele
    arkivet på nytt for hver aksje i samme kjøring.
    """
    if known_keys is None:
        known_keys = load_archive_keys(data_dir)
    fresh = []
    for p in posts:
        if p.get("key") and p["key"] not in known_keys:
            known_keys.add(p["key"])
            fresh.append(_record(p, slug, scraped_at))
    return _write_records(data_dir, fresh)


# ---------------------------------------------------------------- backfill

def _git(repo: str, *args: str) -> str:
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, check=True).stdout


def backfill_from_git(repo: str, data_dir: str, since_days: int = 0) -> None:
    """Går gjennom ALLE commits (eldst først) og arkiverer hvert innlegg
    første gang det dukker opp. Bruker scraped_at fra filen i den commiten,
    så posted_at blir like riktig som om arkivet hadde eksistert hele tiden."""
    if _git(repo, "rev-parse", "--is-shallow-repository").strip() == "true":
        sys.exit("Repoet er en grunn klone (shallow). Kjør først: git fetch --unshallow")

    rel_latest = os.path.relpath(os.path.join(data_dir, "latest"), repo).replace(os.sep, "/")
    known = load_archive_keys(data_dir)
    log_args = ["log", "--reverse", "--format=%H"]
    if since_days and known:  # tomt arkiv -> alltid hele historikken
        log_args.append(f"--since={since_days} days ago")
    commits = _git(repo, *log_args, "--", rel_latest).split()
    start = len(known)
    print(f"{len(commits)} commits å gå gjennom, {start} innlegg allerede i arkivet")

    pending: List[dict] = []
    for i, c in enumerate(commits, 1):
        names = _git(repo, "ls-tree", "--name-only", c, rel_latest + "/").split()
        for name in names:
            if not name.endswith("_new.json") or name.endswith("all_new.json"):
                continue
            try:
                d = json.loads(_git(repo, "show", f"{c}:{name}"))
            except (subprocess.CalledProcessError, json.JSONDecodeError):
                continue
            if not isinstance(d, dict) or not d.get("scraped_at"):
                continue
            slug = d.get("slug") or os.path.basename(name)[: -len("_new.json")]
            for p in d.get("posts") or []:
                k = p.get("key")
                if k and k not in known:
                    known.add(k)
                    pending.append(_record(p, slug, d["scraped_at"]))
        if i % 50 == 0:
            print(f"  {i}/{len(commits)} commits, {len(known) - start} nye innlegg")

    pending.sort(key=lambda r: r["scraped_at"])
    n = _write_records(data_dir, pending)
    print(f"Ferdig: {n} innlegg lagt til i {archive_dir(data_dir)}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Permanent arkiv over forum-innlegg")
    ap.add_argument("--data-dir", default="nordnet_data")
    ap.add_argument("--backfill-from-git", action="store_true",
                    help="Bygg arkivet fra hele git-historikken (engangs)")
    ap.add_argument("--since-days", type=int, default=0,
                    help="Bare se på commits fra de siste N dagene (0 = alle). Ignoreres hvis arkivet er tomt.")
    ap.add_argument("--stats", action="store_true", help="Skriv ut statistikk om arkivet")
    args = ap.parse_args()

    if args.backfill_from_git:
        backfill_from_git(".", args.data_dir, args.since_days)
    if args.stats or not args.backfill_from_git:
        posts = list(iter_archive(args.data_dir))
        with_time = [p for p in posts if p.get("posted_at")]
        print(f"Innlegg i arkivet: {len(posts)}  (med tidsstempel: {len(with_time)})")
        print(f"Aksjer: {len({p['slug'] for p in posts})}")
        if with_time:
            ts = sorted(p["posted_at"] for p in with_time)
            print(f"Periode: {ts[0][:10]} -> {ts[-1][:10]}")


if __name__ == "__main__":
    main()
