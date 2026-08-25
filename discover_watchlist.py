#!/usr/bin/env python3
"""
Discover & validate a watchlist of medium-cap ("medium store") Norwegian
stocks on Nordnet.

WHY THIS EXISTS
Nordnet's full aksjeliste (12 256+ rows, incl. certificates/warranter) is
paginated via JavaScript, not a simple URL parameter - so it can't be
scraped page-by-page with plain requests. What we DO have is a verified
snapshot of the ~100 most-traded Norwegian companies (pulled 21 aug 2026),
filtered down to a "medium" market-cap band (~3-80 mrd NOK børsverdi),
excluding both mega-caps (Equinor, DNB, ...) and micro-caps.

Most of the URL slugs below are BEST-GUESS, built from the pattern seen on
confirmed pages: {selskapsnavn}-{ticker}-{marked}. A handful are already
verified (marked). Since guessing 67 slugs by hand is bound to have a few
misses, this script VALIDATES every URL itself (checks for HTTP 200 and a
"Forum" section) before writing anything to the final watchlist - so wrong
guesses get dropped automatically instead of silently breaking the scraper.

Usage:
    pip install requests
    python discover_watchlist.py
    # writes watchlist_mediumcap.txt (validated slugs) and
    # watchlist_mediumcap_failed.txt (guesses that didn't resolve, for
    # manual lookup)

Then feed the result into the main scraper:
    python nordnet_forum_scraper.py $(cat watchlist_mediumcap.txt) --data-dir nordnet_data
"""

import re
import sys
import time
import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "nb-NO,nb;q=0.9,no;q=0.8,en;q=0.7",
}
BASE_URL = "https://www.nordnet.no/aksjer/kurser/{slug}"

# (display name, best-guess slug, market cap MNOK, confirmed?)
# Market cap figures are a snapshot from 21 aug 2026 - only used for the
# medium-cap filter, not kept up to date.
CANDIDATES = [
    ("Höegh Autoliners", "hoegh-autoliners-hauto-xosl", 36037, True),
    ("BlueNord", "blue-nord-bnor-xosl", 13509, True),
    ("Nordic Semiconductor", "nordic-semiconductor-nod-xosl", 32355, False),
    ("Wallenius Wilhelmsen", "wallenius-wilhelmsen-wawi-xosl", 70315, True),
    ("Norwegian Air Shuttle", "norwegian-air-shuttle-nas-xosl", 13597, False),
    ("BW LPG", "bw-lpg-bwlpg-xosl", 33251, True),
    ("Link Mobility Group Holding", "link-mobility-group-holding-link-xosl", 8009, False),
    ("DNO", "dno-dno-xosl", 18115, False),
    ("Autostore Holdings", "autostore-holdings-store-xosl", 54292, False),
    ("Salmar", "salmar-salm-xosl", 69036, False),
    ("Vend Marketplaces", "vend-marketplaces-vend-xosl", 51043, False),
    ("Zaptec", "zaptec-zap-xosl", 4124, False),
    ("Kitron", "kitron-kit-xosl", 19450, False),
    ("Kongsberg Maritime", "kongsberg-maritime-kogm-xosl", 47974, False),
    ("Panoro Energy", "panoro-energy-pen-xosl", 3793, False),
    ("Tomra Systems", "tomra-systems-tom-xosl", 31383, False),
    ("DOF Group", "dof-group-dofg-xosl", 32956, False),
    ("Hafnia Limited", "hafnia-hafni-xosl", 35751, True),
    ("Okeanis Eco Tankers", "okeanis-eco-tankers-oet-xosl", 22238, True),
    ("Capital Tankers Corp.", "capital-tankers-corp-capt-merk", 20657, True),
    ("MPC Container Ships", "mpc-container-ships-mpcc-xosl", 12491, True),
    ("Protector Forsikring", "protector-forsikring-prot-xosl", 39271, False),
    ("Lerøy Seafood Group", "leroy-seafood-group-lsg-xosl", 24712, False),
    ("Norbit", "norbit-norbt-xosl", 10986, False),
    ("TGS", "tgs-tgs-xosl", 26848, False),
    ("Scatec", "scatec-scatc-xosl", 15184, False),
    ("CMB.Tech NV", "cmb0tech-nv-cmbto-xosl", 47189, True),
    ("Elkem", "elkem-elk-xosl", 12182, False),
    ("Himalaya Shipping", "himalaya-shipping-hshp-xosl", 7060, False),
    ("Endúr", "endur-endur-xosl", 5613, False),
    ("Odfjell Drilling", "odfjell-drilling-odl-xosl", 22746, False),
    ("Constellation Oil Services", "constellation-oil-services-holding-cosh-xosl", 11573, False),
    ("Hexagon Composites", "hexagon-composites-hexa-xosl", 4539, False),
    ("Aker Solutions", "aker-solutions-akso-xosl", 21258, False),
    ("B2 Impact", "b2-impact-b2i-xosl", 9550, False),
    ("Bakkafrost", "bakkafrost-bakka-xosl", 28051, False),
    ("Norconsult", "norconsult-norco-xosl", 11376, False),
    ("Paratus Energy Services", "paratus-energy-services-plsv-xosl", 8017, False),
    ("OKEA", "okea-okea-xosl", 3948, False),
    ("Napatech", "napatech-napa-xosl", 4784, False),
    ("Cadeler", "cadeler-cadlr-xosl", 21322, False),
    ("SED Energy Holdings", "sed-energy-holdings-enh-xosl", 4865, True),
    ("Europris", "europris-epr-xosl", 13844, False),
    ("SATS", "sats-sats-xosl", 9027, False),
    ("Norske Skog", "norske-skog-nsg-xosl", 3822, False),
    ("SpareBank 1 Nord-Norge", "sparebank-1-nord-norge-nonge-xosl", 16903, False),
    ("SpareBank 1 Østlandet", "sparebank-1-ostlandet-spol-xosl", 26002, False),
    ("Sparebanken Norge", "sparebanken-norge-spare-xosl", 33953, False),
    ("Wilh. Wilhelmsen Holding A", "wilh-wilhelmsen-holding-wwi-xosl", 32811, False),
    ("Austevoll Seafood", "austevoll-seafood-auss-xosl", 16812, False),
    ("SpareBank 1 SMN", "sparebank-1-smn-ming-xosl", 29070, False),
    ("Bouvet", "bouvet-bouv-xosl", 4380, False),
    ("Veidekke", "veidekke-vei-xosl", 27599, False),
    ("BW Energy", "bw-energy-bwe-xosl", 14671, False),
    ("Elopak", "elopak-elo-xosl", 9154, False),
    ("Moreld", "moreld-morld-xosl", 3914, False),
    ("Atea", "atea-atea-xosl", 19569, False),
    ("Kid", "kid-kid-xosl", 5341, False),
    ("Grieg Seafood", "grieg-seafood-gsf-xosl", 3281, False),
    ("Akastor", "akastor-aka-xosl", 3775, False),
    ("Stolt-Nielsen", "stolt-nielsen-sni-xosl", 16962, False),
    ("Borregaard", "borregaard-borg-xosl", 15573, False),
    ("Solstad Offshore", "solstad-offshore-soff-xosl", 5708, False),
    ("SoftwareOne Holding", "softwareone-holding-swon-xosl", 21862, False),
    ("Pexip Holding", "pexip-holding-pexip-xosl", 7889, False),
    ("Medistim", "medistim-medi-xosl", 4298, False),
]


def validate_slug(slug: str, session: requests.Session) -> bool:
    """Return True if the slug resolves to a real Nordnet instrument page."""
    url = BASE_URL.format(slug=slug)
    try:
        resp = session.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
    except requests.RequestException:
        return False
    if resp.status_code != 200:
        return False
    # A real instrument page has a "Forum" heading; a 200 soft-404 landing
    # page usually won't.
    return "Forum" in resp.text


def main():
    session = requests.Session()
    valid, failed = [], []

    for name, slug, mcap, confirmed in CANDIDATES:
        if confirmed:
            print(f"✓ {name:35s} (already confirmed)")
            valid.append(slug)
            continue
        ok = validate_slug(slug, session)
        status = "✓" if ok else "✗"
        print(f"{status} {name:35s} {slug}")
        (valid if ok else failed).append((name, slug) if not ok else slug)
        time.sleep(1.0)  # be polite to Nordnet's servers

    with open("watchlist_mediumcap.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(valid) + "\n")

    if failed:
        with open("watchlist_mediumcap_failed.txt", "w", encoding="utf-8") as f:
            for name, slug in failed:
                f.write(f"{name}\t{slug}\n")

    print(f"\n{len(valid)} validated slugs written to watchlist_mediumcap.txt")
    if failed:
        print(f"{len(failed)} guesses failed - see watchlist_mediumcap_failed.txt "
              f"(look up the correct slug manually on nordnet.no and add it "
              f"to watchlist_mediumcap.txt)")


if __name__ == "__main__":
    main()
