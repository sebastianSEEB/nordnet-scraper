# Nyhets-ML: paper trading-backtest

Generert 2026-11-28T00:15 UTC · 120 aksjer · 39198 børsmeldinger
Testperiode (modellen har aldri sett disse dagene): 2021-12-01 → 2026-11-26

| | ML-strategi | Regel (KOG-mønster) | OSEBX |
|---|---|---|---|
| Total avkastning | +48.1 % | +35.6 % | +73.1 % |
| Årlig (CAGR) | +8.2 % | +6.3 % | +11.6 % |
| Største fall | -39.1 % | -5.8 % | -16.1 % |
| Sharpe | 0.54 | 1.01 | 0.84 |
| Handler | 977 | 59 | – |
| Treffrate | +51.4 % | +55.9 % | – |

**Tilfeldighetstest:** 19.7 % av 300 tilfeldige porteføljer med samme handelsfrekvens endte like godt eller bedre (median tilfeldig: +17.9 %).

**AUC ut-av-utvalget:** 0.500 (0,50 = mynt­kast) · **IC:** 0.017 (t = 4.4)

## Viktigste signaler (permutasjon, siste 9 mnd)

- Kursreaksjon på forrige rapport: +0.0049
- Omsetning (log): +0.0043
- Kursreaksjon på kontrakter 90 d: +0.0031
- Kontraktsverdi 90 d / markedsverdi: +0.0022
- Avkastning 120 d: +0.0021
- OSEBX volatilitet: +0.0020
- Avkastning 5 d: +0.0017
- Avkastning 60 d: +0.0015
- Rang avkastning 60 d: +0.0015
- Kontraktsverdi siden rapport / markedsverdi: +0.0011

## ⚠ Sentiment-scoringen feiler

Siste forsøk 2026-10-30T12:59: HTTP 400: {"type":"error","error":{"type":"invalid_request_error","message":"Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase credits."},"request_i

## Forumsentiment som tillegg

Periode med forumdata: 2026-08-31 → 2026-11-26 (64 handelsdager, 54 med fasit = ca. 5.4 uavhengige 10-dagersperioder).

| Signal | Samme dag (reagerer) | Neste 10 dager (forutsier) | p (tilfeldig) |
|---|---|---|---|
| Antall innlegg 5 d | 0.002 | -0.07 | 0.068 |
| Forum-oppmerksomhet mot normalt | 0.002 | -0.015 | 0.612 |
| Sentiment 5 d | 0.043 | -0.012 | 0.742 |
| Sentiment 20 d | 0.018 | 0.039 | 0.328 |
| Stemningen snur (5 d mot 20 d) | 0.047 | -0.016 | 0.606 |
| Forum positivt mens kursen faller | None | 0.021 | 0.532 |
| Andel nyhet/analyse-innlegg | 0.021 | -0.017 | 0.566 |
| Modellscore (uten forum) | -0.091 | -0.01 | 0.804 |
| Kombinert (modell + forum) | -0.19 | -0.001 | 0.982 |

Paper trading i perioden: modell alene -11.1 % (44 handler), modell + forum -17.6 % (48 handler), OSEBX -2.8 %. Tilfeldig median -5.4 %.

## Begrensninger

- Universet er dagens watchlist (overlevelsesskjevhet: aksjer som gikk konkurs er ikke med).
- Markedsverdi bakover i tid bruker dagens aksjeantall.
- Kontraktsverdier tolkes fra tekst med faste valutakurser - grovt.
- Kvartalsrapport-dato er estimert (~63 handelsdager etter forrige).
- Dette er forskning, ikke investeringsråd.
