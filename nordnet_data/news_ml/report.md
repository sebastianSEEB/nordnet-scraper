# Nyhets-ML: paper trading-backtest

Generert 2026-11-13T22:11 UTC · 120 aksjer · 38934 børsmeldinger
Testperiode (modellen har aldri sett disse dagene): 2021-12-01 → 2026-11-13

| | ML-strategi | Regel (KOG-mønster) | OSEBX |
|---|---|---|---|
| Total avkastning | +19.6 % | +15.4 % | +77.5 % |
| Årlig (CAGR) | +3.7 % | +2.9 % | +12.3 % |
| Største fall | -35.3 % | -5.7 % | -16.1 % |
| Sharpe | 0.29 | 0.65 | 0.88 |
| Handler | 966 | 57 | – |
| Treffrate | +50.1 % | +56.1 % | – |

**Tilfeldighetstest:** 46.0 % av 300 tilfeldige porteføljer med samme handelsfrekvens endte like godt eller bedre (median tilfeldig: +17.6 %).

**AUC ut-av-utvalget:** 0.499 (0,50 = mynt­kast) · **IC:** 0.014 (t = 3.5)

## Viktigste signaler (permutasjon, siste 9 mnd)

- Omsetning (log): +0.0037
- Avkastning 60 d: +0.0035
- Kursreaksjon på forrige rapport: +0.0028
- Dager siden kvartalsrapport: +0.0025
- Avkastning 5 d: +0.0019
- Meravkastning 60 d: +0.0015
- Guiding/oppdatering 30 d: +0.0015
- Rang avkastning 60 d: +0.0014
- Kontraktsverdi siden rapport / markedsverdi: +0.0014
- Kursreaksjon på kontrakter 90 d: +0.0009

## ⚠ Sentiment-scoringen feiler

Siste forsøk 2026-10-30T12:59: HTTP 400: {"type":"error","error":{"type":"invalid_request_error","message":"Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase credits."},"request_i

## Forumsentiment som tillegg

Periode med forumdata: 2026-08-31 → 2026-11-13 (55 handelsdager, 45 med fasit = ca. 4.5 uavhengige 10-dagersperioder).

| Signal | Samme dag (reagerer) | Neste 10 dager (forutsier) | p (tilfeldig) |
|---|---|---|---|
| Antall innlegg 5 d | 0.005 | -0.023 | 0.562 |
| Forum-oppmerksomhet mot normalt | -0.005 | 0.006 | 0.882 |
| Sentiment 5 d | 0.05 | -0.033 | 0.374 |
| Sentiment 20 d | 0.026 | 0.027 | 0.512 |
| Stemningen snur (5 d mot 20 d) | 0.054 | -0.03 | 0.368 |
| Forum positivt mens kursen faller | None | -0.01 | 0.78 |
| Andel nyhet/analyse-innlegg | 0.015 | -0.01 | 0.772 |
| Modellscore (uten forum) | -0.089 | -0.014 | 0.748 |
| Kombinert (modell + forum) | -0.186 | -0.014 | 0.694 |

Paper trading i perioden: modell alene +0.1 % (40 handler), modell + forum -6.8 % (40 handler), OSEBX -0.3 %. Tilfeldig median -2.1 %.

## Begrensninger

- Universet er dagens watchlist (overlevelsesskjevhet: aksjer som gikk konkurs er ikke med).
- Markedsverdi bakover i tid bruker dagens aksjeantall.
- Kontraktsverdier tolkes fra tekst med faste valutakurser - grovt.
- Kvartalsrapport-dato er estimert (~63 handelsdager etter forrige).
- Dette er forskning, ikke investeringsråd.
