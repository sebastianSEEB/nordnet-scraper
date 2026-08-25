#!/usr/bin/env python3
"""
Nordnet Forum Scraper (med state-sporing)
==========================================
Leser (scraper) "Forum"-fanen for spesifiserte aksjer på nordnet.no, og
husker hvilke innlegg som er sett før, slik at hver kjøring kun rapporterer
NYE innlegg siden forrige kjøring. Laget for å kjøres i en scheduled task
(Claude Cowork / Claude Code) der Claude selv leser resultatet og vurderer
om det er noe positivt i innleggene.

VIKTIG Å VITE:
- Dette er IKKE et offisielt API. Nordnet kan endre HTML-strukturen når
  som helst, og da må parsingen justeres.
- Kun innleggene som lastes ved første sidevisning hentes per kjøring.
  "Vis mer"-knappen laster inn flere via en AJAX-forespørsel som dette
  scriptet ikke fanger opp.
- Vær grei mot Nordnets servere: ikke sett --delay for lavt.
- Kun lesing støttes (ingen innlogging, ingen posting/liking).

Installasjon:
    pip install requests beautifulsoup4

Bruk (én kjøring, flere aksjer):
    python nordnet_forum_scraper.py equinor-eqnr-xosl observe-medical-obsrv-xoas

Alt lagres under --data-dir (default: ./nordnet_data):
    nordnet_data/state/<slug>.json       -> alt som noen gang er sett (for dedup)
    nordnet_data/latest/<slug>_new.json  -> KUN nye innlegg fra denne kjøringen
    nordnet_data/latest/all_new.json     -> samlet, alle aksjer, denne kjøringen

Slug finner du i URL-en når du er inne på aksjen, f.eks. "equinor-eqnr-xosl"
fra https://www.nordnet.no/aksjer/kurser/equinor-eqnr-xosl
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import List, Optional, Set
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.nordnet.no/aksjer/kurser/{slug}"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "nb-NO,nb;q=0.9,no;q=0.8,en;q=0.7",
}
MEMBER_LINK_RE = re.compile(r"^/aksjeforum/medlemmer/")
REPLY_RE = re.compile(r"^Vis (\d+) svar$")
SHOW_MORE_COMMENTS_RE = re.compile(r"^Vis (\d+) kommentarer? til$")
TIME_AGO_RE = re.compile(r"^for .+ siden(\s*·\s*Endret)?$")
TIME_AGO_PREFIX_RE = re.compile(r"^(for .+? siden)(\s*·\s*Endret)?\s*")
TIME_AGO_SEARCH_RE = re.compile(r"for .+? siden")
BOILERPLATE_EXACT = {"Vis alle kommentarer", "Oversatt", "Vis mer", "Endret"}
BARE_NUMBER_RE = re.compile(r"^\d+$")
URL_RE = re.compile(r"https?://\S+")
# Denne juridiske fotnoteteksten dukker opp lenger ned/senere i dokumentet og
# skal ALDRI være del av et innlegg - stopp med en gang vi ser den.
HARD_STOP_RE = re.compile(r"^Kommentarene ovenfor kommer fra")


@dataclass
class ForumPost:
    key: str  # stable id, used for dedup across runs (author+text hash)
    author: str
    profile_url: str
    posted_relative: Optional[str]
    text: str
    reply_count: Optional[int] = None
    is_reply: bool = False
    engagement_numbers: List[int] = field(default_factory=list)
    links: List[str] = field(default_factory=list)
    char_count: int = 0
    has_link: bool = False


def resolve_url(stock: str) -> str:
    if stock.startswith("http://") or stock.startswith("https://"):
        return stock
    return BASE_URL.format(slug=stock)


def slug_from(stock: str) -> str:
    if stock.startswith("http://") or stock.startswith("https://"):
        return stock.rstrip("/").rsplit("/", 1)[-1]
    return stock


def fetch_html(url: str, session: requests.Session) -> str:
    resp = session.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.text


def compute_lca(elements):
    """Finn dypeste felles forelder for en liste med BeautifulSoup-elementer.
    Brukes til å isolere selve forumområdet uten å stole på bestemte
    klassenavn - alt vi vet er at forumlenkene deler en felles wrapper et
    sted, og den wrapperen er det vi vil hente teksten fra."""
    def ancestors(el):
        chain = []
        node = el
        while node is not None:
            chain.append(node)
            node = node.parent
        return list(reversed(chain))  # rot -> element

    chains = [ancestors(el) for el in elements]
    min_len = min(len(c) for c in chains)
    lca = None
    for i in range(min_len):
        if len({id(c[i]) for c in chains}) == 1:
            lca = chains[0][i]
        else:
            break
    return lca


def make_key(author: str, text: str) -> str:
    raw = f"{author}||{text}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def parse_post_lines(link, lines: List[str]) -> Optional[ForumPost]:
    author = link.get_text(strip=True)
    profile_url = urljoin("https://www.nordnet.no", link.get("href", ""))

    posted_relative = None
    body_lines = []
    engagement_numbers = []
    reply_count = None

    for line in lines:
        if line == author:
            continue
        if HARD_STOP_RE.match(line):
            break  # alt etter dette er juridisk fotnotetekst, ikke innleggsinnhold
        if TIME_AGO_RE.match(line):
            posted_relative = line
            continue
        m = TIME_AGO_PREFIX_RE.match(line)
        if m:
            # Tidspunkt (og evt. "· Endret") er limt sammen med selve
            # meldingsteksten på samme linje - skill dem fra hverandre.
            posted_relative = m.group(0).strip()
            remainder = line[m.end():].strip()
            if remainder:
                body_lines.append(remainder)
            continue
        if line in BOILERPLATE_EXACT:
            continue
        m = REPLY_RE.match(line)
        if m:
            reply_count = int(m.group(1))
            continue
        if SHOW_MORE_COMMENTS_RE.match(line):
            continue
        if BARE_NUMBER_RE.match(line):
            engagement_numbers.append(int(line))
            continue
        body_lines.append(line)

    text = " ".join(body_lines).strip()
    if not text:
        return None
    if len(text) > 3000:
        # Sikkerhetssperre: et ekte forum-innlegg er sjelden så langt - dette
        # er sannsynligvis nok et tegn på at grensededeteksjonen har feilet
        # og dratt med seg innhold den ikke skulle. Kutt av og flagg det.
        text = text[:3000] + " […avkuttet, sannsynlig parsingfeil]"

    # Vi har ikke lenger tilgang til de ekte <a href>-taggene i teksten (vi
    # jobber på flat tekst nå), så lenker fanges kun opp der de vises som
    # synlig URL-tekst i innlegget - det dekker det vanligste tilfellet vi
    # har sett på Nordnet (lenker limt inn som ren tekst).
    links = sorted(set(URL_RE.findall(text)))
    char_count = len(text)

    return ForumPost(
        key=make_key(author, text),
        author=author,
        profile_url=profile_url,
        posted_relative=posted_relative,
        text=text,
        reply_count=reply_count,
        is_reply=False,  # TODO: nøstet svar-deteksjon ikke implementert enda
        engagement_numbers=engagement_numbers,
        links=links,
        char_count=char_count,
        has_link=bool(links),
    )


def scrape_forum(url: str, session: requests.Session, debug: bool = False) -> List[ForumPost]:
    html = fetch_html(url, session)

    if debug:
        debug_path = "debug_" + re.sub(r"[^a-zA-Z0-9]+", "_", url) + ".html"
        with open(debug_path, "w", encoding="utf-8") as f:
            f.write(html)
        all_member_links_raw = re.findall(r'/aksjeforum/medlemmer/[^"\'\s]+', html)
        print(f"  [DEBUG] Lagret rå HTML til {debug_path}")
        print(f"  [DEBUG] Antall treff på /aksjeforum/medlemmer/ i rå HTML: {len(all_member_links_raw)}")

    soup = BeautifulSoup(html, "html.parser")
    all_member_links = soup.find_all("a", href=MEMBER_LINK_RE)
    name_links = [l for l in all_member_links if l.get_text(strip=True)]

    if not name_links:
        if debug:
            print("  [DEBUG] Fant ingen medlemslenker med synlig navnetekst.")
        return []

    forum_root = compute_lca(name_links) or soup
    lines = [l for l in forum_root.get_text("\n", strip=True).split("\n") if l]

    if debug:
        print(f"  [DEBUG] Antall navnelenker (ekskl. tomme avatar-lenker): {len(name_links)}")
        print(f"  [DEBUG] Felles forelder-tag for forumområdet: <{forum_root.name}> {forum_root.get('class')}")
        print(f"  [DEBUG] Antall tekstlinjer i forumområdet: {len(lines)}")

    # Finn hvor hver forfatters navn dukker opp i tekststrømmen, i rekkefølge.
    boundaries = []
    cursor = 0
    unmatched = 0
    for link in name_links:
        name = link.get_text(strip=True)
        idx = None
        for j in range(cursor, len(lines)):
            if lines[j] == name:
                idx = j
                break
        if idx is None:
            unmatched += 1
            idx = cursor  # fallback - gir et for kort/feil utsnitt, men stopper ikke resten
        boundaries.append(idx)
        cursor = idx + 1

    if debug and unmatched:
        print(f"  [DEBUG] Advarsel: fant ikke navnetekst i linjestrømmen for {unmatched} lenke(r) - kan gi noen tomme/feil innlegg.")

    posts: List[ForumPost] = []
    seen_keys: Set[str] = set()
    for i, link in enumerate(name_links):
        start = boundaries[i]
        end = boundaries[i + 1] if i + 1 < len(boundaries) else len(lines)
        post = parse_post_lines(link, lines[start:end])
        if post is None or post.key in seen_keys:
            continue
        seen_keys.add(post.key)
        posts.append(post)

    if debug:
        print(f"  [DEBUG] Antall unike innlegg trukket ut: {len(posts)}")
        for i, p in enumerate(posts):
            print(f"  [DEBUG]   {i}: {p.author} ({p.posted_relative}) [{p.char_count} tegn, lenker={len(p.links)}]: {p.text}")

    return posts


def load_state(state_path: str):
    """Returnerer (seen_keys, last_run_iso). Bakoverkompatibel med det gamle
    formatet (bare en liste med nøkler, ingen last_run kjent)."""
    if not os.path.exists(state_path):
        return set(), None
    with open(state_path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return set(), None
    if isinstance(data, list):
        return set(data), None  # gammelt format
    return set(data.get("keys", [])), data.get("last_run")


def save_state(state_path: str, keys: Set[str], last_run_iso: str) -> None:
    os.makedirs(os.path.dirname(state_path), exist_ok=True)
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump({"keys": sorted(keys), "last_run": last_run_iso}, f)


def main():
    parser = argparse.ArgumentParser(description="Scraper Nordnets forum-tab og finn nye innlegg siden sist kjøring.")
    parser.add_argument("stocks", nargs="*", help="Nordnet slug (f.eks. equinor-eqnr-xosl) eller full URL")
    parser.add_argument("--from-file", help="Tekstfil med én slug/URL per linje (f.eks. watchlist_mediumcap.txt), i tillegg til stocks")
    parser.add_argument("--data-dir", default="nordnet_data", help="Mappe for state og output (default: ./nordnet_data)")
    parser.add_argument("--delay", type=float, default=3.0, help="Sekunder mellom forespørsler (default 3.0 - økt fra 2.0 siden lista nå har mange flere aksjer)")
    parser.add_argument("--include-old", action="store_true", help="Ta med ALLE innlegg (ikke bare nye) i output")
    parser.add_argument("--debug", action="store_true", help="Lagre rå HTML og skriv ut diagnostikk for å feilsøke parsing")
    args = parser.parse_args()

    stock_list = list(args.stocks)
    if args.from_file:
        with open(args.from_file, "r", encoding="utf-8") as f:
            file_stocks = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        stock_list.extend(s for s in file_stocks if s not in stock_list)

    if not stock_list:
        parser.error("Ingen aksjer oppgitt - gi minst én slug/URL eller bruk --from-file")
    args.stocks = stock_list

    session = requests.Session()
    state_dir = os.path.join(args.data_dir, "state")
    latest_dir = os.path.join(args.data_dir, "latest")
    os.makedirs(state_dir, exist_ok=True)
    os.makedirs(latest_dir, exist_ok=True)

    all_new = {}

    for i, stock in enumerate(args.stocks):
        url = resolve_url(stock)
        slug = slug_from(stock)
        print(f"Henter forum for: {url}")
        try:
            posts = scrape_forum(url, session, debug=args.debug)
        except requests.RequestException as e:
            print(f"  Feil ved henting av {url}: {e}", file=sys.stderr)
            posts = []

        state_path = os.path.join(state_dir, f"{slug}.json")
        seen_keys, last_run = load_state(state_path)
        first_run = len(seen_keys) == 0
        now_iso = datetime.now(timezone.utc).isoformat()

        if last_run:
            gap_minutes = (datetime.now(timezone.utc) - datetime.fromisoformat(last_run)).total_seconds() / 60
            if gap_minutes > 180:  # mer enn 3 timer siden sist - kan ha rukket å bli fullt
                print(f"  [MERK] {gap_minutes:.0f} min siden forrige kjøring for {slug} - "
                      f"innlegg kan ha rukket å bli skjøvet under det synlige vinduet.")

        new_posts = [p for p in posts if p.key not in seen_keys]
        # Prioriter: lenke-innlegg først, deretter lengst tekst (ofte mer
        # data/substans enn ett-linjers magefølelses-kommentarer).
        new_posts.sort(key=lambda p: (not p.has_link, -p.char_count))
        seen_keys.update(p.key for p in posts)
        save_state(state_path, seen_keys, now_iso)

        output_posts = posts if args.include_old else new_posts
        out_path = os.path.join(latest_dir, f"{slug}_new.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump({
                "slug": slug,
                "url": url,
                "scraped_at": datetime.now(timezone.utc).isoformat(),
                "first_run": first_run,
                "total_posts_on_page": len(posts),
                "new_posts_count": len(new_posts),
                "posts": [asdict(p) for p in output_posts],
            }, f, ensure_ascii=False, indent=2)

        first_run_posts = sorted(posts, key=lambda p: (not p.has_link, -p.char_count))
        this_run_new = first_run_posts if first_run else new_posts
        all_new[slug] = [asdict(p) for p in this_run_new]

        if this_run_new:
            pending_path = os.path.join(latest_dir, "pending_for_claude.json")
            pending = {}
            if os.path.exists(pending_path):
                try:
                    with open(pending_path, "r", encoding="utf-8") as f:
                        pending = json.load(f)
                except json.JSONDecodeError:
                    pending = {}
            existing_keys = {p["key"] for p in pending.get(slug, [])}
            merged = pending.get(slug, []) + [asdict(p) for p in this_run_new if p.key not in existing_keys]
            pending[slug] = merged
            with open(pending_path, "w", encoding="utf-8") as f:
                json.dump(pending, f, ensure_ascii=False, indent=2)

        if first_run:
            print(f"  Første kjøring for {slug}: lagret {len(posts)} innlegg som kjent (ingen 'nye' å varsle om ennå).")
        else:
            print(f"  {slug}: {len(new_posts)} nye innlegg siden forrige kjøring (av {len(posts)} totalt på siden).")
        for p in new_posts:
            prefix = "    ↳ " if p.is_reply else "    - "
            print(f"{prefix}{p.author} ({p.posted_relative}): {p.text}")

        if i < len(args.stocks) - 1:
            time.sleep(args.delay)

    combined_path = os.path.join(latest_dir, "all_new.json")
    with open(combined_path, "w", encoding="utf-8") as f:
        json.dump(all_new, f, ensure_ascii=False, indent=2)
    print(f"\nSamlet resultat (nye innlegg per aksje): {combined_path}")


if __name__ == "__main__":
    main()
