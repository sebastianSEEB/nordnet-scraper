# Nyhets-ML: paper trading-backtest

Generert 2026-11-03T22:02 UTC · 120 aksjer · 38686 børsmeldinger
Testperiode (modellen har aldri sett disse dagene): 2021-12-01 → 2026-11-03

| | ML-strategi | Regel (KOG-mønster) | OSEBX |
|---|---|---|---|
| Total avkastning | +15.6 % | +15.5 % | +76.8 % |
| Årlig (CAGR) | +3.0 % | +3.0 % | +12.3 % |
| Største fall | -34.5 % | -6.1 % | -16.1 % |
| Sharpe | 0.25 | 0.67 | 0.88 |
| Handler | 960 | 62 | – |
| Treffrate | +50.6 % | +59.7 % | – |

**Tilfeldighetstest:** 56.7 % av 300 tilfeldige porteføljer med samme handelsfrekvens endte like godt eller bedre (median tilfeldig: +23.9 %).

**AUC ut-av-utvalget:** 0.496 (0,50 = mynt­kast) · **IC:** 0.010 (t = 2.6)

## Viktigste signaler (permutasjon, siste 9 mnd)

- Kursreaksjon på forrige rapport: +0.0045
- Avkastning 120 d: +0.0041
- Kursreaksjon på kontrakter 90 d: +0.0036
- Dager siden kvartalsrapport: +0.0029
- Avstand til SMA200: +0.0029
- Volum-z (20 d mot 60 d): +0.0024
- Omsetning (log): +0.0022
- Avkastning 5 d: +0.0021
- Kontraktsverdi 90 d / markedsverdi: +0.0015
- Rang avkastning 60 d: +0.0012

## ⚠ Sentiment-scoringen feiler

Siste forsøk 2026-10-30T12:59: HTTP 400: {"type":"error","error":{"type":"invalid_request_error","message":"Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase credits."},"request_i

## Forumsentiment som tillegg

Periode med forumdata: 2026-08-31 → 2026-11-03 (47 handelsdager, 37 med fasit = ca. 3.7 uavhengige 10-dagersperioder).

| Signal | Samme dag (reagerer) | Neste 10 dager (forutsier) | p (tilfeldig) |
|---|---|---|---|
| Antall innlegg 5 d | 0.018 | 0.003 | 0.952 |
| Forum-oppmerksomhet mot normalt | -0.012 | -0.01 | 0.782 |
| Sentiment 5 d | 0.041 | -0.046 | 0.254 |
| Sentiment 20 d | 0.022 | 0.034 | 0.448 |
| Stemningen snur (5 d mot 20 d) | 0.048 | -0.055 | 0.132 |
| Forum positivt mens kursen faller | None | -0.04 | 0.246 |
| Andel nyhet/analyse-innlegg | 0.018 | 0.033 | 0.366 |
| Modellscore (uten forum) | -0.097 | -0.024 | 0.59 |
| Kombinert (modell + forum) | -0.198 | -0.033 | 0.408 |

Paper trading i perioden: modell alene -0.3 % (32 handler), modell + forum -7.8 % (32 handler), OSEBX -0.7 %. Tilfeldig median -2.9 %.

## Begrensninger

- Universet er dagens watchlist (overlevelsesskjevhet: aksjer som gikk konkurs er ikke med).
- Markedsverdi bakover i tid bruker dagens aksjeantall.
- Kontraktsverdier tolkes fra tekst med faste valutakurser - grovt.
- Kvartalsrapport-dato er estimert (~63 handelsdager etter forrige).
- Dette er forskning, ikke investeringsråd.
