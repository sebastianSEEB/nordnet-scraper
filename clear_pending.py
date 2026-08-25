#!/usr/bin/env python3
"""
Tømmer pending_for_claude.json etter at innholdet er lest og behandlet.

Brukes av scheduled-tasken ETTER at rapporten er skrevet - ikke av
scrape-jobben selv. Så lenge denne ikke kjøres, fortsetter køen å vokse
(trygt), så et glemt/feilet Claude-kall mister ingenting.

Bruk:
    python clear_pending.py --data-dir nordnet_data
"""
import argparse
import json
import os


def main():
    parser = argparse.ArgumentParser(description="Tøm pending_for_claude.json etter lesing.")
    parser.add_argument("--data-dir", default="nordnet_data")
    args = parser.parse_args()

    pending_path = os.path.join(args.data_dir, "latest", "pending_for_claude.json")
    if not os.path.exists(pending_path):
        print("Ingen pending-fil funnet - ingenting å tømme.")
        return

    with open(pending_path, "r", encoding="utf-8") as f:
        pending = json.load(f)
    total = sum(len(v) for v in pending.values())

    with open(pending_path, "w", encoding="utf-8") as f:
        json.dump({}, f)

    print(f"Tømte {total} innlegg fra {len(pending)} aksjer i pending-køen.")


if __name__ == "__main__":
    main()
