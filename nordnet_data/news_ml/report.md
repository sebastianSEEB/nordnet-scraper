# Nyhets-ML: paper trading-backtest

Generert 2026-11-17T00:30 UTC · 120 aksjer · 38934 børsmeldinger
Testperiode (modellen har aldri sett disse dagene): 2021-12-01 → 2026-11-13

| | ML-strategi | Regel (KOG-mønster) | OSEBX |
|---|---|---|---|
| Total avkastning | +2.4 % | +15.4 % | +77.5 % |
| Årlig (CAGR) | +0.5 % | +2.9 % | +12.3 % |
| Største fall | -29.3 % | -5.7 % | -16.1 % |
| Sharpe | 0.12 | 0.65 | 0.88 |
| Handler | 965 | 57 | – |
| Treffrate | +49.3 % | +56.1 % | – |

**Tilfeldighetstest:** 71.3 % av 300 tilfeldige porteføljer med samme handelsfrekvens endte like godt eller bedre (median tilfeldig: +18.3 %).

**AUC ut-av-utvalget:** 0.500 (0,50 = mynt­kast) · **IC:** 0.015 (t = 3.8)

## Viktigste signaler (permutasjon, siste 9 mnd)

- Omsetning (log): +0.0048
- Kursreaksjon på forrige rapport: +0.0039
- Avkastning 60 d: +0.0038
- Avkastning 120 d: +0.0019
- Kontraktsverdi siden rapport / markedsverdi: +0.0019
- Volum-z (20 d mot 60 d): +0.0016
- Dager siden kvartalsrapport: +0.0016
- Avkastning 5 d: +0.0014
- Meravkastning 60 d: +0.0014
- Avstand til SMA50: +0.0012

## ⚠ Sentiment-scoringen feiler

Siste forsøk 2026-10-30T12:59: HTTP 400: {"type":"error","error":{"type":"invalid_request_error","message":"Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase credits."},"request_i

## Forumsentiment som tillegg

Periode med forumdata: 2026-08-31 → 2026-11-13 (55 handelsdager, 45 med fasit = ca. 4.5 uavhengige 10-dagersperioder).

| Signal | Samme dag (reagerer) | Neste 10 dager (forutsier) | p (tilfeldig) |
|---|---|---|---|
| Antall innlegg 5 d | 0.005 | -0.023 | 0.558 |
| Forum-oppmerksomhet mot normalt | -0.005 | 0.006 | 0.89 |
| Sentiment 5 d | 0.05 | -0.033 | 0.38 |
| Sentiment 20 d | 0.027 | 0.027 | 0.512 |
| Stemningen snur (5 d mot 20 d) | 0.053 | -0.03 | 0.372 |
| Forum positivt mens kursen faller | None | -0.01 | 0.782 |
| Andel nyhet/analyse-innlegg | 0.016 | -0.01 | 0.768 |
| Modellscore (uten forum) | -0.087 | -0.01 | 0.796 |
| Kombinert (modell + forum) | -0.184 | -0.012 | 0.746 |

Paper trading i perioden: modell alene -3.2 % (40 handler), modell + forum -7.6 % (40 handler), OSEBX -0.3 %. Tilfeldig median -2.1 %.

## Begrensninger

- Universet er dagens watchlist (overlevelsesskjevhet: aksjer som gikk konkurs er ikke med).
- Markedsverdi bakover i tid bruker dagens aksjeantall.
- Kontraktsverdier tolkes fra tekst med faste valutakurser - grovt.
- Kvartalsrapport-dato er estimert (~63 handelsdager etter forrige).
- Dette er forskning, ikke investeringsråd.
