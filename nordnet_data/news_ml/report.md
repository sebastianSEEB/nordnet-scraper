# Nyhets-ML: paper trading-backtest

Generert 2026-11-25T01:07 UTC · 120 aksjer · 39107 børsmeldinger
Testperiode (modellen har aldri sett disse dagene): 2021-12-01 → 2026-11-23

| | ML-strategi | Regel (KOG-mønster) | OSEBX |
|---|---|---|---|
| Total avkastning | +63.2 % | +34.4 % | +72.1 % |
| Årlig (CAGR) | +10.3 % | +6.1 % | +11.5 % |
| Største fall | -27.6 % | -5.8 % | -16.1 % |
| Sharpe | 0.63 | 0.98 | 0.84 |
| Handler | 972 | 58 | – |
| Treffrate | +51.1 % | +55.2 % | – |

**Tilfeldighetstest:** 11.7 % av 300 tilfeldige porteføljer med samme handelsfrekvens endte like godt eller bedre (median tilfeldig: +19.5 %).

**AUC ut-av-utvalget:** 0.499 (0,50 = mynt­kast) · **IC:** 0.012 (t = 3.1)

## Viktigste signaler (permutasjon, siste 9 mnd)

- Kursreaksjon på forrige rapport: +0.0051
- Avkastning 120 d: +0.0046
- Omsetning (log): +0.0031
- Avkastning 5 d: +0.0024
- Kursreaksjon på kontrakter 90 d: +0.0018
- Dager siden kvartalsrapport: +0.0018
- Meravkastning 60 d: +0.0017
- Avkastning 60 d: +0.0017
- Kontraktsmeldinger 90 d: +0.0015
- Kontraktsverdi siden rapport / markedsverdi: +0.0015

## ⚠ Sentiment-scoringen feiler

Siste forsøk 2026-10-30T12:59: HTTP 400: {"type":"error","error":{"type":"invalid_request_error","message":"Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase credits."},"request_i

## Forumsentiment som tillegg

Periode med forumdata: 2026-08-31 → 2026-11-23 (61 handelsdager, 51 med fasit = ca. 5.1 uavhengige 10-dagersperioder).

| Signal | Samme dag (reagerer) | Neste 10 dager (forutsier) | p (tilfeldig) |
|---|---|---|---|
| Antall innlegg 5 d | 0.003 | -0.057 | 0.12 |
| Forum-oppmerksomhet mot normalt | 0.003 | -0.006 | 0.882 |
| Sentiment 5 d | 0.043 | -0.017 | 0.604 |
| Sentiment 20 d | 0.018 | 0.037 | 0.35 |
| Stemningen snur (5 d mot 20 d) | 0.05 | -0.02 | 0.51 |
| Forum positivt mens kursen faller | None | 0.009 | 0.77 |
| Andel nyhet/analyse-innlegg | 0.019 | -0.023 | 0.516 |
| Modellscore (uten forum) | -0.095 | 0.01 | 0.776 |
| Kombinert (modell + forum) | -0.197 | 0.012 | 0.71 |

Paper trading i perioden: modell alene -6.8 % (43 handler), modell + forum -6.3 % (43 handler), OSEBX -3.3 %. Tilfeldig median -3.6 %.

## Begrensninger

- Universet er dagens watchlist (overlevelsesskjevhet: aksjer som gikk konkurs er ikke med).
- Markedsverdi bakover i tid bruker dagens aksjeantall.
- Kontraktsverdier tolkes fra tekst med faste valutakurser - grovt.
- Kvartalsrapport-dato er estimert (~63 handelsdager etter forrige).
- Dette er forskning, ikke investeringsråd.
