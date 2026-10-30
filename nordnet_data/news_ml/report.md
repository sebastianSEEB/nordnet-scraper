# Nyhets-ML: paper trading-backtest

Generert 2026-10-30T13:54 UTC · 120 aksjer · 38608 børsmeldinger
Testperiode (modellen har aldri sett disse dagene): 2021-12-01 → 2026-10-30

| | ML-strategi | Regel (KOG-mønster) | OSEBX |
|---|---|---|---|
| Total avkastning | +79.0 % | +20.8 % | +79.7 % |
| Årlig (CAGR) | +12.6 % | +3.9 % | +12.7 % |
| Største fall | -26.9 % | -4.7 % | -16.1 % |
| Sharpe | 0.76 | 0.96 | 0.91 |
| Handler | 966 | 54 | – |
| Treffrate | +52.5 % | +63.0 % | – |

**Tilfeldighetstest:** 5.3 % av 300 tilfeldige porteføljer med samme handelsfrekvens endte like godt eller bedre (median tilfeldig: +19.1 %).

**AUC ut-av-utvalget:** 0.502 (0,50 = mynt­kast) · **IC:** 0.021 (t = 5.6)

## Viktigste signaler (permutasjon, siste 9 mnd)

- Dager siden kvartalsrapport: +0.0072
- Kursreaksjon på forrige rapport: +0.0049
- Kursreaksjon på kontrakter 90 d: +0.0035
- Volum-z (20 d mot 60 d): +0.0034
- Avkastning 120 d: +0.0032
- Omsetning (log): +0.0026
- Avstand til SMA200: +0.0024
- Rang avkastning 60 d: +0.0019
- Avkastning 60 d: +0.0018
- Avkastning 5 d: +0.0017

## ⚠ Sentiment-scoringen feiler

Siste forsøk 2026-10-30T12:59: HTTP 400: {"type":"error","error":{"type":"invalid_request_error","message":"Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase credits."},"request_i

## Forumsentiment som tillegg

Periode med forumdata: 2021-12-01 → 2026-10-30 (1235 handelsdager, 1225 med fasit = ca. 122.5 uavhengige 10-dagersperioder).

| Signal | Samme dag (reagerer) | Neste 10 dager (forutsier) | p (tilfeldig) |
|---|---|---|---|
| Antall innlegg 5 d | 0.0 | -0.003 | 0.914 |
| Forum-oppmerksomhet mot normalt | -0.0 | 0.007 | 0.618 |
| Sentiment 5 d | 0.026 | -0.007 | 0.884 |
| Sentiment 20 d | 0.028 | 0.037 | 0.494 |
| Stemningen snur (5 d mot 20 d) | 0.029 | -0.001 | 0.994 |
| Forum positivt mens kursen faller | None | 0.025 | 0.508 |
| Andel nyhet/analyse-innlegg | 0.039 | 0.076 | 0.084 |
| Modellscore (uten forum) | -0.029 | 0.021 | 0.03 |
| Kombinert (modell + forum) | -0.033 | 0.021 | 0.024 |

Paper trading i perioden: modell alene +79.0 % (966 handler), modell + forum +94.2 % (984 handler), OSEBX +79.7 %. Tilfeldig median +21.1 %.

## Begrensninger

- Universet er dagens watchlist (overlevelsesskjevhet: aksjer som gikk konkurs er ikke med).
- Markedsverdi bakover i tid bruker dagens aksjeantall.
- Kontraktsverdier tolkes fra tekst med faste valutakurser - grovt.
- Kvartalsrapport-dato er estimert (~63 handelsdager etter forrige).
- Dette er forskning, ikke investeringsråd.
