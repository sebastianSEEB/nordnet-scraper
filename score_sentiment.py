#!/usr/bin/env python3
"""
Sentiment-score for hvert forum-innlegg (Claude Haiku)
======================================================
Leser arkivet (nordnet_data/archive/), finner innlegg som ikke er scoret
ennå, og ber Claude gi hvert innlegg:

    s  sentiment mot aksjen:  -1.0 (sterkt negativt) .. 0 .. +1.0 (sterkt positivt)
    r  relevans:               0.0 (off-topic)       ..        1.0 (direkte om selskapet)
    c  kategori:               nyhet | analyse | mening | spørsmål | humor | offtopic

Resultat legges til (append) i nordnet_data/sentiment/scores.jsonl, én linje
per innlegg. Scriptet er inkrementelt og kan avbrytes og startes igjen - det
scorer aldri samme innlegg to ganger.

Hvorfor relevans i tillegg til sentiment? Mange innlegg er småprat eller
handler om noe helt annet (makro, andre aksjer, krangling). Uten relevans
ville "Hva skjedde i 2008?" telle like mye som "Ny kontrakt på 2 mrd".

Kostnad: innleggene sendes i grupper (30 om gangen, per aksje), så prompten
deles av mange innlegg. Bruk --dry-run for å se omtrentlig tokenmengde før du
kjører, og --max-posts for å sette et tak.

Krever: ANTHROPIC_API_KEY (samme GitHub-hemmelighet som analyze_and_report.py)
Modell: miljøvariabel SENTIMENT_MODEL (standard claude-haiku-5-5)

Bruk:
    python score_sentiment.py --dry-run
    python score_sentiment.py --max-posts 500     # test på et utvalg
    python score_sentiment.py                     # alt som mangler
"""

import argparse
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Dict, List, Optional

import requests

from archive_posts import DATE_PREFIX_RE, iter_archive

MODEL = os.environ.get("SENTIMENT_MODEL", "claude-haiku-5-5")
API_URL = "https://api.anthropic.com/v1/messages"
CATEGORIES = {"nyhet", "analyse", "mening", "spørsmål", "humor", "offtopic"}
MAX_TEXT_CHARS = 1200
MIN_TEXT_CHARS = 8
DELETED_RE = re.compile(r"^innlegget er slettet\.?$", re.IGNORECASE)
NOISE_RE = re.compile(r"\s*Vis \d+ (kommentar(er)?|svar)( til)?\s*$")
PREFIX_NOISE_RE = re.compile(r"^[\s·]*(Endret)?[\s·]*")

_write_lock = threading.Lock()


# ------------------------------------------------------------- hjelpere

def company_from_slug(slug: str) -> (str, str):
    """'frontline-fro-xosl' -> ('Frontline', 'FRO')"""
    parts = slug.split("-")[:-1]  # dropp markedsplass (xosl/xoas/merk)
    if len(parts) >= 2:
        ticker, name_parts = parts[-1], parts[:-1]
    else:
        ticker, name_parts = parts[0], parts
    name = " ".join(name_parts)
    name = re.sub(r"(?<=[a-z])0", ".", name)  # Nordnet skriver "." som "0": wilh0 -> wilh.
    return name.title(), ticker.upper()


def clean_text(text: str) -> str:
    """Fjerner dato-prefiks, 'Endret' og 'Vis N kommentarer til' som scraperen
    noen ganger limer inn i teksten."""
    t = text or ""
    m = DATE_PREFIX_RE.match(t)
    if m:
        t = t[m.end():]
    t = PREFIX_NOISE_RE.sub("", t, count=1)
    t = NOISE_RE.sub("", t).strip()
    if len(t) > MAX_TEXT_CHARS:
        t = t[:MAX_TEXT_CHARS] + " […]"
    return t


def scores_path(data_dir: str) -> str:
    return os.path.join(data_dir, "sentiment", "scores.jsonl")


def load_scored_keys(data_dir: str) -> set:
    path = scores_path(data_dir)
    if not os.path.exists(path):
        return set()
    with open(path, "r", encoding="utf-8") as f:
        return {json.loads(line)["key"] for line in f if line.strip()}


def sample_posts_across_period(posts: List[dict], max_posts: int) -> List[dict]:
    """Velg et deterministisk utvalg over hele perioden, inkludert endepunktene."""
    if max_posts < 0:
        raise ValueError("max_posts må være 0 eller større")
    if max_posts == 0 or len(posts) <= max_posts:
        return posts
    ordered = sorted(posts, key=lambda p: (p.get("posted_at") or p["scraped_at"], p["key"]))
    if max_posts == 1:
        return ordered[-1:]
    return [ordered[i * (len(ordered) - 1) // (max_posts - 1)] for i in range(max_posts)]


def append_scores(data_dir: str, rows: List[dict]) -> None:
    if not rows:
        return
    path = scores_path(data_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with _write_lock, open(path, "a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def build_prompt(name: str, ticker: str, texts: List[str]) -> str:
    numbered = "\n".join(f"[{i}] {t}" for i, t in enumerate(texts, 1))
    return f"""Du vurderer innlegg fra Nordnets aksjeforum, skrevet under aksjen {name} ({ticker}) på Oslo Børs.

Gi hvert innlegg tre verdier:
- "s" (sentiment): hva innlegget signaliserer om forventet kursutvikling for {ticker} de nærmeste dagene, fra -1.0 (sterkt negativt, f.eks. selger/shorter, dårlige nyheter) via 0 (nøytralt eller uklart) til 1.0 (sterkt positivt, f.eks. kjøper, gode nyheter). Vurder FORFATTERENS holdning og innholdet, ikke om du selv er enig. Spørsmål uten tydelig holdning = 0. Ironi og sarkasme tolkes etter ment betydning.
- "r" (relevans): 0.0-1.0, hvor mye innlegget handler om {name} sine utsikter eller kurs. 0 = småprat, krangling, andre selskaper eller makro uten kobling til {ticker}. 1 = direkte om selskapet (nyheter, resultater, kontrakter, utbytte, kurs, innsidehandel).
- "c" (kategori): én av "nyhet", "analyse", "mening", "spørsmål", "humor", "offtopic".

Forum-slang: "rakett", "til månen", "laster opp", "fylt på", "kjøpt mer" = positivt. "shorte", "dumpe", "bagholder", "solgt alt", "kjører ned", "død aksje" = negativt.

Svar KUN med en JSON-liste med ett objekt per innlegg, i samme rekkefølge, uten annen tekst:
[{{"id": 1, "s": 0.4, "r": 0.9, "c": "mening"}}, ...]

Innlegg:
{numbered}"""


def call_claude(prompt: str, n_expected: int, retries: int = 5) -> (List[dict], dict):
    body = {
        "model": MODEL,
        "max_tokens": 120 + 40 * n_expected,
        "temperature": 0,
        "thinking": {"type": "disabled"},
        "messages": [{"role": "user", "content": prompt}],
    }
    headers = {
        "x-api-key": os.environ["ANTHROPIC_API_KEY"],
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    delay = 5.0
    for attempt in range(retries):
        try:
            resp = requests.post(API_URL, headers=headers, json=body, timeout=120)
        except requests.RequestException as e:
            err = str(e)
        else:
            if resp.status_code == 200:
                data = resp.json()
                text = "".join(b["text"] for b in data.get("content", []) if b.get("type") == "text")
                m = re.search(r"\[.*\]", text, re.DOTALL)
                if not m:
                    raise ValueError(f"Fant ingen JSON-liste i svaret: {text[:200]}")
                return json.loads(m.group(0), strict=False), data.get("usage", {})
            err = f"HTTP {resp.status_code}: {resp.text[:200]}"
            if resp.status_code not in (429, 500, 502, 503, 504, 529):
                raise RuntimeError(err)
        print(f"  forsøk {attempt + 1} feilet ({err}), venter {delay:.0f}s", file=sys.stderr)
        time.sleep(delay)
        delay *= 2
    raise RuntimeError(f"Ga opp etter {retries} forsøk")


def _clamp(x, lo, hi) -> Optional[float]:
    try:
        return max(lo, min(hi, float(x)))
    except (TypeError, ValueError):
        return None


def score_batch(slug: str, posts: List[dict]) -> (List[dict], dict):
    name, ticker = company_from_slug(slug)
    texts = [clean_text(p["text"]) for p in posts]
    result, usage = call_claude(build_prompt(name, ticker, texts), len(posts))
    by_id = {}
    for item in result if isinstance(result, list) else []:
        if isinstance(item, dict) and "id" in item:
            by_id[int(item["id"])] = item
    now = datetime.now(timezone.utc).isoformat()
    rows = []
    for i, p in enumerate(posts, 1):
        item = by_id.get(i)
        if not item:
            continue  # mangler i svaret - prøves igjen neste kjøring
        s, r = _clamp(item.get("s"), -1.0, 1.0), _clamp(item.get("r"), 0.0, 1.0)
        if s is None or r is None:
            continue
        c = str(item.get("c", "")).strip().lower()
        rows.append({"key": p["key"], "slug": slug, "sentiment": s, "relevance": r,
                     "category": c if c in CATEGORIES else "mening",
                     "model": MODEL, "scored_at": now})
    return rows, usage


# ------------------------------------------------------------------ main

def main() -> None:
    ap = argparse.ArgumentParser(description="Score forum-innlegg for sentiment med Claude")
    ap.add_argument("--data-dir", default="nordnet_data")
    ap.add_argument("--max-posts", type=int, default=0, help="Maks antall innlegg denne kjøringen (0 = alle)")
    ap.add_argument("--batch-size", type=int, default=30)
    ap.add_argument("--workers", type=int, default=4, help="Parallelle API-kall")
    ap.add_argument("--since", help="Kun innlegg skrevet etter denne datoen (YYYY-MM-DD)")
    ap.add_argument("--dry-run", action="store_true", help="Bare tell og estimer, ingen API-kall")
    args = ap.parse_args()
    if args.max_posts < 0:
        ap.error("--max-posts må være 0 eller større")

    scored = load_scored_keys(args.data_dir)
    todo = [p for p in iter_archive(args.data_dir) if p["key"] not in scored]
    if args.since:
        todo = [p for p in todo if (p.get("posted_at") or p["scraped_at"]) >= args.since]
    # Nyeste først ved full kjøring; begrensede kjøringer spres over hele perioden.
    todo.sort(key=lambda p: p.get("posted_at") or p["scraped_at"], reverse=True)

    # Regel-scoring uten API: tomme, ultrakorte og slettede innlegg
    rule_rows, api_posts = [], []
    now = datetime.now(timezone.utc).isoformat()
    for p in todo:
        t = clean_text(p["text"])
        if len(t) < MIN_TEXT_CHARS or DELETED_RE.match(t):
            rule_rows.append({"key": p["key"], "slug": p["slug"], "sentiment": 0.0, "relevance": 0.0,
                              "category": "offtopic", "model": "regel", "scored_at": now})
        else:
            api_posts.append(p)
    api_posts = sample_posts_across_period(api_posts, args.max_posts)

    chars = sum(len(clean_text(p["text"])) for p in api_posts)
    n_batches = 0
    by_slug: Dict[str, List[dict]] = {}
    for p in api_posts:
        by_slug.setdefault(p["slug"], []).append(p)
    batches = []
    for slug, ps in by_slug.items():
        for i in range(0, len(ps), args.batch_size):
            batches.append((slug, ps[i:i + args.batch_size]))
    n_batches = len(batches)
    est_in = chars / 3.5 + n_batches * 450  # ~3.5 tegn/token for norsk + fast prompt
    est_out = len(api_posts) * 22
    print(f"Ikke scoret: {len(todo)}  (regel: {len(rule_rows)}, til Claude: {len(api_posts)} i {n_batches} kall)")
    print(f"Estimat: ~{est_in / 1e6:.2f}M input-tokens, ~{est_out / 1e6:.2f}M output-tokens  (modell: {MODEL})")
    if args.dry_run:
        return
    append_scores(args.data_dir, rule_rows)
    if not api_posts:
        print("Ingenting å sende til Claude.")
        return
    if "ANTHROPIC_API_KEY" not in os.environ:
        sys.exit("ANTHROPIC_API_KEY mangler - kan ikke score.")

    done, failed, tok_in, tok_out = 0, 0, 0, 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(score_batch, slug, ps): (slug, ps) for slug, ps in batches}
        for k, fut in enumerate(as_completed(futures), 1):
            slug, ps = futures[fut]
            try:
                rows, usage = fut.result()
            except Exception as e:  # én feilet gruppe skal ikke stoppe resten
                failed += len(ps)
                print(f"  FEIL {slug} ({len(ps)} innlegg): {e}", file=sys.stderr)
                continue
            append_scores(args.data_dir, rows)
            done += len(rows)
            failed += len(ps) - len(rows)
            tok_in += usage.get("input_tokens", 0)
            tok_out += usage.get("output_tokens", 0)
            if k % 20 == 0 or k == n_batches:
                print(f"  {k}/{n_batches} kall, {done} scoret, {time.time() - t0:.0f}s")

    print(f"\nFerdig: {done} scoret, {failed} mangler (prøves neste gang). "
          f"Tokens brukt: {tok_in:,} inn / {tok_out:,} ut")


if __name__ == "__main__":
    main()
