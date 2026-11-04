# Nyhets-ML: paper trading-backtest

Generert 2026-11-04T22:07 UTC · 120 aksjer · 38717 børsmeldinger
Testperiode (modellen har aldri sett disse dagene): 2021-12-01 → 2026-11-04

| | ML-strategi | Regel (KOG-mønster) | OSEBX |
|---|---|---|---|
| Total avkastning | +7.5 % | +15.4 % | +76.7 % |
| Årlig (CAGR) | +1.5 % | +3.0 % | +12.3 % |
| Største fall | -41.2 % | -6.1 % | -16.1 % |
| Sharpe | 0.17 | 0.66 | 0.88 |
| Handler | 961 | 62 | – |
| Treffrate | +51.0 % | +59.7 % | – |

**Tilfeldighetstest:** 61.3 % av 300 tilfeldige porteføljer med samme handelsfrekvens endte like godt eller bedre (median tilfeldig: +14.4 %).

**AUC ut-av-utvalget:** 0.495 (0,50 = mynt­kast) · **IC:** 0.009 (t = 2.2)

## Viktigste signaler (permutasjon, siste 9 mnd)

- Dager siden kvartalsrapport: +0.0037
- Avstand til SMA200: +0.0028
- Avkastning 120 d: +0.0026
- Omsetning (log): +0.0024
- Oppkjøp/fusjon 90 d: +0.0020
- Avkastning 60 d: +0.0017
- Volum-z (20 d mot 60 d): +0.0015
- Guiding/oppdatering 30 d: +0.0013
- Kursreaksjon på forrige rapport: +0.0012
- Avkastning 5 d: +0.0010

## ⚠ Sentiment-scoringen feiler

Siste forsøk 2026-10-30T12:59: HTTP 400: {"type":"error","error":{"type":"invalid_request_error","message":"Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase credits."},"request_i

## Forumsentiment som tillegg

Periode med forumdata: 2026-08-31 → 2026-11-04 (48 handelsdager, 38 med fasit = ca. 3.8 uavhengige 10-dagersperioder).

| Signal | Samme dag (reagerer) | Neste 10 dager (forutsier) | p (tilfeldig) |
|---|---|---|---|
| Antall innlegg 5 d | 0.014 | 0.001 | 0.996 |
| Forum-oppmerksomhet mot normalt | -0.015 | -0.007 | 0.848 |
| Sentiment 5 d | 0.043 | -0.047 | 0.232 |
| Sentiment 20 d | 0.02 | 0.033 | 0.464 |
| Stemningen snur (5 d mot 20 d) | 0.052 | -0.056 | 0.124 |
| Forum positivt mens kursen faller | None | -0.041 | 0.236 |
| Andel nyhet/analyse-innlegg | 0.014 | 0.028 | 0.46 |
| Modellscore (uten forum) | -0.106 | -0.033 | 0.466 |
| Kombinert (modell + forum) | -0.207 | -0.04 | 0.322 |

Paper trading i perioden: modell alene -2.1 % (32 handler), modell + forum -6.3 % (32 handler), OSEBX -0.8 %. Tilfeldig median -2.7 %.

## Begrensninger

- Universet er dagens watchlist (overlevelsesskjevhet: aksjer som gikk konkurs er ikke med).
- Markedsverdi bakover i tid bruker dagens aksjeantall.
- Kontraktsverdier tolkes fra tekst med faste valutakurser - grovt.
- Kvartalsrapport-dato er estimert (~63 handelsdager etter forrige).
- Dette er forskning, ikke investeringsråd.
