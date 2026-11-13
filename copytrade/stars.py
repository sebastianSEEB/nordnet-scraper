#!/usr/bin/env python3
"""
Stjernerating for Nordnet Social-profiler
=========================================
Nordnet viser stjerner (0-3) på hver offentlige profil uten innlogging.
3 stjerner = porteføljens risikojusterte avkastning (Sharpe) er blant topp 10 %
på Nordnet Social. Beholdning og handler krever innlogging, så dem henter vi IKKE.

Profilene vi sjekker er de som har skrevet i forumet på aksjene i watchlisten
(nordnet_data/archive/posts_*.jsonl). Mest aktive først, og hver profil sjekkes
på nytt etter --recheck-days dager. Kjøres inkrementelt - noen hundre profiler
per kjøring, så Nordnet ikke får en storm av forespørsler.

Stjernehistorikk (fra 2026-11-13): Nordnet viser bare DAGENS stjerner, ikke hvor
lenge brukeren har hatt dem. Derfor logger vi hver sjekk selv:
    star_log             [[dato, stjerner], ...]  - ny rad bare når stjernene endrer seg
    first_checked_at     første gang vi sjekket profilen
    three_since          første sjekk i den nåværende 3-stjerners-perioden (None ellers)
    three_streak_checks  antall sjekker på rad med 3 stjerner
three_since er en NEDRE grense: en bruker som hadde 3 stjerner første gang vi så
ham, kan ha hatt dem i årevis. Med sjekk hver 14. dag gir et halvt år ca. 13 sjekker.

Output:
    nordnet_data/copytrade/profiles.json        {brukernavn: {stars, followers, star_log, ...}}
    nordnet_data/copytrade/stars_status.json    hvor mange som ble parset, feil
    nordnet_data/copytrade/debug/profile_*.html to rå sider hvis parsingen feiler,
                                                så regexene kan rettes

Bruk:
    python copytrade/stars.py --max-profiles 500 --delay 1.0
"""

import argparse
import json
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime, timedelta, timezone

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from archive_posts import iter_archive  # noqa: E402

DATA_DIR = os.path.join(ROOT, "nordnet_data")
OUT_DIR = os.path.join(DATA_DIR, "copytrade")
PROFILES = os.path.join(OUT_DIR, "profiles.json")
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
    "Accept-Language": "nb-NO,nb;q=0.9,no;q=0.8,en;q=0.7",
}

# Flere mulige formater, siden vi ikke styrer Nordnets HTML. Første treff vinner.
# Det Nordnet faktisk bruker (sett i rå HTML okt 2026): <span class="sr-only">2 stars</span> / "null stars"
SR_ONLY_RE = re.compile(r'class="sr-only">\s*(null|\d)\s*stars?\s*<', re.I)
STAR_RES = [
    re.compile(r'"(?:rating|stars|starRating|star_rating|numberOfStars)"\s*:\s*"?(\d)"?', re.I),
    re.compile(r'aria-label="[^"]{0,40}?(\d)\s*(?:av\s*3\s*)?(?:stars?|stjerner?)', re.I),
    re.compile(r'Vurdering.{0,400}?\b(\d)\s*(?:stars?|stjerner?)\b', re.I | re.S),
    re.compile(r'\b(\d)\s*(?:av\s*3\s*)?(?:stars?|stjerner?)\b', re.I),
]
NO_STARS_RES = [
    re.compile(r'Vurdering.{0,400}?\b(null|no|ingen|0)\s*(?:stars?|stjerner?)\b', re.I | re.S),
    re.compile(r'"(?:rating|stars|starRating)"\s*:\s*null', re.I),
]
FOLLOWERS_RE = re.compile(r'(\d[\d\s .]*)\s*(?:<[^>]+>\s*)*Følgere', re.I)
MEMBER_RE = re.compile(r'Medlem i\s*(?:<[^>]+>\s*)*([^<]{1,20})', re.I)


def parse_profile(html):
    stars, how = None, None
    m = SR_ONLY_RE.search(html)
    if m:
        v = m.group(1).lower()
        return {"stars": 0 if v == "null" else int(v), "parsed_by": "sr-only",
                **_extras(html)}
    for rx in NO_STARS_RES:
        if rx.search(html):
            stars, how = 0, "ingen"
            break
    if stars is None:
        for i, rx in enumerate(STAR_RES):
            m = rx.search(html)
            if m and 0 <= int(m.group(1)) <= 3:
                stars, how = int(m.group(1)), f"regex{i}"
                break
    return {"stars": stars, "parsed_by": how, **_extras(html)}


def _extras(html):
    followers = None
    m = FOLLOWERS_RE.search(html)
    if m:
        digits = re.sub(r"\D", "", m.group(1))
        followers = int(digits) if digits else None
    member = None
    m = MEMBER_RE.search(html)
    if m:
        member = m.group(1).strip()
    return {"followers": followers, "member_for": member}


def backfill_history(p):
    """Profiler sjekket før historikken fantes: start loggen fra siste kjente sjekk."""
    if "star_log" in p or not p.get("checked_at") or p.get("stars") is None:
        return
    day = p["checked_at"][:10]
    p["first_checked_at"] = p["checked_at"]
    p["star_log"] = [[day, p["stars"]]]
    p["three_streak_checks"] = 1 if p["stars"] == 3 else 0
    p["three_since"] = day if p["stars"] == 3 else None


def update_history(p, stars, at):
    """Legg en ny sjekk inn i stjernehistorikken (kalles bare når stjernene ble funnet)."""
    day = at[:10]
    p.setdefault("first_checked_at", at)
    log = p.setdefault("star_log", [])
    if not log or log[-1][1] != stars:
        log.append([day, stars])
    if stars == 3:
        p["three_streak_checks"] = p.get("three_streak_checks", 0) + 1
        if not p.get("three_since"):
            p["three_since"] = day
    else:
        p["three_streak_checks"] = 0
        p["three_since"] = None


def candidate_profiles(data_dir):
    posts = Counter()
    url_of = {}
    for p in iter_archive(data_dir):
        url = p.get("profile_url") or ""
        if "/aksjeforum/medlemmer/" not in url:
            continue
        user = url.rstrip("/").rsplit("/", 1)[-1]
        posts[user] += 1
        url_of[user] = url
    return posts, url_of


def load_json(path, default):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default=DATA_DIR)
    ap.add_argument("--max-profiles", type=int, default=500)
    ap.add_argument("--delay", type=float, default=1.0)
    ap.add_argument("--recheck-days", type=int, default=14)
    ap.add_argument("--max-minutes", type=float, default=15)
    args = ap.parse_args()

    os.makedirs(os.path.join(OUT_DIR, "debug"), exist_ok=True)
    profiles = load_json(PROFILES, {})
    posts, url_of = candidate_profiles(args.data_dir)
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=args.recheck_days)).isoformat()

    for user, n in posts.items():
        profiles.setdefault(user, {"url": url_of[user]})
        profiles[user]["forum_posts"] = n
    for p in profiles.values():
        backfill_history(p)

    due = [u for u in posts if (profiles[u].get("checked_at") or "") < cutoff]
    due.sort(key=lambda u: (profiles[u].get("checked_at") is not None, -posts[u]))  # aldri sjekket + mest aktive først
    due = due[:args.max_profiles]

    session = requests.Session()
    deadline = time.time() + args.max_minutes * 60
    status = {"started": now.isoformat(), "candidates": len(posts), "due": len(due), "checked": 0,
              "parsed_stars": 0, "http_errors": Counter(), "parsed_by": Counter(), "debug_saved": 0}
    for user in due:
        if time.time() > deadline:
            break
        try:
            r = session.get(profiles[user]["url"], headers=HEADERS, timeout=20)
        except requests.RequestException as e:
            status["http_errors"][type(e).__name__] += 1
            time.sleep(args.delay * 3)
            continue
        if r.status_code != 200:
            status["http_errors"][str(r.status_code)] += 1
            if r.status_code == 429:
                time.sleep(30)
            continue
        info = parse_profile(r.text)
        profiles[user].update(info)
        profiles[user]["checked_at"] = datetime.now(timezone.utc).isoformat()
        if info["stars"] is not None:
            update_history(profiles[user], info["stars"], profiles[user]["checked_at"])
        status["checked"] += 1
        status["parsed_by"][info["parsed_by"] or "ikke funnet"] += 1
        if info["stars"] is not None:
            status["parsed_stars"] += 1
        elif status["debug_saved"] < 2:
            with open(os.path.join(OUT_DIR, "debug", f"profile_{status['debug_saved']}.html"), "w",
                      encoding="utf-8") as f:
                f.write(r.text)
            status["debug_saved"] += 1
        time.sleep(args.delay)

    with open(PROFILES, "w", encoding="utf-8") as f:
        json.dump(dict(sorted(profiles.items())), f, ensure_ascii=False, indent=1)

    dist = Counter(str(p.get("stars")) for p in profiles.values() if p.get("checked_at"))
    status.update({"finished": datetime.now(timezone.utc).isoformat(), "star_distribution": dist,
                   "total_checked_ever": sum(1 for p in profiles.values() if p.get("checked_at"))})
    status = json.loads(json.dumps(status, default=dict))
    with open(os.path.join(OUT_DIR, "stars_status.json"), "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)
    print(json.dumps(status, ensure_ascii=False, indent=2))
    if status["checked"] and not status["parsed_stars"]:
        print("ADVARSEL: fant ingen stjerner - se nordnet_data/copytrade/debug/ og rett STAR_RES.")


if __name__ == "__main__":
    main()
