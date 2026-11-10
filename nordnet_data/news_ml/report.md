# Nyhets-ML: paper trading-backtest

Generert 2026-11-10T21:59 UTC · 119 aksjer · 38852 børsmeldinger
Testperiode (modellen har aldri sett disse dagene): 2021-12-01 → 2026-11-10

| | ML-strategi | Regel (KOG-mønster) | OSEBX |
|---|---|---|---|
| Total avkastning | +17.4 % | +15.0 % | +75.0 % |
| Årlig (CAGR) | +3.3 % | +2.9 % | +12.0 % |
| Største fall | -38.4 % | -6.1 % | -16.1 % |
| Sharpe | 0.27 | 0.64 | 0.86 |
| Handler | 962 | 64 | – |
| Treffrate | +52.1 % | +59.4 % | – |

**Tilfeldighetstest:** 48.7 % av 300 tilfeldige porteføljer med samme handelsfrekvens endte like godt eller bedre (median tilfeldig: +16.6 %).

**AUC ut-av-utvalget:** 0.497 (0,50 = mynt­kast) · **IC:** 0.014 (t = 3.7)

## Viktigste signaler (permutasjon, siste 9 mnd)

- Dager siden kvartalsrapport: +0.0046
- Kursreaksjon på forrige rapport: +0.0040
- Omsetning (log): +0.0032
- Volum-z (20 d mot 60 d): +0.0028
- Avstand til SMA200: +0.0028
- Kursreaksjon på kontrakter 90 d: +0.0025
- Kontraktsverdi 90 d / markedsverdi: +0.0021
- Avkastning 120 d: +0.0020
- Emisjoner/lån 90 d: +0.0015
- Rang avkastning 60 d: +0.0015

## ⚠ Sentiment-scoringen feiler

Siste forsøk 2026-10-30T12:59: HTTP 400: {"type":"error","error":{"type":"invalid_request_error","message":"Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase credits."},"request_i

## Forumsentiment som tillegg

Periode med forumdata: 2026-08-31 → 2026-11-10 (52 handelsdager, 42 med fasit = ca. 4.2 uavhengige 10-dagersperioder).

| Signal | Samme dag (reagerer) | Neste 10 dager (forutsier) | p (tilfeldig) |
|---|---|---|---|
| Antall innlegg 5 d | 0.009 | -0.007 | 0.872 |
| Forum-oppmerksomhet mot normalt | -0.012 | 0.004 | 0.898 |
| Sentiment 5 d | 0.047 | -0.044 | 0.274 |
| Sentiment 20 d | 0.026 | 0.025 | 0.57 |
| Stemningen snur (5 d mot 20 d) | 0.052 | -0.041 | 0.26 |
| Forum positivt mens kursen faller | None | -0.02 | 0.544 |
| Andel nyhet/analyse-innlegg | 0.013 | -0.002 | 0.952 |
| Modellscore (uten forum) | -0.095 | -0.011 | 0.78 |
| Kombinert (modell + forum) | -0.201 | -0.017 | 0.674 |

Paper trading i perioden: modell alene -0.3 % (35 handler), modell + forum -8.6 % (38 handler), OSEBX -1.7 %. Tilfeldig median -2.3 %.

## Begrensninger

- Universet er dagens watchlist (overlevelsesskjevhet: aksjer som gikk konkurs er ikke med).
- Markedsverdi bakover i tid bruker dagens aksjeantall.
- Kontraktsverdier tolkes fra tekst med faste valutakurser - grovt.
- Kvartalsrapport-dato er estimert (~63 handelsdager etter forrige).
- Dette er forskning, ikke investeringsråd.
