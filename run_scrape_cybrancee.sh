#!/bin/bash
# Kjøres av Pterodactyl "Schedules" hvert 15. minutt.
# Henter nyeste versjon fra GitHub først (i tilfelle Claude nettopp har
# tømt køen), kjører scriperen (som legger nye funn til i køen), og
# pusher resultatet tilbake.
set -e

cd /home/container/nordnet-scraper   # juster til riktig mappe på serveren

git pull --rebase origin main

python3 nordnet_forum_scraper.py --from-file watchlist_full.txt --data-dir nordnet_data

git add nordnet_data
if ! git diff --staged --quiet; then
    git commit -m "Scrape $(date -u +'%Y-%m-%d %H:%M UTC')"
    git push origin main
else
    echo "Ingenting nytt å committe denne runden."
fi
