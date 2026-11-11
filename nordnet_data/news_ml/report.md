# Nyhets-ML: paper trading-backtest

Generert 2026-11-11T23:01 UTC · 120 aksjer · 38882 børsmeldinger
Testperiode (modellen har aldri sett disse dagene): 2021-12-01 → 2026-11-11

| | ML-strategi | Regel (KOG-mønster) | OSEBX |
|---|---|---|---|
| Total avkastning | +20.4 % | +14.8 % | +77.1 % |
| Årlig (CAGR) | +3.8 % | +2.8 % | +12.2 % |
| Største fall | -37.4 % | -6.1 % | -16.1 % |
| Sharpe | 0.30 | 0.63 | 0.88 |
| Handler | 964 | 64 | – |
| Treffrate | +51.9 % | +59.4 % | – |

**Tilfeldighetstest:** 51.0 % av 300 tilfeldige porteføljer med samme handelsfrekvens endte like godt eller bedre (median tilfeldig: +20.8 %).

**AUC ut-av-utvalget:** 0.497 (0,50 = mynt­kast) · **IC:** 0.010 (t = 2.8)

## Viktigste signaler (permutasjon, siste 9 mnd)

- Kursreaksjon på forrige rapport: +0.0058
- Dager siden kvartalsrapport: +0.0053
- Omsetning (log): +0.0040
- Avkastning 120 d: +0.0034
- Volum-z (20 d mot 60 d): +0.0026
- Avkastning 60 d: +0.0026
- Avkastning 5 d: +0.0023
- Avstand til SMA200: +0.0022
- Emisjoner/lån 90 d: +0.0011
- Kursreaksjon på kontrakter 90 d: +0.0010

## ⚠ Sentiment-scoringen feiler

Siste forsøk 2026-10-30T12:59: HTTP 400: {"type":"error","error":{"type":"invalid_request_error","message":"Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase credits."},"request_i

## Forumsentiment som tillegg

Periode med forumdata: 2026-08-31 → 2026-11-11 (53 handelsdager, 43 med fasit = ca. 4.3 uavhengige 10-dagersperioder).

| Signal | Samme dag (reagerer) | Neste 10 dager (forutsier) | p (tilfeldig) |
|---|---|---|---|
| Antall innlegg 5 d | 0.011 | -0.009 | 0.814 |
| Forum-oppmerksomhet mot normalt | -0.006 | 0.01 | 0.812 |
| Sentiment 5 d | 0.045 | -0.04 | 0.28 |
| Sentiment 20 d | 0.026 | 0.026 | 0.546 |
| Stemningen snur (5 d mot 20 d) | 0.049 | -0.039 | 0.264 |
| Forum positivt mens kursen faller | None | -0.015 | 0.656 |
| Andel nyhet/analyse-innlegg | 0.015 | -0.004 | 0.938 |
| Modellscore (uten forum) | -0.096 | -0.012 | 0.758 |
| Kombinert (modell + forum) | -0.198 | -0.015 | 0.684 |

Paper trading i perioden: modell alene -1.0 % (38 handler), modell + forum -4.3 % (40 handler), OSEBX -0.5 %. Tilfeldig median -1.6 %.

## Begrensninger

- Universet er dagens watchlist (overlevelsesskjevhet: aksjer som gikk konkurs er ikke med).
- Markedsverdi bakover i tid bruker dagens aksjeantall.
- Kontraktsverdier tolkes fra tekst med faste valutakurser - grovt.
- Kvartalsrapport-dato er estimert (~63 handelsdager etter forrige).
- Dette er forskning, ikke investeringsråd.
