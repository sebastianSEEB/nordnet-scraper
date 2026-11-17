# Nyhets-ML: paper trading-backtest

Generert 2026-11-17T23:42 UTC · 120 aksjer · 38959 børsmeldinger
Testperiode (modellen har aldri sett disse dagene): 2021-12-01 → 2026-11-16

| | ML-strategi | Regel (KOG-mønster) | OSEBX |
|---|---|---|---|
| Total avkastning | +39.3 % | +16.4 % | +76.8 % |
| Årlig (CAGR) | +6.9 % | +3.1 % | +12.2 % |
| Største fall | -36.7 % | -5.7 % | -16.1 % |
| Sharpe | 0.46 | 0.69 | 0.88 |
| Handler | 966 | 57 | – |
| Treffrate | +50.9 % | +56.1 % | – |

**Tilfeldighetstest:** 27.7 % av 300 tilfeldige porteføljer med samme handelsfrekvens endte like godt eller bedre (median tilfeldig: +21.7 %).

**AUC ut-av-utvalget:** 0.499 (0,50 = mynt­kast) · **IC:** 0.013 (t = 3.3)

## Viktigste signaler (permutasjon, siste 9 mnd)

- Omsetning (log): +0.0052
- Avkastning 60 d: +0.0041
- Kursreaksjon på forrige rapport: +0.0036
- Rang avkastning 60 d: +0.0033
- Avkastning 120 d: +0.0031
- Avkastning 5 d: +0.0021
- Tilbakekjøp 90 d: +0.0017
- Guiding/oppdatering 30 d: +0.0016
- Kursreaksjon på kontrakter 90 d: +0.0015
- Volum-z (20 d mot 60 d): +0.0014

## ⚠ Sentiment-scoringen feiler

Siste forsøk 2026-10-30T12:59: HTTP 400: {"type":"error","error":{"type":"invalid_request_error","message":"Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase credits."},"request_i

## Forumsentiment som tillegg

Periode med forumdata: 2026-08-31 → 2026-11-16 (56 handelsdager, 46 med fasit = ca. 4.6 uavhengige 10-dagersperioder).

| Signal | Samme dag (reagerer) | Neste 10 dager (forutsier) | p (tilfeldig) |
|---|---|---|---|
| Antall innlegg 5 d | 0.005 | -0.028 | 0.452 |
| Forum-oppmerksomhet mot normalt | -0.001 | 0.005 | 0.894 |
| Sentiment 5 d | 0.046 | -0.03 | 0.42 |
| Sentiment 20 d | 0.023 | 0.027 | 0.496 |
| Stemningen snur (5 d mot 20 d) | 0.05 | -0.027 | 0.432 |
| Forum positivt mens kursen faller | None | -0.011 | 0.736 |
| Andel nyhet/analyse-innlegg | 0.017 | -0.014 | 0.67 |
| Modellscore (uten forum) | -0.091 | -0.015 | 0.692 |
| Kombinert (modell + forum) | -0.189 | -0.018 | 0.578 |

Paper trading i perioden: modell alene -7.1 % (40 handler), modell + forum -7.8 % (40 handler), OSEBX -0.7 %. Tilfeldig median -2.0 %.

## Begrensninger

- Universet er dagens watchlist (overlevelsesskjevhet: aksjer som gikk konkurs er ikke med).
- Markedsverdi bakover i tid bruker dagens aksjeantall.
- Kontraktsverdier tolkes fra tekst med faste valutakurser - grovt.
- Kvartalsrapport-dato er estimert (~63 handelsdager etter forrige).
- Dette er forskning, ikke investeringsråd.
