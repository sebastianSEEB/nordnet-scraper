# Nyhets-ML: paper trading-backtest

Generert 2026-10-30T21:04 UTC · 120 aksjer · 38626 børsmeldinger
Testperiode (modellen har aldri sett disse dagene): 2021-12-01 → 2026-10-30

| | ML-strategi | Regel (KOG-mønster) | OSEBX |
|---|---|---|---|
| Total avkastning | +37.6 % | +15.7 % | +80.3 % |
| Årlig (CAGR) | +6.7 % | +3.0 % | +12.8 % |
| Største fall | -30.2 % | -6.1 % | -16.1 % |
| Sharpe | 0.46 | 0.68 | 0.91 |
| Handler | 962 | 62 | – |
| Treffrate | +53.2 % | +59.7 % | – |

**Tilfeldighetstest:** 35.3 % av 300 tilfeldige porteføljer med samme handelsfrekvens endte like godt eller bedre (median tilfeldig: +24.6 %).

**AUC ut-av-utvalget:** 0.497 (0,50 = mynt­kast) · **IC:** 0.012 (t = 3.0)

## Viktigste signaler (permutasjon, siste 9 mnd)

- Dager siden kvartalsrapport: +0.0054
- Avkastning 60 d: +0.0023
- Omsetning (log): +0.0023
- Kursreaksjon på forrige rapport: +0.0022
- Volum-z (20 d mot 60 d): +0.0022
- Avkastning 120 d: +0.0019
- Avkastning 5 d: +0.0016
- Oppkjøp/fusjon 90 d: +0.0011
- Kursreaksjon på kontrakter 90 d: +0.0010
- Dager til ventet rapport: +0.0010

## ⚠ Sentiment-scoringen feiler

Siste forsøk 2026-10-30T12:59: HTTP 400: {"type":"error","error":{"type":"invalid_request_error","message":"Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase credits."},"request_i

## Forumsentiment som tillegg

Periode med forumdata: 2026-08-31 → 2026-10-30 (45 handelsdager, 35 med fasit = ca. 3.5 uavhengige 10-dagersperioder).

| Signal | Samme dag (reagerer) | Neste 10 dager (forutsier) | p (tilfeldig) |
|---|---|---|---|
| Antall innlegg 5 d | 0.022 | 0.0 | 0.988 |
| Forum-oppmerksomhet mot normalt | -0.011 | -0.019 | 0.63 |
| Sentiment 5 d | 0.038 | -0.041 | 0.332 |
| Sentiment 20 d | 0.021 | 0.034 | 0.45 |
| Stemningen snur (5 d mot 20 d) | 0.042 | -0.049 | 0.182 |
| Forum positivt mens kursen faller | None | -0.035 | 0.348 |
| Andel nyhet/analyse-innlegg | 0.028 | 0.033 | 0.384 |
| Modellscore (uten forum) | -0.097 | -0.03 | 0.492 |
| Kombinert (modell + forum) | -0.198 | -0.034 | 0.408 |

Paper trading i perioden: modell alene +0.5 % (32 handler), modell + forum -6.9 % (32 handler), OSEBX +1.3 %. Tilfeldig median -1.6 %.

## Begrensninger

- Universet er dagens watchlist (overlevelsesskjevhet: aksjer som gikk konkurs er ikke med).
- Markedsverdi bakover i tid bruker dagens aksjeantall.
- Kontraktsverdier tolkes fra tekst med faste valutakurser - grovt.
- Kvartalsrapport-dato er estimert (~63 handelsdager etter forrige).
- Dette er forskning, ikke investeringsråd.
