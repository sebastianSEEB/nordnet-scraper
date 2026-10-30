"""
Innsidehandler fra børsmeldingene (Newsweb) -> strukturerte handler
==================================================================
Leser meldingene som news_ml/fetch_news.py allerede har hentet
(nordnet_data/news/messages_*.jsonl, kind == "insider") og trekker ut:

    retning     +1 kjøp, -1 salg, 0 ukjent/ikke en markedshandel
    antall      antall aksjer i selve handelen (ikke beholdningen etterpå)
    kurs        snittkurs per aksje
    verdi_nok   antall * kurs, omregnet grovt til NOK
    rolle       CEO / CFO / styreleder / styremedlem / ledelse / annet
    støy        True for spareprogram, opsjoner, aksjeprogram, selskapets egne
                aksjer, utlån, pant, gave/arv osv. - ikke et "jeg tror på aksjen"-kjøp

Parsingen er regelbasert og gjør feil på rare meldinger. Det er greit:
handler der vi ikke finner antall eller kurs får verdi_nok = None og blir
filtrert bort av strategien, i stedet for å gjette.
"""

import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from news_ml.common import FX, NEWS_DIR, insider_direction  # noqa: E402

NOISE_RE = re.compile(
    r"spareprogram|spareordning|aksjespareprogram|share savings|savings (plan|program)|employee share|"
    r"\bansatte\b|\bemployees\b|aksjeprogram for|share purchase (plan|program)|incentive|\blti\b|\brsus?\b|\bpsus?\b|"
    r"(exercise|exercised|utøv\w*) .{0,40}(option|opsjon|warrant|tegningsrett)|"
    r"\b(grant|allocat|tildel)\w* .{0,40}(option|opsjon|share|aksje|\brsu|\bpsu)|"
    r"own shares|egne aksjer|egne egenkapitalbevis|egne bevis|treasury shares|"
    r"share lending|aksjelån|lån av aksjer|securities lending|pledge|pantsat|"
    r"\bgift\b|\bgave\b|inheritance|\barv\b|dividend reinvestment|\bscrip\b|"
    r"subscri\w+ .{0,40}(private placement|offering|emisjon)|tegnet .{0,40}emisjon|"
    r"rights issue|fortrinnsrett|bonus shares|share split|compensation package|remuneration|godtgjørelse|"
    r"styrehonorar|board fee|as part of (his|her|their) (fee|salary)",
    re.I,
)
# Selskapet selv som kjøper (spareprogram-meldinger o.l.) - "SpareBank 1 SMN har 29. oktober kjøpt ..."
COMPANY_BUYS_RE = re.compile(r"^\s*[A-ZÆØÅ][\w .&-]{1,60}(ASA|AS|ASA's)? (har|has) (\d{1,2}\.? \w+ )?(kjøpt|purchased|bought)", re.M)

ROLE_RULES = [
    ("CEO", r"\b(ceo|chief executive|administrerende direktør|adm\.? dir|konsernsjef|daglig leder|"
            r"president and ceo|managing director)\b"),
    ("CFO", r"\b(cfo|chief financial|finansdirektør|økonomidirektør)\b"),
    ("Styreleder", r"\b(chair(man|person|woman)? of the board|board chair|styreleder|styrets leder|chair)\b"),
    ("Styremedlem", r"\b(board member|member of the board|director of the board|styremedlem|non-executive director|"
                    r"close associate of .{0,40}board)\b"),
    ("Ledelse", r"\b(chief \w+ officer|c[otsi]o\b|evp|svp|vp\b|executive vice|direktør|director|"
                r"head of|primary insider|primærinnsider|member of (the )?(executive )?management|konsernledelse)\b"),
]
_ROLE_RE = [(r, re.compile(p, re.I)) for r, p in ROLE_RULES]

VERB_RE = re.compile(r"\b(bought|purchased|acquired|sold|disposed|kjøpt|kjøpte|solgt|solgte|"
                     r"buy|sell|purchase|sale of|salg av|kjøp av)\b", re.I)
AFTER_RE = re.compile(r"(following|after|etter) (this|the|these|denne|disse|handelen|transaksjonen)|"
                      r"\b(holds|owns|eier|innehar|beholdning|total holding|holding of)\b", re.I)

NUM = r"\d[\d\s,. ]*\d|\d"
SHARES_RE = re.compile(rf"({NUM})\s*(?:(?:new|ordinary|class [ab]|a-|b-|nye|ordinære|additional)\s*)?"
                       rf"(shares|aksjer|egenkapitalbevis|bevis|depository receipts|units)\b", re.I)
MONTHS = (r"jan\w*|feb\w*|mar\w*|apr\w*|ma[iy]|jun\w*|jul\w*|aug\w*|sep\w*|o[ck]t\w*|nov\w*|de[cs]\w*")
DATE_RE = re.compile(rf"\b\d{{1,2}}[./-]\d{{1,2}}[./-]\d{{2,4}}\b|\b\d{{4}}-\d{{2}}-\d{{2}}\b|"
                     rf"\b\d{{1,2}}\.?\s+(?:{MONTHS})\s+(?:19|20)\d{{2}}\b|\b(?:{MONTHS})\s+\d{{1,2}},?\s+(?:19|20)\d{{2}}\b|"
                     rf"\b(?:19|20)\d{{2}}\b(?=\s*[,.:]?\s*(?!shares|aksjer))", re.I)
CURR = r"(NOK|USD|EUR|SEK|DKK|GBP|kr\.?|kroner)"
PRICE_RES = [
    # "at an average price of NOK 31.46" / "til kurs 218,53 kroner" / "price per share of NOK 84.9"
    re.compile(rf"(?:price|pris|kurs|kurser)\b[^0-9\n]{{0,40}}?{CURR}?\s*({NUM})\s*{CURR}?", re.I),
    # "NOK 31.46 per share" / "31,46 kroner per aksje"
    re.compile(rf"{CURR}\s*({NUM})\s*(?:per|pr\.?|/)\s*(share|aksje|bevis)", re.I),
    re.compile(rf"({NUM})\s*{CURR}\s*(?:per|pr\.?|/)\s*(share|aksje|bevis)", re.I),
]


def _clean(s):
    return s.replace(" ", " ").strip().rstrip(".,")


def parse_count(s):
    """Antall aksjer: separatorer er alltid tusenskille ('30,000', '24.318', '1 250 000')."""
    s = _clean(s)
    digits = re.sub(r"[\s,.]", "", s)
    return int(digits) if digits.isdigit() else None


def parse_price(s):
    """Kurs: '31.46', '218,53', '1,250.50', '1.250,50', '0.125', '1 250'."""
    s = re.sub(r"\s", "", _clean(s))
    if "," in s and "." in s:
        dec = "," if s.rfind(",") > s.rfind(".") else "."
        s = s.replace("." if dec == "," else ",", "").replace(dec, ".")
    elif s.count(",") + s.count(".") == 1:
        sep = "," if "," in s else "."
        whole, frac = s.split(sep)
        # Snittkurser har ofte 3 desimaler ("NOK 8.295"), så én separator tolkes som desimal.
        # Den sjeldne "NOK 1,250" (tusenskille) rettes i paper.py ved å sjekke mot faktisk kurs.
        s = whole + "." + frac
    elif s.count(",") + s.count(".") > 1:
        s = re.sub(r"[,.]", "", s)
    try:
        return float(s)
    except ValueError:
        return None


def _currency(tok):
    if not tok:
        return "NOK"
    tok = tok.upper().rstrip(".")
    return "NOK" if tok in ("KR", "KRONER") else tok


def find_price(text):
    for rx in PRICE_RES:
        for m in rx.finditer(text):
            groups = [g for g in m.groups() if g]
            num = next((g for g in groups if re.match(r"\d", g)), None)
            cur = next((g for g in groups if re.match(r"(?i)nok|usd|eur|sek|dkk|gbp|kr", g)), None)
            p = parse_price(num) if num else None
            if p and 0.001 <= p <= 100000:
                return p, _currency(cur)
    return None, None


def detect_role(text):
    head = text[:900]  # rollen står nesten alltid i første avsnitt
    for role, rx in _ROLE_RE:
        if rx.search(head):
            return role
    return "Annet"


def sentences(text):
    return [s for s in re.split(r"(?<=[.;:])\s+(?=[A-ZÆØÅ])|\n{2,}", text.replace("\n", " ")) if s.strip()]


def parse_trade(msg):
    title = msg.get("title") or ""
    body = DATE_RE.sub(" DATO ", msg.get("body") or "")
    text = f"{title}\n{body}"
    direction = insider_direction(text)
    noise = bool(NOISE_RE.search(text)) or bool(COMPANY_BUYS_RE.search(body))

    shares_total, value_total, prices = 0, 0.0, []
    fallback_price, fallback_cur = find_price(body)
    for s in sentences(body):
        if not VERB_RE.search(s):
            continue
        # Skjær bort "... Following this transaction X holds 76,995 shares" fra setningen
        cut = AFTER_RE.search(s)
        part = s[:cut.start()] if cut else s
        m = SHARES_RE.search(part)
        if not m:
            continue
        n = parse_count(m.group(1))
        if not n or n > 5e9:
            continue
        p, cur = find_price(part)
        if p is None:
            p, cur = fallback_price, fallback_cur
        if p is None:
            continue
        shares_total += n
        value_total += n * p * FX.get(cur or "NOK", 1.0)
        prices.append(p)

    return {
        "id": msg.get("id"),
        "published": msg.get("published"),
        "issuer": msg.get("issuer"),
        "issuer_name": msg.get("issuer_name"),
        "title": title,
        "direction": direction,
        "role": detect_role(text),
        "shares": shares_total or None,
        "price": round(sum(prices) / len(prices), 4) if prices else None,
        "value_nok": round(value_total) if value_total else None,
        "noise": noise,
        "has_body": bool(body),
    }


def load_trades(news_dir=NEWS_DIR):
    out = []
    for path in sorted(glob.glob(os.path.join(news_dir, "messages_*.jsonl"))):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                m = json.loads(line)
                if m.get("kind") == "insider" and m.get("body"):
                    out.append(parse_trade(m))
    out.sort(key=lambda t: t["published"] or "")
    # Mange selskaper sender samme melding på norsk og engelsk -> behold én
    seen, uniq = set(), []
    for t in out:
        k = (t["issuer"], (t["published"] or "")[:10], t["direction"], t["shares"])
        if t["shares"] and k in seen:
            continue
        seen.add(k)
        uniq.append(t)
    return uniq


if __name__ == "__main__":
    trades = load_trades()
    good = [t for t in trades if t["direction"] == 1 and not t["noise"] and t["value_nok"]]
    print(f"{len(trades)} innsidemeldinger med tekst, {len(good)} rene markedskjøp med beløp")
    for t in trades[-15:]:
        print(t["published"][:10], t["issuer"], t["direction"], t["role"], t["shares"], t["price"],
              t["value_nok"], "STØY" if t["noise"] else "")
