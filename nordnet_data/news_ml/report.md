# Nyhets-ML: paper trading-backtest

Generert 2026-11-05T22:15 UTC · 120 aksjer · 38769 børsmeldinger
Testperiode (modellen har aldri sett disse dagene): 2021-12-01 → 2026-11-05

| | ML-strategi | Regel (KOG-mønster) | OSEBX |
|---|---|---|---|
| Total avkastning | +29.2 % | +15.1 % | +74.9 % |
| Årlig (CAGR) | +5.3 % | +2.9 % | +12.0 % |
| Største fall | -38.7 % | -6.1 % | -16.1 % |
| Sharpe | 0.39 | 0.65 | 0.87 |
| Handler | 961 | 62 | – |
| Treffrate | +52.1 % | +59.7 % | – |

**Tilfeldighetstest:** 35.7 % av 300 tilfeldige porteføljer med samme handelsfrekvens endte like godt eller bedre (median tilfeldig: +16.2 %).

**AUC ut-av-utvalget:** 0.496 (0,50 = mynt­kast) · **IC:** 0.013 (t = 3.3)

## Viktigste signaler (permutasjon, siste 9 mnd)

- Dager siden kvartalsrapport: +0.0056
- Avkastning 120 d: +0.0039
- Kursreaksjon på kontrakter 90 d: +0.0024
- Avstand til SMA200: +0.0023
- Kursreaksjon på forrige rapport: +0.0022
- Avkastning 60 d: +0.0019
- Innsidesalg 90 d: +0.0018
- Volum-z (20 d mot 60 d): +0.0014
- Guiding/oppdatering 30 d: +0.0012
- Omsetning (log): +0.0010

## ⚠ Sentiment-scoringen feiler

Siste forsøk 2026-10-30T12:59: HTTP 400: {"type":"error","error":{"type":"invalid_request_error","message":"Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase credits."},"request_i

## Forumsentiment som tillegg

Periode med forumdata: 2026-08-31 → 2026-11-05 (49 handelsdager, 39 med fasit = ca. 3.9 uavhengige 10-dagersperioder).

| Signal | Samme dag (reagerer) | Neste 10 dager (forutsier) | p (tilfeldig) |
|---|---|---|---|
| Antall innlegg 5 d | 0.005 | -0.003 | 0.942 |
| Forum-oppmerksomhet mot normalt | -0.018 | -0.005 | 0.906 |
| Sentiment 5 d | 0.042 | -0.05 | 0.208 |
| Sentiment 20 d | 0.019 | 0.032 | 0.48 |
| Stemningen snur (5 d mot 20 d) | 0.054 | -0.056 | 0.124 |
| Forum positivt mens kursen faller | None | -0.041 | 0.226 |
| Andel nyhet/analyse-innlegg | 0.012 | 0.02 | 0.582 |
| Modellscore (uten forum) | -0.098 | -0.002 | 0.956 |
| Kombinert (modell + forum) | -0.203 | -0.018 | 0.674 |

Paper trading i perioden: modell alene -2.7 % (32 handler), modell + forum -5.6 % (32 handler), OSEBX -1.8 %. Tilfeldig median -3.7 %.

## Begrensninger

- Universet er dagens watchlist (overlevelsesskjevhet: aksjer som gikk konkurs er ikke med).
- Markedsverdi bakover i tid bruker dagens aksjeantall.
- Kontraktsverdier tolkes fra tekst med faste valutakurser - grovt.
- Kvartalsrapport-dato er estimert (~63 handelsdager etter forrige).
- Dette er forskning, ikke investeringsråd.
