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

# Billig grovfilter - portvakt FØR vi bruker et API-kall i det hele tatt.
# Trivielle kommentarer (ingen lenke, kort, ingen nøkkelord) trigger ikke
# noe Claude-kall - køen får bare vokse litt til noe substansielt dukker opp.
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

Marker et funn som "urgent" KUN hvis det er ekstremt viktig: bekreftet
konsoliderings-/oppkjøpsbekreftelse, en stor konkret kontrakt, flere
analytikere som oppgraderer samme dag, eller uvanlig stort innsidekjøp fra
ledelsen. Vanlig positiv sentiment eller enkeltstående kursmål-justeringer
teller IKKE som urgent.

Svar KUN med gyldig JSON på dette eksakte formatet, ingenting annet:
{{
  "report_markdown": "hele rapporten som lesbar markdown, med klassifisering per aksje og et eget avsnitt om kryssegment-funn",
  "urgent": true/false,
  "alerts": [
    {{
      "company": "Selskapsnavn (TICKER)",
      "headline": "Kort overskrift på hovedsaken, maks 8 ord",
      "signal_strength": "Sterkt signal" eller "Signal" eller "Svakt signal",
      "reasoning": "1-2 setninger som begrunner vurderingen, med konkrete fakta (hvem, hva, tall)"
    }}
  ]
}}

"alerts" skal være TOM LISTE hvis urgent er false. Hvis flere selskaper
kvalifiserer, sorter listen med det VIKTIGSTE funnet først. "signal_strength"
beskriver styrken på selve signalet i markedet/forumet (f.eks. hvor mange
analytikere, hvor stort innsidekjøp) - IKKE en kjøpsanbefaling fra deg.

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
            "max_tokens": 8000,
            "thinking": {"type": "disabled"},  # ren klassifisering - trenger ikke tenke-modus
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    # Ikke anta at content[0] alltid er ren tekst - modellen kan legge en
    # "thinking"-blokk først. Plukk ut og slå sammen alle text-blokker.
    text_parts = [block["text"] for block in data.get("content", []) if block.get("type") == "text"]
    if not text_parts:
        stop_reason = data.get("stop_reason", "ukjent")
        raise ValueError(
            f"Fant ingen text-blokk i Claude-svaret (stop_reason={stop_reason}). "
            f"Rått svar: {json.dumps(data)[:500]}"
        )
    text = "".join(text_parts).strip()
    text = re.sub(r"^```(json)?|```$", "", text.strip()).strip()
    return json.loads(text)


STRENGTH_ORDER = {"Sterkt signal": 0, "Signal": 1, "Svakt signal": 2}
STRENGTH_ICON = {"Sterkt signal": "🔴", "Signal": "🟡", "Svakt signal": "⚪"}


def format_alert_body(alerts: list) -> str:
    ordered = sorted(alerts, key=lambda a: STRENGTH_ORDER.get(a.get("signal_strength"), 1))
    blocks = []
    for a in ordered:
        icon = STRENGTH_ICON.get(a.get("signal_strength"), "🟡")
        blocks.append(
            f"{icon} {a.get('signal_strength', 'Signal')} — {a.get('company', '?')}\n"
            f"{a.get('headline', '')}\n"
            f"{a.get('reasoning', '')}"
        )
    return "\n──────────\n".join(blocks)


def send_ntfy(body: str, title: str) -> None:
    result = subprocess.run(
        [
            "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
            "-H", f"Title: {title}",
            "-H", "Priority: high",
            "-d", body,
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

    has_candidate = any(passes_prefilter(p) for posts in pending.values() for p in posts)
    if not has_candidate:
        total = sum(len(v) for v in pending.values())
        print(f"{total} nye innlegg i køen, men ingen passerte grovfilteret - "
              f"hopper over Claude-kallet for å spare kostnad. Køen forblir uendret.")
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

    if result.get("urgent") and result.get("alerts"):
        n = len(result["alerts"])
        title = "Nordnet: viktig funn" if n == 1 else f"Nordnet: {n} viktige funn"
        body = format_alert_body(result["alerts"])
        print(f"Flagget {n} funn som viktig:\n{body}")
        send_ntfy(body, title)
    else:
        print("Ingenting ekstremt viktig denne runden.")

    # Køen er nå konsumert - tøm den (kun ved suksess, se return over ved feil).
    with open(PENDING_PATH, "w", encoding="utf-8") as f:
        json.dump({}, f)
    print("Køen tømt.")


if __name__ == "__main__":
    main()
