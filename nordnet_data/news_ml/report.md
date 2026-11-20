# Nyhets-ML: paper trading-backtest

Generert 2026-11-20T22:49 UTC · 119 aksjer · 39077 børsmeldinger
Testperiode (modellen har aldri sett disse dagene): 2021-12-01 → 2026-11-20

| | ML-strategi | Regel (KOG-mønster) | OSEBX |
|---|---|---|---|
| Total avkastning | +45.2 % | +23.9 % | +71.3 % |
| Årlig (CAGR) | +7.8 % | +4.4 % | +11.4 % |
| Største fall | -31.2 % | -5.8 % | -16.1 % |
| Sharpe | 0.50 | 0.88 | 0.83 |
| Handler | 964 | 57 | – |
| Treffrate | +50.5 % | +54.4 % | – |

**Tilfeldighetstest:** 23.7 % av 300 tilfeldige porteføljer med samme handelsfrekvens endte like godt eller bedre (median tilfeldig: +19.5 %).

**AUC ut-av-utvalget:** 0.499 (0,50 = mynt­kast) · **IC:** 0.012 (t = 3.2)

## Viktigste signaler (permutasjon, siste 9 mnd)

- Omsetning (log): +0.0046
- Avkastning 120 d: +0.0035
- Rang volatilitet: +0.0028
- Kursreaksjon på kontrakter 90 d: +0.0024
- Rang avkastning 60 d: +0.0022
- Kursreaksjon på forrige rapport: +0.0018
- Kontraktsverdi 90 d / markedsverdi: +0.0016
- Meravkastning 60 d: +0.0015
- Kontraktsverdi siden rapport / markedsverdi: +0.0014
- Avstand til SMA200: +0.0011

## ⚠ Sentiment-scoringen feiler

Siste forsøk 2026-10-30T12:59: HTTP 400: {"type":"error","error":{"type":"invalid_request_error","message":"Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase credits."},"request_i

## Forumsentiment som tillegg

Periode med forumdata: 2026-08-31 → 2026-11-20 (60 handelsdager, 50 med fasit = ca. 5.0 uavhengige 10-dagersperioder).

| Signal | Samme dag (reagerer) | Neste 10 dager (forutsier) | p (tilfeldig) |
|---|---|---|---|
| Antall innlegg 5 d | -0.001 | -0.053 | 0.158 |
| Forum-oppmerksomhet mot normalt | 0.003 | -0.004 | 0.91 |
| Sentiment 5 d | 0.045 | -0.018 | 0.594 |
| Sentiment 20 d | 0.021 | 0.038 | 0.348 |
| Stemningen snur (5 d mot 20 d) | 0.05 | -0.021 | 0.524 |
| Forum positivt mens kursen faller | None | 0.002 | 0.936 |
| Andel nyhet/analyse-innlegg | 0.019 | -0.023 | 0.474 |
| Modellscore (uten forum) | -0.089 | -0.004 | 0.92 |
| Kombinert (modell + forum) | -0.189 | -0.002 | 0.952 |

Paper trading i perioden: modell alene -5.9 % (40 handler), modell + forum -4.8 % (40 handler), OSEBX -3.8 %. Tilfeldig median -4.9 %.

## Begrensninger

- Universet er dagens watchlist (overlevelsesskjevhet: aksjer som gikk konkurs er ikke med).
- Markedsverdi bakover i tid bruker dagens aksjeantall.
- Kontraktsverdier tolkes fra tekst med faste valutakurser - grovt.
- Kvartalsrapport-dato er estimert (~63 handelsdager etter forrige).
- Dette er forskning, ikke investeringsråd.
