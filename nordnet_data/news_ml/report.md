# Nyhets-ML: paper trading-backtest

Generert 2026-11-18T23:09 UTC · 120 aksjer · 38990 børsmeldinger
Testperiode (modellen har aldri sett disse dagene): 2021-12-01 → 2026-11-17

| | ML-strategi | Regel (KOG-mønster) | OSEBX |
|---|---|---|---|
| Total avkastning | -12.4 % | +21.2 % | +76.2 % |
| Årlig (CAGR) | -2.6 % | +4.0 % | +12.1 % |
| Største fall | -47.2 % | -5.7 % | -16.1 % |
| Sharpe | -0.06 | 0.80 | 0.87 |
| Handler | 970 | 57 | – |
| Treffrate | +50.4 % | +56.1 % | – |

**Tilfeldighetstest:** 88.3 % av 300 tilfeldige porteføljer med samme handelsfrekvens endte like godt eller bedre (median tilfeldig: +19.0 %).

**AUC ut-av-utvalget:** 0.501 (0,50 = mynt­kast) · **IC:** 0.016 (t = 4.2)

## Viktigste signaler (permutasjon, siste 9 mnd)

- Omsetning (log): +0.0060
- Kursreaksjon på forrige rapport: +0.0046
- Meravkastning 60 d: +0.0026
- Avkastning 120 d: +0.0026
- Rang avkastning 60 d: +0.0026
- Rang volatilitet: +0.0024
- Avkastning 60 d: +0.0022
- Volum-z (20 d mot 60 d): +0.0021
- Dager siden kvartalsrapport: +0.0018
- Avstand til SMA50: +0.0017

## ⚠ Sentiment-scoringen feiler

Siste forsøk 2026-10-30T12:59: HTTP 400: {"type":"error","error":{"type":"invalid_request_error","message":"Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase credits."},"request_i

## Forumsentiment som tillegg

Periode med forumdata: 2026-08-31 → 2026-11-17 (57 handelsdager, 47 med fasit = ca. 4.7 uavhengige 10-dagersperioder).

| Signal | Samme dag (reagerer) | Neste 10 dager (forutsier) | p (tilfeldig) |
|---|---|---|---|
| Antall innlegg 5 d | 0.006 | -0.036 | 0.328 |
| Forum-oppmerksomhet mot normalt | 0.001 | 0.001 | 0.972 |
| Sentiment 5 d | 0.042 | -0.027 | 0.456 |
| Sentiment 20 d | 0.02 | 0.029 | 0.482 |
| Stemningen snur (5 d mot 20 d) | 0.049 | -0.024 | 0.466 |
| Forum positivt mens kursen faller | None | -0.013 | 0.692 |
| Andel nyhet/analyse-innlegg | 0.02 | -0.019 | 0.548 |
| Modellscore (uten forum) | -0.088 | -0.002 | 0.958 |
| Kombinert (modell + forum) | -0.189 | -0.007 | 0.83 |

Paper trading i perioden: modell alene -10.5 % (40 handler), modell + forum -8.4 % (40 handler), OSEBX -1.0 %. Tilfeldig median -2.3 %.

## Begrensninger

- Universet er dagens watchlist (overlevelsesskjevhet: aksjer som gikk konkurs er ikke med).
- Markedsverdi bakover i tid bruker dagens aksjeantall.
- Kontraktsverdier tolkes fra tekst med faste valutakurser - grovt.
- Kvartalsrapport-dato er estimert (~63 handelsdager etter forrige).
- Dette er forskning, ikke investeringsråd.
