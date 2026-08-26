#!/usr/bin/env python3
"""
Sjekker nye funn etter hver scrape-kjøring, bruker Claude (via Anthropic API)
til å avgjøre om noe er verdt et varsel OG skrive et kort resymé, og sender
det til ntfy hvis terskelen nås.

Kjøres FRA GitHub Actions - som har vanlig internett-tilgang, både til
api.anthropic.com og ntfy.sh, uten den egress-allowlisten som blokkerer en
Cowork-økt.

Krever miljøvariabelen ANTHROPIC_API_KEY (satt som GitHub-hemmelighet).
"""
import json
import os
import re
import subprocess
import sys

import requests

NTFY_TOPIC = "Sebastian_Nordnet_Seeb"
PENDING_PATH = "nordnet_data/latest/pending_for_claude.json"
MODEL = "claude-haiku-4-5-20251001"  # rask og billig - nok til klassifisering+resymé

# Grovfilter FØR vi bruker API-kall - holder kostnaden nede ved å bare sende
# de mest lovende innleggene til Claude, ikke alt.
KEYWORDS = [
    "kursmål", "oppgraderer", "oppgradering", "nedgraderer", "nedgradering",
    "innsidekjøp", "innsidesalg", "primærinsidetransaksjon",
    "oppkjøp", "kontrakt", "utbytte", "guiding",
    "fusjon", "konsolidering", "kjøpsanbefaling",
]
KEYWORD_RE = re.compile("|".join(KEYWORDS), re.IGNORECASE)


def passes_prefilter(post: dict) -> bool:
    if post.get("has_link"):
        return True
    if post.get("char_count", 0) > 400:
        return True
    if KEYWORD_RE.search(post.get("text", "")):
        return True
    return False


def ask_claude(candidates: list) -> dict:
    """Send de forhåndsfiltrerte innleggene til Claude og be om en streng
    JSON-vurdering: skal det varsles, og i så fall med hvilket resymé."""
    listing = "\n\n".join(
        f"[{c['slug']}] {c['author']}: {c['text'][:600]}" for c in candidates
    )
    prompt = f"""Dette er nye innlegg fra Nordnets aksjeforum, allerede grovfiltrert
til de mest lovende (lenker, lange innlegg, eller nøkkelord om kursmål/innsidehandel/
kontrakter/oppkjøp). Vurder om NOE av dette er EKSTREMT VIKTIG nok til å forstyrre
en person med en push-varsling akkurat nå - dvs: bekreftet konsoliderings-/
oppkjøpsbekreftelse, en stor konkret kontrakt, flere analytikere som oppgraderer
samme dag, eller uvanlig stort innsidekjøp fra ledelsen. Vanlig positiv sentiment,
enkeltstående kursmål-justeringer, eller synsing teller IKKE som ekstremt viktig.

Innlegg:
{listing}

Svar KUN med gyldig JSON på dette eksakte formatet, ingenting annet:
{{"alert": true/false, "summary": "kort resymé på maks 3 setninger, norsk, egnet for en push-varsling"}}"""

    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": MODEL,
            "max_tokens": 300,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=30,
    )
    resp.raise_for_status()
    text = resp.json()["content"][0]["text"].strip()
    # Klipp bort ev. kodeblokk-markører hvis modellen legger det på uansett
    text = re.sub(r"^```(json)?|```$", "", text.strip()).strip()
    return json.loads(text)


def send_ntfy(summary: str) -> None:
    result = subprocess.run(
        [
            "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
            "-H", "Title: Nordnet: viktig funn",
            "-H", "Priority: high",
            "-d", summary,
            f"https://ntfy.sh/{NTFY_TOPIC}",
        ],
        capture_output=True, text=True,
    )
    print(f"ntfy svarte med HTTP {result.stdout}")


def main():
    if not os.path.exists(PENDING_PATH):
        print("Ingen pending-fil funnet - ingenting å sjekke.")
        return

    with open(PENDING_PATH, "r", encoding="utf-8") as f:
        pending = json.load(f)

    candidates = []
    for slug, posts in pending.items():
        for post in posts:
            if passes_prefilter(post):
                candidates.append({**post, "slug": slug})

    if not candidates:
        print("Ingenting passerte grovfilteret - ingen API-kall nødvendig.")
        return

    if "ANTHROPIC_API_KEY" not in os.environ:
        print("ANTHROPIC_API_KEY mangler - hopper over Claude-vurdering.", file=sys.stderr)
        return

    print(f"{len(candidates)} innlegg passerte grovfilteret - spør Claude om vurdering...")
    try:
        verdict = ask_claude(candidates)
    except Exception as e:
        print(f"Feil under Claude-kallet: {e}", file=sys.stderr)
        return

    if not verdict.get("alert"):
        print("Claude vurderte ingenting som ekstremt viktig denne runden.")
        return

    print(f"Claude flagget dette som viktig: {verdict['summary']}")
    send_ntfy(verdict["summary"])


if __name__ == "__main__":
    main()
