# Nyhets-ML: paper trading-backtest

Generert 2026-10-30T16:04 UTC · 120 aksjer · 38626 børsmeldinger
Testperiode (modellen har aldri sett disse dagene): 2021-12-01 → 2026-10-30

| | ML-strategi | Regel (KOG-mønster) | OSEBX |
|---|---|---|---|
| Total avkastning | +23.7 % | +16.0 % | +79.9 % |
| Årlig (CAGR) | +4.4 % | +3.1 % | +12.7 % |
| Største fall | -42.7 % | -6.1 % | -16.1 % |
| Sharpe | 0.33 | 0.69 | 0.91 |
| Handler | 966 | 62 | – |
| Treffrate | +50.4 % | +59.7 % | – |

**Tilfeldighetstest:** 43.3 % av 300 tilfeldige porteføljer med samme handelsfrekvens endte like godt eller bedre (median tilfeldig: +17.4 %).

**AUC ut-av-utvalget:** 0.498 (0,50 = mynt­kast) · **IC:** 0.014 (t = 3.6)

## Viktigste signaler (permutasjon, siste 9 mnd)

- Dager siden kvartalsrapport: +0.0045
- Kursreaksjon på forrige rapport: +0.0032
- Omsetning (log): +0.0031
- Avkastning 5 d: +0.0024
- Volum-z (20 d mot 60 d): +0.0022
- Avkastning 120 d: +0.0021
- Avkastning 60 d: +0.0020
- Kursreaksjon på kontrakter 90 d: +0.0014
- Oppkjøp/fusjon 90 d: +0.0014
- Dager til ventet rapport: +0.0011

## ⚠ Sentiment-scoringen feiler

Siste forsøk 2026-10-30T12:59: HTTP 400: {"type":"error","error":{"type":"invalid_request_error","message":"Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase credits."},"request_i

## Forumsentiment som tillegg

Periode med forumdata: 2026-08-31 → 2026-10-30 (45 handelsdager, 35 med fasit = ca. 3.5 uavhengige 10-dagersperioder).

| Signal | Samme dag (reagerer) | Neste 10 dager (forutsier) | p (tilfeldig) |
|---|---|---|---|
| Antall innlegg 5 d | 0.011 | 0.0 | 0.998 |
| Forum-oppmerksomhet mot normalt | -0.033 | -0.019 | 0.632 |
| Sentiment 5 d | 0.03 | -0.041 | 0.324 |
| Sentiment 20 d | 0.023 | 0.033 | 0.46 |
| Stemningen snur (5 d mot 20 d) | 0.038 | -0.049 | 0.188 |
| Forum positivt mens kursen faller | None | -0.036 | 0.338 |
| Andel nyhet/analyse-innlegg | 0.032 | 0.034 | 0.362 |
| Modellscore (uten forum) | -0.092 | -0.028 | 0.55 |
| Kombinert (modell + forum) | -0.187 | -0.034 | 0.432 |

Paper trading i perioden: modell alene +1.1 % (32 handler), modell + forum -5.0 % (32 handler), OSEBX +1.1 %. Tilfeldig median -1.7 %.

## Begrensninger

- Universet er dagens watchlist (overlevelsesskjevhet: aksjer som gikk konkurs er ikke med).
- Markedsverdi bakover i tid bruker dagens aksjeantall.
- Kontraktsverdier tolkes fra tekst med faste valutakurser - grovt.
- Kvartalsrapport-dato er estimert (~63 handelsdager etter forrige).
- Dette er forskning, ikke investeringsråd.
