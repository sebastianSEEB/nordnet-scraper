# Nyhets-ML: paper trading-backtest

Generert 2026-10-30T14:08 UTC · 120 aksjer · 38610 børsmeldinger
Testperiode (modellen har aldri sett disse dagene): 2021-12-01 → 2026-10-30

| | ML-strategi | Regel (KOG-mønster) | OSEBX |
|---|---|---|---|
| Total avkastning | +20.9 % | +15.9 % | +80.5 % |
| Årlig (CAGR) | +3.9 % | +3.0 % | +12.8 % |
| Største fall | -32.1 % | -4.7 % | -16.1 % |
| Sharpe | 0.31 | 0.71 | 0.91 |
| Handler | 972 | 60 | – |
| Treffrate | +51.0 % | +58.3 % | – |

**Tilfeldighetstest:** 46.3 % av 300 tilfeldige porteføljer med samme handelsfrekvens endte like godt eller bedre (median tilfeldig: +17.5 %).

**AUC ut-av-utvalget:** 0.500 (0,50 = mynt­kast) · **IC:** 0.018 (t = 4.9)

## Viktigste signaler (permutasjon, siste 9 mnd)

- Dager siden kvartalsrapport: +0.0063
- Kursreaksjon på forrige rapport: +0.0052
- Avkastning 120 d: +0.0037
- Volum-z (20 d mot 60 d): +0.0030
- Kursreaksjon på kontrakter 90 d: +0.0015
- Omsetning (log): +0.0015
- Innsidesalg 90 d: +0.0015
- Avkastning 60 d: +0.0014
- Avkastning 5 d: +0.0014
- Oppkjøp/fusjon 90 d: +0.0011

## ⚠ Sentiment-scoringen feiler

Siste forsøk 2026-10-30T12:59: HTTP 400: {"type":"error","error":{"type":"invalid_request_error","message":"Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase credits."},"request_i

## Forumsentiment som tillegg

Periode med forumdata: 2026-08-31 → 2026-10-30 (45 handelsdager, 35 med fasit = ca. 3.5 uavhengige 10-dagersperioder).

| Signal | Samme dag (reagerer) | Neste 10 dager (forutsier) | p (tilfeldig) |
|---|---|---|---|
| Antall innlegg 5 d | 0.011 | 0.001 | 0.986 |
| Forum-oppmerksomhet mot normalt | -0.035 | -0.018 | 0.644 |
| Sentiment 5 d | 0.03 | -0.041 | 0.328 |
| Sentiment 20 d | 0.022 | 0.034 | 0.458 |
| Stemningen snur (5 d mot 20 d) | 0.038 | -0.049 | 0.178 |
| Forum positivt mens kursen faller | None | -0.035 | 0.346 |
| Andel nyhet/analyse-innlegg | 0.032 | 0.034 | 0.366 |
| Modellscore (uten forum) | -0.104 | -0.019 | 0.67 |
| Kombinert (modell + forum) | -0.198 | -0.027 | 0.53 |

Paper trading i perioden: modell alene +2.6 % (32 handler), modell + forum +0.6 % (32 handler), OSEBX +1.4 %. Tilfeldig median -1.2 %.

## Begrensninger

- Universet er dagens watchlist (overlevelsesskjevhet: aksjer som gikk konkurs er ikke med).
- Markedsverdi bakover i tid bruker dagens aksjeantall.
- Kontraktsverdier tolkes fra tekst med faste valutakurser - grovt.
- Kvartalsrapport-dato er estimert (~63 handelsdager etter forrige).
- Dette er forskning, ikke investeringsråd.
