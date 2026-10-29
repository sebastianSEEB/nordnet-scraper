"""Felles hjelpefunksjoner for news_ml: univers, stier og tolking av børsmeldinger."""

import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.environ.get("NEWS_ML_DATA", os.path.join(ROOT, "nordnet_data"))
NEWS_DIR = os.path.join(DATA_DIR, "news")
OUT_DIR = os.path.join(DATA_DIR, "news_ml")
PRICE_DIR = os.path.join(DATA_DIR, "news_ml_prices")
WATCHLIST = os.environ.get("NEWS_ML_WATCHLIST", os.path.join(ROOT, "watchlist_full.txt"))
OVERRIDES = os.path.join(ROOT, "ticker_overrides.json")
BENCHMARK = "_benchmark"


def slug_to_ticker(slug):
    parts = slug.split("-")
    base = parts[-2] if len(parts) > 2 else parts[0]
    return f"{base.upper()}.OL"


def load_universe():
    """Watchlisten -> [{slug, ticker, issuer}] uten duplikater."""
    overrides = {}
    if os.path.exists(OVERRIDES):
        with open(OVERRIDES, encoding="utf-8") as f:
            overrides = {k: v for k, v in json.load(f).items() if not k.startswith("_")}
    seen, out = set(), []
    with open(WATCHLIST, encoding="utf-8") as f:
        for line in f:
            slug = line.strip()
            if not slug or slug.startswith("#") or slug in seen:
                continue
            seen.add(slug)
            ticker = overrides.get(slug, slug_to_ticker(slug))
            out.append({"slug": slug, "ticker": ticker, "issuer": ticker.split(".")[0].upper()})
    return out


# ---------------------------------------------------------------- klassifisering
# Rekkefølgen betyr noe: første treff vinner.
KIND_RULES = [
    ("insider", r"primary insider|primærinnsider|mandatory notification of trade|meldepliktig handel|"
                r"notification of trade|pdmr|person(s)? discharging managerial"),
    ("calendar", r"invitation|invitasjon|financial calendar|finansiell kalender|reminder|påminnelse|webcast"),
    ("buyback", r"buy[- ]?back|share repurchase|tilbakekjøp|kjøp av egne aksjer|purchase of own shares"),
    ("report", r"\b(q[1-4]|first|second|third|fourth)[ -]?(quarter|qtr)?\b.*(result|report|presentation|interim)|"
               r"\bkvartal|interim report|half[- ]year|halvår|annual report|årsrapport|"
               r"quarterly (results|report)|(q[1-4]|h[12]) 20\d\d"),
    ("guidance", r"guidance|outlook|profit warning|resultatvarsel|trading update|preliminary"),
    ("contract", r"contract|kontrakt|award|tildel|order\b|ordre|letter of intent|\bloi\b|framework agreement|"
                 r"rammeavtale|charter|befraktning|time ?charter|secures|signs|signed|selected|wins"),
    ("mna", r"acqui|oppkjøp|merger|fusjon|takeover|tender offer|bud på|voluntary offer|mandatory offer|"
            r"strategic review|divest"),
    ("dividend", r"dividend|utbytte|ex[- ]date"),
    ("financing", r"private placement|rettet emisjon|share issue|emisjon|bond issue|obligasjon|rights issue|"
                  r"subsequent offering|convertible"),
]
_KIND_RE = [(k, re.compile(p, re.I)) for k, p in KIND_RULES]


def classify(title, category=""):
    t = f"{title} || {category}"
    if re.search(r"mandatory notification of trade|primary insider", category or "", re.I):
        return "insider"
    for kind, rx in _KIND_RE:
        if rx.search(t):
            return kind
    return "other"


# ---------------------------------------------------------------- beløp
# Grove faste kurser til NOK - godt nok til "hvor stor er kontrakten", ikke regnskap.
FX = {"NOK": 1.0, "USD": 10.5, "EUR": 11.5, "GBP": 13.5, "SEK": 1.0, "DKK": 1.55, "CHF": 12.0}
SCALE = {"billion": 1e9, "bn": 1e9, "milliard": 1e9, "milliarder": 1e9, "mrd": 1e9, "bnok": 1e9,
         "million": 1e6, "mill": 1e6, "mln": 1e6, "m": 1e6, "mnok": 1e6, "millioner": 1e6,
         "thousand": 1e3, "k": 1e3}
_NUM = r"(\d{1,3}(?:[ ,.]\d{3})*(?:[.,]\d+)?|\d+(?:[.,]\d+)?)"
_AMT_RES = [
    # NOK 11.5 billion / USD 54 million / EUR 140m
    re.compile(rf"\b(NOK|USD|EUR|GBP|SEK|DKK|CHF|US\$|\$|€)\s*{_NUM}\s*(billion|bn|million|mill|mln|m)\b", re.I),
    # MNOK 500 / BNOK 1,2
    re.compile(rf"\b(MNOK|BNOK|MUSD|MEUR)\s*{_NUM}", re.I),
    # 11,5 milliarder kroner / 500 millioner kroner / 1.7 billion NOK
    re.compile(rf"{_NUM}\s*(milliarder|milliard|mrd\.?|millioner|mill\.?|billion|million)\s*(kroner|nok|usd|dollar|euro|eur)",
               re.I),
]


def _num(s):
    s = s.strip()
    if re.fullmatch(r"\d{1,3}([ ,.]\d{3})+", s):  # tusenskille
        return float(re.sub(r"[ ,.]", "", s))
    return float(s.replace(" ", "").replace(",", "."))


def parse_amount_nok(text):
    """Største beløp nevnt i teksten, i NOK. None hvis ingen."""
    best = None
    for rx in _AMT_RES:
        for m in rx.finditer(text or ""):
            g = m.groups()
            try:
                if rx is _AMT_RES[0]:
                    cur = {"US$": "USD", "$": "USD", "€": "EUR"}.get(g[0], g[0].upper())
                    val = _num(g[1]) * SCALE[g[2].lower().rstrip(".")]
                elif rx is _AMT_RES[1]:
                    code = g[0].upper()
                    cur = {"MNOK": "NOK", "BNOK": "NOK", "MUSD": "USD", "MEUR": "EUR"}[code]
                    val = _num(g[1]) * (1e9 if code == "BNOK" else 1e6)
                else:
                    unit = g[1].lower().rstrip(".")
                    cur = {"kroner": "NOK", "nok": "NOK", "usd": "USD", "dollar": "USD", "euro": "EUR",
                           "eur": "EUR"}[g[2].lower()]
                    val = _num(g[0]) * SCALE.get(unit, 1e6)
            except (ValueError, KeyError):
                continue
            nok = val * FX.get(cur, 1.0)
            if 1e5 <= nok <= 5e12 and (best is None or nok > best):
                best = nok
    return best


def insider_direction(text):
    """+1 kjøp, -1 salg, 0 ukjent (f.eks. tildeling av opsjoner)."""
    t = (text or "").lower()
    if re.search(r"\b(allocat|grant|tildel|share[- ]based|incentive|lti|rsu|options? (were|was)? ?(granted|allocated))", t):
        if not re.search(r"\b(bought|purchased|kjøpt|acquired)\b", t):
            return 0
    buy = len(re.findall(r"\b(bought|purchased|purchase of|kjøpt|kjøp av|acquired|acquisition of)\b", t))
    sell = len(re.findall(r"\b(sold|sale of|solgt|salg av|disposed)\b", t))
    if buy > sell:
        return 1
    if sell > buy:
        return -1
    return 0
