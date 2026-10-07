"""Connects Ripple to the Nordnet forum scraper (github.com/sebastianSEEB/nordnet-scraper).

Pulled automatically from the repo, no setup needed:
  - watchlist_full.txt       -> extra Oslo stocks added to the network
  - maritime_segments.json   -> companies in the same segment get linked
  - nordnet_data/signals.jsonl -> AI-scored forum sentiment, used as news triggers
Files are cached locally so Ripple still works if GitHub is unreachable.
"""
import json
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

from config import ROOT, UNIVERSE, SEED_LINKS

RAW = "https://raw.githubusercontent.com/sebastianSEEB/nordnet-scraper/main/"
CACHE = ROOT / "nordnet_cache"
EXCH = {"xosl": ".OL", "xoas": ".OL", "merk": ".OL"}
SEGMENT_NAMES = {
    "tank_raaolje": "Crude tankers", "tank_produkt_kjemikalier": "Product tankers",
    "gass": "Gas carriers", "toerrbulk": "Dry bulk", "container": "Container",
    "bilfrakt_roro": "Car carriers", "offshore_spesialisert": "Offshore",
}


def _fetch(path):
    CACHE.mkdir(exist_ok=True)
    local = CACHE / path.replace("/", "_")
    try:
        r = requests.get(RAW + path, timeout=20)
        if r.ok:
            local.write_text(r.text, encoding="utf-8")
            return r.text
    except requests.RequestException:
        pass
    return local.read_text(encoding="utf-8") if local.exists() else ""


def slug_to_ticker(slug):
    parts = slug.split("-")
    if len(parts) < 2 or parts[-1] not in EXCH:
        return None, None
    tk = parts[-2].upper() + EXCH[parts[-1]]
    name = " ".join(parts[:-2]) or parts[0]
    return tk, re.sub(r"(?<=[a-z])0", ".", name).title()


def load(offline=False):
    """Returns (universe, seed_links, slug->ticker map)."""
    universe = dict(UNIVERSE)
    links = list(SEED_LINKS)
    slug_map = {}
    if offline:
        return universe, links, slug_map

    seg_text = _fetch("maritime_segments.json")
    segments = json.loads(seg_text) if seg_text else {}
    slug_sector = {}
    for key, seg in segments.items():
        if not isinstance(seg, dict):
            continue
        name = SEGMENT_NAMES.get(key, key.replace("_", " ").capitalize())
        tks = []
        for slug in seg.get("aksjer", []):
            slug_sector[slug] = name
            tk, _ = slug_to_ticker(slug)
            if tk:
                tks.append(tk)
        links += [(a, b, +1) for a in tks for b in tks if a != b]

    for line in _fetch("watchlist_full.txt").splitlines():
        slug = line.strip()
        if not slug or slug.startswith("#"):
            continue
        tk, name = slug_to_ticker(slug)
        if not tk:
            continue
        slug_map[slug] = tk
        if tk not in universe:
            universe[tk] = (name, slug_sector.get(slug, "Oslo Børs"))
    return universe, links, slug_map


def signals(slug_map):
    """Forum sentiment rows shaped like headlines:
    (id, date, ticker, title, link, sentiment, source)."""
    text = _fetch("nordnet_data/signals.jsonl")
    rows = []
    for line in text.splitlines():
        try:
            s = json.loads(line)
        except json.JSONDecodeError:
            continue
        tk = slug_map.get(s.get("slug")) or slug_to_ticker(s.get("slug", ""))[0]
        if not tk:
            continue
        ts = datetime.fromisoformat(s["analyzed_at"].replace("Z", "+00:00"))
        date = ts.astimezone(ZoneInfo("Europe/Oslo")).strftime("%Y-%m-%d")
        strength = s.get("signal_strength", "Signal")
        title = f"Nordnet forum ({strength}): {s.get('summary', '')}"
        rows.append((f"nn-{s['analyzed_at']}-{s['slug']}", date, tk, title,
                     "https://www.nordnet.no/aksjer/kurser/" + s["slug"],
                     float(s.get("sentiment", 0)), "nordnet"))
    return rows
