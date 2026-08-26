#!/usr/bin/env python3
"""
Sjekker nye funn etter hver scrape-kjøring og sender et ntfy-varsel hvis noe
kvalifiserer. Kjøres FRA GitHub Actions, ikke fra Cowork - det er poenget:
GitHub Actions-serveren har vanlig internett-tilgang, uten den samme
egress-allowlisten som blokkerer utgående varsler fra en Cowork-økt.

Dette er en enklere, regelbasert sjekk - ikke like nyansert som Claudes
egen vurdering i den planlagte oppgaven, men den er alltid levert.
"""
import json
import os
import re
import subprocess
import sys

NTFY_TOPIC = "Sebastian_Nordnet_Seeb"
PENDING_PATH = "nordnet_data/latest/pending_for_claude.json"

# Nøkkelord som ofte indikerer noe substansielt, ikke bare magefølelse.
KEYWORDS = [
    "kursmål", "oppgraderer", "oppgradering", "nedgraderer", "nedgradering",
    "innsidekjøp", "innsidesalg", "primærinsidetransaksjon",
    "oppkjøp", "kontrakt", "utbytte", "rapport", "guiding",
    "fusjon", "konsolidering", "kjøpsanbefaling", "kursmål",
]
KEYWORD_RE = re.compile("|".join(KEYWORDS), re.IGNORECASE)


def is_noteworthy(post: dict) -> bool:
    if post.get("has_link"):
        return True
    if post.get("char_count", 0) > 500:
        return True
    if KEYWORD_RE.search(post.get("text", "")):
        return True
    return False


def main():
    if not os.path.exists(PENDING_PATH):
        print("Ingen pending-fil funnet - ingenting å varsle om.")
        return

    with open(PENDING_PATH, "r", encoding="utf-8") as f:
        pending = json.load(f)

    flagged = []
    for slug, posts in pending.items():
        for post in posts:
            if is_noteworthy(post):
                snippet = post["text"][:120] + ("…" if len(post["text"]) > 120 else "")
                flagged.append(f"{slug}: {post['author']} - {snippet}")

    if not flagged:
        print("Ingenting kvalifiserte for varsel denne runden.")
        return

    # Begrens til de 5 første for å holde varselet lesbart.
    body = "\n\n".join(flagged[:5])
    if len(flagged) > 5:
        body += f"\n\n(+{len(flagged) - 5} til - se full rapport)"

    print(f"Sender varsel for {len(flagged)} funn...")
    result = subprocess.run(
        [
            "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
            "-H", "Title: Nordnet: nytt å sjekke",
            "-H", "Priority: default",
            "-d", body,
            f"https://ntfy.sh/{NTFY_TOPIC}",
        ],
        capture_output=True, text=True,
    )
    print(f"ntfy svarte med HTTP {result.stdout}")


if __name__ == "__main__":
    main()
