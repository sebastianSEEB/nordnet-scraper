#!/usr/bin/env python3
"""
Sentiment uten API: lokal norsk språkmodell (gratis, kjører på GitHub Actions)
=============================================================================
Erstatning for score_sentiment.py når Anthropic-kontoen er tom eller du ikke
vil betale per innlegg. Skriver til SAMME fil (nordnet_data/sentiment/scores.jsonl)
i samme format, så sentiment_analysis.py, news_ml/forum.py og copytrade/paper.py
bruker resultatet uten endringer.

Modell: ltg/norbert3-base_sentence-sentiment (Universitetet i Oslo, CC-BY-4.0),
trent på norske setninger (NoReC). Gir Negativ / Positiv / Nøytral / Blandet.
    sentiment = P(positiv) - P(negativ)              -1 .. 1

Modellen er trent på anmeldelser, ikke aksjeforum, så den kjenner ikke
børsslang ("rakett", "shortere", "dumpe"). Et lite ordforråd under dytter
sentimentet litt i riktig retning for de vanligste uttrykkene.

Relevans og kategori har ingen modell her - de settes med enkle regler:
nevner selskapet/tickeren, har lenke, er et spørsmål, lengde osv. Det er
grovere enn Claude, men godt nok til å skille "Ny kontrakt på 2 mrd" fra "lol".

Bruk:
    pip install -r requirements-sentiment.txt transformers torch --extra-index-url https://download.pytorch.org/whl/cpu
    python score_sentiment_local.py              # alt som mangler
    python score_sentiment_local.py --max-posts 300
"""

import argparse
import math
import os
import re
from datetime import datetime, timezone

from archive_posts import iter_archive
from score_sentiment import (DELETED_RE, MIN_TEXT_CHARS, append_scores, clean_text, company_from_slug,
                             load_scored_keys)

MODEL_ID = os.environ.get("LOCAL_SENTIMENT_MODEL", "ltg/norbert3-base_sentence-sentiment")
MODEL_TAG = "norbert3-lokal"

BULL = r"rakett|til månen|kjøpt mer|kjøper mer|fylt på|fyller på|lader|laste opp|lastet opp|undervurdert|" \
       r"billig|kursmål opp|oppgrader\w*|kontrakt|rekord|utbytte|breakout|grønt|bull\w*|long\b|🚀|📈"
BEAR = r"shorte\w*|short\b|dump\w*|solgt alt|solgte alt|ut av aksjen|overvurdert|kursmål ned|nedgrader\w*|" \
       r"emisjon|utvanning|konkurs|tap\b|rødt|bear\w*|pump and dump|📉"
BULL_RE, BEAR_RE = re.compile(BULL, re.I), re.compile(BEAR, re.I)
FIN_RE = re.compile(r"kurs|aksje|kvartal|resultat|kontrakt|ordre|utbytte|emisjon|analyti|kursmål|rapport|"
                    r"inntekt|ebitda|margin|gjeld|oppkjøp|bud\b|innsid|børs|mrd|mill|nok\b|%", re.I)
LINK_RE = re.compile(r"https?://")


# Reserve hvis NorBERT ikke laster (den trenger trust_remote_code og kan brekke med nye transformers)
FALLBACK_MODELS = ["cardiffnlp/twitter-xlm-roberta-base-sentiment"]
DEFAULT_LABELS = {0: "negative", 1: "positive", 2: "neutral"}  # NorBERT-rekkefølgen fra modellkortet
LOAD_ERRORS = []


def _norm_labels(model):
    raw = getattr(model.config, "id2label", None) or {}
    labels = {int(i): str(l).lower() for i, l in raw.items()}
    if not labels or all(l.startswith("label_") for l in labels.values()):
        labels = dict(DEFAULT_LABELS) if model.config.num_labels == 3 else labels
    return labels


def load_model():
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    global MODEL_TAG
    for mid in [MODEL_ID] + FALLBACK_MODELS:
        try:
            remote = mid.startswith("ltg/")
            tok = AutoTokenizer.from_pretrained(mid, trust_remote_code=remote)
            model = AutoModelForSequenceClassification.from_pretrained(mid, trust_remote_code=remote)
            model.eval()
            torch.set_num_threads(os.cpu_count() or 2)
            if mid != MODEL_ID:
                MODEL_TAG = "xlmr-lokal"
                if mid.startswith("cardiffnlp/"):
                    return tok, model, {0: "negative", 1: "neutral", 2: "positive"}, mid
            return tok, model, _norm_labels(model), mid
        except Exception as e:  # noqa: BLE001 - prøv neste modell
            LOAD_ERRORS.append(f"{mid}: {type(e).__name__}: {str(e)[:400]}")
            print("Kunne ikke laste", mid, "->", LOAD_ERRORS[-1])
    raise RuntimeError("Ingen sentiment-modell kunne lastes: " + " | ".join(LOAD_ERRORS))


def predict(tok, model, labels, texts, batch_size=32):
    import torch
    out = []
    for i in range(0, len(texts), batch_size):
        enc = tok(texts[i:i + batch_size], padding=True, truncation=True, max_length=256, return_tensors="pt")
        with torch.no_grad():
            probs = torch.softmax(model(**enc).logits, dim=-1).tolist()
        for row in probs:
            p = {labels[j]: v for j, v in enumerate(row)}
            pos = p.get("positive", 0) + 0.5 * p.get("mixed", 0)
            neg = p.get("negative", 0) + 0.5 * p.get("mixed", 0)
            out.append(pos - neg)
    return out


def lexicon_nudge(text):
    b, s = len(BULL_RE.findall(text)), len(BEAR_RE.findall(text))
    return 0.15 * math.tanh(b - s)


def relevance_and_category(text, slug):
    name, ticker = company_from_slug(slug)
    low = text.lower()
    mentions = ticker.lower() in re.findall(r"[a-zæøå0-9]+", low) or name.split()[0].lower() in low
    fin = len(FIN_RE.findall(text))
    rel = 0.25 + 0.35 * mentions + min(0.3, 0.1 * fin) + (0.1 if len(text) > 120 else 0) - (0.2 if len(text) < 25 else 0)
    rel = round(max(0.0, min(1.0, rel)), 2)
    if LINK_RE.search(text):
        cat = "nyhet"
    elif text.rstrip().endswith("?"):
        cat = "spørsmål"
    elif fin >= 3 and len(text) > 200:
        cat = "analyse"
    elif rel < 0.3:
        cat = "offtopic"
    else:
        cat = "mening"
    return rel, cat


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="nordnet_data")
    ap.add_argument("--max-posts", type=int, default=0)
    ap.add_argument("--chunk", type=int, default=500, help="Skriv til disk etter så mange innlegg")
    args = ap.parse_args()

    scored = load_scored_keys(args.data_dir)
    todo = [p for p in iter_archive(args.data_dir) if p["key"] not in scored]
    todo.sort(key=lambda p: p.get("posted_at") or p["scraped_at"], reverse=True)
    if args.max_posts:
        todo = todo[:args.max_posts]
    now = datetime.now(timezone.utc).isoformat()

    rule_rows, work = [], []
    for p in todo:
        t = clean_text(p["text"])
        if len(t) < MIN_TEXT_CHARS or DELETED_RE.match(t):
            rule_rows.append({"key": p["key"], "slug": p["slug"], "sentiment": 0.0, "relevance": 0.0,
                              "category": "offtopic", "model": "regel", "scored_at": now})
        else:
            work.append((p, t))
    append_scores(args.data_dir, rule_rows)
    print(f"Ikke scoret: {len(todo)}  (regel: {len(rule_rows)}, til lokal modell: {len(work)})")
    if not work:
        return

    status = {"started": now, "to_model": len(work), "rule": len(rule_rows), "scored": 0}
    try:
        tok, model, labels, used = load_model()
    except Exception as e:  # noqa: BLE001
        status.update({"error": str(e)[:2000], "load_errors": LOAD_ERRORS})
        _write_status(args.data_dir, status)
        raise
    status.update({"model": used, "labels": labels, "load_errors": LOAD_ERRORS})
    print(f"Modell {used} lastet, etiketter: {labels}")
    done = 0
    for i in range(0, len(work), args.chunk):
        part = work[i:i + args.chunk]
        sents = predict(tok, model, labels, [t for _, t in part])
        rows = []
        for (p, t), s in zip(part, sents):
            rel, cat = relevance_and_category(t, p["slug"])
            s = max(-1.0, min(1.0, s + lexicon_nudge(t)))
            rows.append({"key": p["key"], "slug": p["slug"], "sentiment": round(s, 3), "relevance": rel,
                         "category": cat, "model": MODEL_TAG, "scored_at": now})
        append_scores(args.data_dir, rows)
        done += len(rows)
        status["scored"] = done
        _write_status(args.data_dir, status)
        print(f"  scoret {done}/{len(work)}")
    status["finished"] = datetime.now(timezone.utc).isoformat()
    _write_status(args.data_dir, status)


def _write_status(data_dir, status):
    import json
    path = os.path.join(data_dir, "sentiment", "local_status.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2, default=str)


if __name__ == "__main__":
    main()
