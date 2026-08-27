#!/usr/bin/env python3
"""
Leser HELE den oppsamlede pending-køen, sender den i én samlet forespørsel
til Claude for full klassifisering (Positivt/Negativt/Blandet/Ingenting per
aksje + kryssegment-resonnering), lagrer rapporten i repoet, sender et
ntfy-varsel hvis noe er ekstremt viktig, og TØMMER køen etterpå.

Kjøres FRA GitHub Actions - som både har vanlig internett-tilgang (til
api.anthropic.com og ntfy.sh) OG full skrivetilgang til repoet, i motsetning
til en Cowork-økt. Dette gjør at vi ikke lenger trenger en separat Cowork
scheduled task for selve rapporteringen.

Krever miljøvariabelen ANTHROPIC_API_KEY (satt som GitHub-hemmelighet).
"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

import requests

NTFY_TOPIC = "Sebastian_Nordnet_Seeb"
PENDING_PATH = "nordnet_data/latest/pending_for_claude.json"
SEGMENTS_PATH = "maritime_segments.json"
REPORT_PATH = "nordnet_data/latest/report.md"
MODEL = "claude-sonnet-5"  # full nyansert klassifisering på tvers av mange aksjer


def call_claude(pending: dict, segments: dict) -> dict:
    prompt = f"""Du analyserer nye innlegg fra Nordnets aksjeforum siden forrige sjekk.

SEGMENT-METADATA (for kryss-aksje-resonnering):
{json.dumps(segments, ensure_ascii=False, indent=2)}

NYE INNLEGG PER AKSJE:
{json.dumps(pending, ensure_ascii=False, indent=2)}

Prioriter innlegg med has_link: true eller høy char_count. For hver aksje med
nye innlegg: klassifiser som Positivt signal / Negativt signal / Blandet /
Ingenting nevneverdig, basert på analytikerhandlinger, innsidekjøp/-salg,
resultater, kontrakter, rateendringer eller geopolitiske hendelser - ikke
enkeltbrukeres magefølelse. Bruk segment-taggingen til å vurdere om noe er
relevant på tvers av flere aksjer i samme segment, selv om den aksjen ikke
har egne nye innlegg denne runden.

Marker noe som "urgent" KUN hvis det er ekstremt viktig: bekreftet
konsoliderings-/oppkjøpsbekreftelse, en stor konkret kontrakt, flere
analytikere som oppgraderer samme dag, eller uvanlig stort innsidekjøp fra
ledelsen. Vanlig positiv sentiment eller enkeltstående kursmål-justeringer
teller IKKE som urgent.

Svar KUN med gyldig JSON på dette eksakte formatet, ingenting annet:
{{
  "report_markdown": "hele rapporten som lesbar markdown, med klassifisering per aksje og et eget avsnitt om kryssegment-funn",
  "urgent": true/false,
  "urgent_summary": "kort resymé på maks 3 setninger hvis urgent er true, ellers tom streng"
}}

Avslutt report_markdown med: "Dette er en signalrapport basert på
forumaktivitet, ikke en kjøps- eller salgsanbefaling.\""""

    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": MODEL,
            "max_tokens": 4000,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    # Ikke anta at content[0] alltid er ren tekst - nyere modeller kan legge
    # en "thinking"-blokk først. Plukk ut og slå sammen alle text-blokker.
    text_parts = [block["text"] for block in data.get("content", []) if block.get("type") == "text"]
    if not text_parts:
        raise ValueError(f"Fant ingen text-blokk i Claude-svaret: {json.dumps(data)[:500]}")
    text = "".join(text_parts).strip()
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
        print("Ingen pending-fil funnet.")
        return

    with open(PENDING_PATH, "r", encoding="utf-8") as f:
        pending = json.load(f)

    pending = {slug: posts for slug, posts in pending.items() if posts}
    if not pending:
        print("Køen er tom - ingen API-kall nødvendig.")
        return

    segments = {}
    if os.path.exists(SEGMENTS_PATH):
        with open(SEGMENTS_PATH, "r", encoding="utf-8") as f:
            segments = json.load(f)

    if "ANTHROPIC_API_KEY" not in os.environ:
        print("ANTHROPIC_API_KEY mangler - hopper over, køen forblir uendret.", file=sys.stderr)
        return

    total_posts = sum(len(v) for v in pending.values())
    print(f"Sender {total_posts} innlegg fra {len(pending)} aksjer til Claude...")

    try:
        result = call_claude(pending, segments)
    except Exception as e:
        print(f"Feil under Claude-kallet: {e} - køen forblir uendret, prøves igjen neste kjøring.", file=sys.stderr)
        return  # VIKTIG: ikke tøm køen hvis kallet feilet

    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat()
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(f"# Nordnet-rapport ({timestamp})\n\n{result['report_markdown']}\n")
    print(f"Rapport skrevet til {REPORT_PATH}")

    if result.get("urgent"):
        print(f"Flagget som viktig: {result['urgent_summary']}")
        send_ntfy(result["urgent_summary"])
    else:
        print("Ingenting ekstremt viktig denne runden.")

    # Køen er nå konsumert - tøm den (kun ved suksess, se return over ved feil).
    with open(PENDING_PATH, "w", encoding="utf-8") as f:
        json.dump({}, f)
    print("Køen tømt.")


if __name__ == "__main__":
    main()
