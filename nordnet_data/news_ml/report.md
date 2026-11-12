# Nyhets-ML: paper trading-backtest

Generert 2026-11-12T22:28 UTC · 120 aksjer · 38911 børsmeldinger
Testperiode (modellen har aldri sett disse dagene): 2021-12-01 → 2026-11-12

| | ML-strategi | Regel (KOG-mønster) | OSEBX |
|---|---|---|---|
| Total avkastning | -5.1 % | +13.1 % | +77.1 % |
| Årlig (CAGR) | -1.1 % | +2.5 % | +12.2 % |
| Største fall | -33.5 % | -5.7 % | -16.1 % |
| Sharpe | 0.03 | 0.57 | 0.88 |
| Handler | 965 | 57 | – |
| Treffrate | +47.7 % | +56.1 % | – |

**Tilfeldighetstest:** 72.3 % av 300 tilfeldige porteføljer med samme handelsfrekvens endte like godt eller bedre (median tilfeldig: +13.6 %).

**AUC ut-av-utvalget:** 0.499 (0,50 = mynt­kast) · **IC:** 0.013 (t = 3.5)

## Viktigste signaler (permutasjon, siste 9 mnd)

- Omsetning (log): +0.0051
- Kursreaksjon på forrige rapport: +0.0045
- Dager siden kvartalsrapport: +0.0039
- Avkastning 60 d: +0.0033
- Avkastning 120 d: +0.0027
- Meravkastning 60 d: +0.0024
- Rang avkastning 60 d: +0.0024
- Volum-z (20 d mot 60 d): +0.0023
- Avkastning 5 d: +0.0021
- Guiding/oppdatering 30 d: +0.0018

## ⚠ Sentiment-scoringen feiler

Siste forsøk 2026-10-30T12:59: HTTP 400: {"type":"error","error":{"type":"invalid_request_error","message":"Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase credits."},"request_i

## Forumsentiment som tillegg

Periode med forumdata: 2026-08-31 → 2026-11-12 (54 handelsdager, 44 med fasit = ca. 4.4 uavhengige 10-dagersperioder).

| Signal | Samme dag (reagerer) | Neste 10 dager (forutsier) | p (tilfeldig) |
|---|---|---|---|
| Antall innlegg 5 d | 0.005 | -0.018 | 0.668 |
| Forum-oppmerksomhet mot normalt | -0.007 | 0.006 | 0.894 |
| Sentiment 5 d | 0.048 | -0.035 | 0.352 |
| Sentiment 20 d | 0.027 | 0.027 | 0.512 |
| Stemningen snur (5 d mot 20 d) | 0.051 | -0.034 | 0.328 |
| Forum positivt mens kursen faller | None | -0.011 | 0.756 |
| Andel nyhet/analyse-innlegg | 0.015 | -0.004 | 0.906 |
| Modellscore (uten forum) | -0.093 | -0.018 | 0.642 |
| Kombinert (modell + forum) | -0.191 | -0.017 | 0.628 |

Paper trading i perioden: modell alene -3.3 % (40 handler), modell + forum -5.6 % (40 handler), OSEBX -0.5 %. Tilfeldig median -2.3 %.

## Begrensninger

- Universet er dagens watchlist (overlevelsesskjevhet: aksjer som gikk konkurs er ikke med).
- Markedsverdi bakover i tid bruker dagens aksjeantall.
- Kontraktsverdier tolkes fra tekst med faste valutakurser - grovt.
- Kvartalsrapport-dato er estimert (~63 handelsdager etter forrige).
- Dette er forskning, ikke investeringsråd.
