# Nyhets-ML: paper trading-backtest

Generert 2026-11-10T00:30 UTC · 120 aksjer · 38803 børsmeldinger
Testperiode (modellen har aldri sett disse dagene): 2021-12-01 → 2026-11-06

| | ML-strategi | Regel (KOG-mønster) | OSEBX |
|---|---|---|---|
| Total avkastning | +35.3 % | +14.6 % | +72.6 % |
| Årlig (CAGR) | +6.3 % | +2.8 % | +11.7 % |
| Største fall | -36.3 % | -6.1 % | -16.1 % |
| Sharpe | 0.44 | 0.63 | 0.85 |
| Handler | 967 | 62 | – |
| Treffrate | +51.6 % | +59.7 % | – |

**Tilfeldighetstest:** 31.7 % av 300 tilfeldige porteføljer med samme handelsfrekvens endte like godt eller bedre (median tilfeldig: +16.5 %).

**AUC ut-av-utvalget:** 0.496 (0,50 = mynt­kast) · **IC:** 0.012 (t = 3.1)

## Viktigste signaler (permutasjon, siste 9 mnd)

- Kursreaksjon på forrige rapport: +0.0042
- Dager siden kvartalsrapport: +0.0036
- Avstand til SMA200: +0.0035
- Kursreaksjon på kontrakter 90 d: +0.0028
- Avkastning 120 d: +0.0026
- Avkastning 60 d: +0.0024
- Volum-z (20 d mot 60 d): +0.0022
- OSEBX volatilitet: +0.0021
- Omsetning (log): +0.0018
- RSI 14: +0.0016

## ⚠ Sentiment-scoringen feiler

Siste forsøk 2026-10-30T12:59: HTTP 400: {"type":"error","error":{"type":"invalid_request_error","message":"Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase credits."},"request_i

## Forumsentiment som tillegg

Periode med forumdata: 2026-08-31 → 2026-11-06 (50 handelsdager, 40 med fasit = ca. 4.0 uavhengige 10-dagersperioder).

| Signal | Samme dag (reagerer) | Neste 10 dager (forutsier) | p (tilfeldig) |
|---|---|---|---|
| Antall innlegg 5 d | 0.006 | -0.007 | 0.874 |
| Forum-oppmerksomhet mot normalt | -0.012 | -0.0 | 0.994 |
| Sentiment 5 d | 0.044 | -0.052 | 0.182 |
| Sentiment 20 d | 0.022 | 0.031 | 0.5 |
| Stemningen snur (5 d mot 20 d) | 0.052 | -0.055 | 0.124 |
| Forum positivt mens kursen faller | None | -0.036 | 0.27 |
| Andel nyhet/analyse-innlegg | 0.013 | 0.013 | 0.728 |
| Modellscore (uten forum) | -0.097 | -0.024 | 0.578 |
| Kombinert (modell + forum) | -0.201 | -0.033 | 0.406 |

Paper trading i perioden: modell alene -7.2 % (32 handler), modell + forum -5.1 % (32 handler), OSEBX -3.1 %. Tilfeldig median -4.4 %.

## Begrensninger

- Universet er dagens watchlist (overlevelsesskjevhet: aksjer som gikk konkurs er ikke med).
- Markedsverdi bakover i tid bruker dagens aksjeantall.
- Kontraktsverdier tolkes fra tekst med faste valutakurser - grovt.
- Kvartalsrapport-dato er estimert (~63 handelsdager etter forrige).
- Dette er forskning, ikke investeringsråd.
